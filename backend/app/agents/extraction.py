"""Deterministic, conservative extraction from attributed HTML/JSON-LD snapshots."""
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from html.parser import HTMLParser
import json
import re
from urllib.parse import urljoin

from pydantic import JsonValue, ValidationError

from app.harness.research_types import Evidence, Observation, PageExtraction, ProductExtraction, RetrievedSource

EXTRACTOR_VERSION = "attributed-extraction-1.0"
REQUIRED_FIELDS = ("brand", "product", "sku", "variant", "product_type", "price", "currency", "weight_g", "pack_qty", "ingredients", "marketing_claim", "channels", "packaging", "positioning", "audience", "public_review", "reported_launch")


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


class HTML(HTMLParser):
    def __init__(self, body: str):
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.links: list[str] = []
        self.structured: list[JsonValue] = []
        self.script = False
        self.json_script = False
        self.hidden = 0
        self.buffer = ""
        self.title = ""
        self.in_title = False
        self.in_h1 = False
        self.h1 = ""
        self.label_tag: str | None = None
        self.label_buffer = ""
        self.last_label = ""
        self.labels: dict[str, str] = {}
        self.restricted = False
        self.feed(body)
        self.close()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "script":
            self.script = True
            self.json_script = attributes.get("type", "").lower() == "application/ld+json"
            self.buffer = ""
        if tag in {"style", "noscript"}:
            self.hidden += 1
        if tag == "title":
            self.in_title = True
        if tag == "h1":
            self.in_h1 = True
        if tag in {"dt", "dd"}:
            self.label_tag, self.label_buffer = tag, ""
        if tag == "a" and attributes.get("href"):
            self.links.append(attributes["href"])
        if tag == "input" and attributes.get("type", "").lower() == "password":
            self.restricted = True
        if tag == "meta" and attributes.get("name", "").lower() in {"robots", "latherlensbot"}:
            if any(token in attributes.get("content", "").lower() for token in ("noarchive", "nosnippet", "none")):
                self.restricted = True

    def handle_endtag(self, tag):
        if tag == "script":
            if self.json_script:
                try:
                    parsed = json.loads(self.buffer, parse_float=Decimal, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
                    # Decimal values are canonicalized as exact strings for provenance/precision.
                    normalized = json.loads(canonical(parsed))
                    self.structured.append(normalized)
                    if any(node.get("isAccessibleForFree") is False for node, _ in nodes(normalized)):
                        self.restricted = True
                except (ValueError, RecursionError):
                    self.text.append("[Malformed structured data; unavailable]")
            self.script = self.json_script = False
        if tag in {"style", "noscript"}:
            self.hidden = max(0, self.hidden - 1)
        if tag == "title":
            self.in_title = False
        if tag == "h1":
            self.in_h1 = False
        if tag in {"dt", "dd"} and self.label_tag == tag:
            if tag == "dt":
                self.last_label = self.label_buffer.strip().casefold()
            elif self.last_label:
                self.labels[self.last_label] = self.label_buffer.strip()
            self.label_tag = None

    def handle_data(self, data):
        if self.script:
            if self.json_script:
                self.buffer += data
        elif not self.hidden:
            cleaned = " ".join(data.split())
            if cleaned:
                self.text.append(cleaned)
                if self.in_title:
                    self.title += cleaned
                if self.in_h1:
                    self.h1 += cleaned
                if self.label_tag:
                    self.label_buffer += (" " if self.label_buffer else "") + cleaned


def parse_html(body: str, url: str) -> tuple[str, str, tuple[JsonValue, ...], tuple[str, ...], bool]:
    parsed = HTML(body)
    text = "\n".join(parsed.text) + "\nJSON-LD\n" + canonical(parsed.structured)
    if len(text.encode()) > 256000:
        raise ValueError("excerpt_limit")
    # Do not execute scripts, load images/iframes, resolve remote JSON-LD contexts or follow arbitrary links.
    links = tuple(dict.fromkeys(urljoin(url, link) for link in parsed.links))[:50]
    restricted = parsed.restricted or bool(re.search(r"\b(?:captcha|access denied|subscribe to continue|sign in to continue)\b", " ".join(parsed.text), re.I))
    return parsed.title[:500] or "Untitled public page", text, tuple(parsed.structured), links, restricted


def nodes(value, pointer="", depth=0):
    if depth > 12:
        return
    if isinstance(value, dict):
        yield value, pointer
        for key, child in value.items():
            yield from nodes(child, pointer + "/" + key.replace("~", "~0").replace("/", "~1"), depth + 1)
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            yield from nodes(child, pointer + "/" + str(index), depth + 1)


def fact(source: RetrievedSource, field: str, raw, pointer: str, *, value=None, marketing=False) -> Observation:
    if raw is None or (isinstance(raw, str) and not raw.strip()) or raw == [] or raw == {}:
        return unknown(field)
    quote = canonical(raw)
    if not source.excerpt or quote not in source.excerpt or len(quote) > 10000:
        return unknown(field, "evidence_unavailable")
    evidence = Evidence(source_id=source.source_id, quote=quote, quote_hash=sha256(quote.encode()).hexdigest(), locator="json:" + pointer)
    return Observation(field=field, value=raw if value is None else value, evidence=(evidence,), kind="competitor_marketing_claim" if marketing else "fact")


def unknown(field: str, reason="not_disclosed") -> Observation:
    return Observation(field=field, value=None, unavailable_reason=reason)


def number(value, *, positive=False) -> Decimal | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        parsed = Decimal(str(value))
        if not parsed.is_finite() or parsed < 0 or (positive and parsed <= 0) or int(parsed.as_tuple().exponent) < -4 or parsed >= Decimal("100000000000000"):
            return None
        return parsed
    except (InvalidOperation, TypeError, ValueError):
        return None


def extract(source: RetrievedSource, competitor_name: str, *, first_party: bool) -> PageExtraction:
    from app.agents.snippet_extraction import eligible, extract_snippet
    if eligible(source, first_party):
        return extract_snippet(source)
    if source.access_status != "ok" or source.evidence_kind != "page_excerpt":
        reason = source.reason or "not_a_retrieved_page"
        return PageExtraction(source_id=source.source_id, products=(), observations=tuple(unknown(field, reason) for field in REQUIRED_FIELDS), limitations=(reason,))
    products: list[ProductExtraction] = []
    page_facts: list[Observation] = []
    limitations: list[str] = []
    for node, pointer in list(nodes(source.structured))[:300]:
        kind = node.get("@type")
        kinds = kind if isinstance(kind, list) else [kind]
        if "Product" in kinds:
            if len(products) >= 10:
                limitations.append("product_limit")
                break
            brand = node.get("brand")
            brand_name = brand.get("name") if isinstance(brand, dict) else brand
            if (brand_name and str(brand_name).casefold() != competitor_name.casefold()) or (not first_party and str(brand_name).casefold() != competitor_name.casefold()):
                limitations.append("other_or_unattributed_brand_excluded")
                continue
            if not isinstance(node.get("name"), str) or not node["name"].strip():
                limitations.append("unnamed_product_excluded")
                continue
            fields = []
            for key, field in [("name", "product"), ("sku", "sku"), ("model", "variant"), ("category", "product_type"), ("brand", "brand"), ("audience", "audience")]:
                raw = node.get(key)
                fields.append(fact(source, field, raw, pointer + "/" + key) if raw is not None else unknown(field))
            description = node.get("description")
            fields.append(fact(source, "marketing_claim", description, pointer + "/description", marketing=True) if isinstance(description, str) and description else unknown("marketing_claim"))
            props = node.get("additionalProperty", [])
            props_single = isinstance(props, dict)
            if isinstance(props, dict):
                props = [props]
            properties = {str(prop.get("name", "")).casefold(): (prop.get("value"), pointer + "/additionalProperty" + ("" if props_single else f"/{index}") + "/value") for index, prop in enumerate(props) if isinstance(prop, dict)} if isinstance(props, list) else {}
            extracted_props = {}
            for field, names in {"ingredients": ("ingredients", "inci"), "channels": ("channels", "sales channels"), "packaging": ("packaging",), "positioning": ("positioning",), "pack_text": ("pack", "pack description")}.items():
                found = next((properties[name] for name in names if name in properties), None)
                fields.append(fact(source, field, found[0], found[1], marketing=field in {"packaging", "positioning"}) if found and found[0] is not None else unknown(field))
                extracted_props[field] = found[0] if found else None
            weight = node.get("weight")
            weight_value = weight.get("value") if isinstance(weight, dict) else None
            unit = weight.get("unitCode") if isinstance(weight, dict) else None
            grams = number(weight_value, positive=True) if unit in {"GRM", "g"} else None
            basis_raw = properties.get("weight basis")
            basis = basis_raw[0] if basis_raw and basis_raw[0] in {"per_bar", "total_pack"} else "unknown"
            qty_raw = node.get("numberOfItems")
            qty = qty_raw if isinstance(qty_raw, int) and not isinstance(qty_raw, bool) and qty_raw > 0 else None
            total = grams if grams is not None and basis == "total_pack" else grams * qty if grams is not None and qty is not None and basis == "per_bar" else None
            total = number(total, positive=True)
            fields.extend((fact(source, "weight_g", weight, pointer + "/weight", value=str(grams)) if grams is not None else unknown("weight_g", "missing_or_invalid_weight_unit"),
                fact(source, "pack_qty", qty_raw, pointer + "/numberOfItems") if qty is not None else unknown("pack_qty"),
                fact(source, "weight_basis", basis_raw[0], basis_raw[1]) if basis_raw and basis != "unknown" else unknown("weight_basis", "ambiguous_pack_weight")))
            offers = node.get("offers", [])
            if isinstance(offers, dict):
                offers = [offers]
            if not isinstance(offers, list) or not offers:
                offers = [{}]
            ingredients_raw = extracted_props["ingredients"]
            ingredients = tuple(item.strip() for item in ingredients_raw.split(",") if item.strip()) if isinstance(ingredients_raw, str) else tuple(ingredients_raw) if isinstance(ingredients_raw, list) and all(isinstance(i, str) for i in ingredients_raw) else None
            ingredients = ingredients or None
            reviews = node.get("review", [])
            reviews_single = isinstance(reviews, dict)
            if isinstance(reviews, dict):
                reviews = [reviews]
            if isinstance(reviews, list):
                for index, review in enumerate(reviews[:20]):
                    if isinstance(review, dict) and isinstance(review.get("reviewBody"), str):
                        fields.append(fact(source, "public_review", review["reviewBody"], pointer + "/review" + ("" if reviews_single else f"/{index}") + "/reviewBody", marketing=True))
            if not any(f.field == "public_review" for f in fields):
                fields.append(unknown("public_review"))
            for offer_index, offer in enumerate(offers[:10]):
                if not isinstance(offer, dict):
                    continue
                price = number(offer.get("price"))
                currency = offer.get("priceCurrency")
                currency = currency if isinstance(currency, str) and re.fullmatch("[A-Z]{3}", currency) else None
                offer_pointer = pointer + ("/offers" if isinstance(node.get("offers"), dict) else f"/offers/{offer_index}")
                # Preserve explicit listing status, never infer it from a failed fetch.
                availability = offer.get("availability")
                availability_fields = [fact(source, "availability", availability, offer_pointer + "/availability", marketing=True)] if availability in (
                    "InStock", "OutOfStock", "Discontinued", "https://schema.org/InStock", "https://schema.org/OutOfStock", "https://schema.org/Discontinued",
                    "http://schema.org/InStock", "http://schema.org/OutOfStock", "http://schema.org/Discontinued") else []
                item = offer.get("itemOffered")
                mismatched = isinstance(item, dict) and any(item.get(key) is not None and item[key] != node.get(key) for key in ("sku", "model", "@id"))
                if mismatched or offer.get("@type") == "AggregateOffer":
                    availability_fields = []
                if mismatched:
                    page_facts.append(fact(source, "unmatched_offer", offer, offer_pointer, marketing=True))
                    price = None
                    limitations.append("offer_item_mismatch")
                if offer.get("@type") == "AggregateOffer":
                    page_facts.append(fact(source, "price_range", offer, offer_pointer, marketing=True))
                offer_fields = [fact(source, "price", offer["price"], offer_pointer + "/price", value=str(price)) if price is not None else unknown("price", "missing_or_invalid_price"),
                    fact(source, "currency", currency, offer_pointer + "/priceCurrency") if currency else unknown("currency")]
                try:
                    products.append(ProductExtraction.model_validate(dict(source_id=source.source_id, locator=offer_pointer, name=node["name"],
                        sku=node.get("sku") if isinstance(node.get("sku"), str) and node["sku"].strip() else None, variant=node.get("model") if isinstance(node.get("model"), str) and node["model"].strip() else None,
                        amount=price, currency=currency, weight_g=grams, pack_qty=qty, weight_basis=basis, total_weight_g=total, ingredients=ingredients,
                        observations=tuple(fields + offer_fields + availability_fields))))
                except ValidationError:
                    limitations.append("invalid_product_numbers_unavailable")
        if "NewsArticle" in kinds or "Article" in kinds:
            article = node.get("articleBody", "")
            headline = node.get("headline", "")
            if not isinstance(article, str) or not re.search(r"(?<!\w)" + re.escape(competitor_name) + r"(?!\w)", str(headline) + " " + article, re.I):
                continue
            page_facts.append(fact(source, "news", article, pointer + "/articleBody", marketing=True))
            if isinstance(headline, str) and headline:
                page_facts.append(fact(source, "headline", headline, pointer + "/headline", marketing=True))
            if node.get("datePublished") is not None:
                page_facts.append(fact(source, "published_date", node["datePublished"], pointer + "/datePublished"))
            if re.search(r"\b(?:launch(?:ed|es)?|introduc(?:ed|es)|new product)\b", article, re.I):
                page_facts.append(fact(source, "reported_launch", article, pointer + "/articleBody", marketing=True))
    if not products and first_party:
        fallback = visible_product(source)
        if fallback:
            products.append(fallback)
    if not products:
        limitations.append("no_supported_structured_product")
    if not page_facts:
        page_facts.append(unknown("news_or_launch"))
    return PageExtraction(source_id=source.source_id, products=tuple(products), observations=tuple(page_facts), limitations=tuple(dict.fromkeys(limitations)))


def visible_product(source: RetrievedSource) -> ProductExtraction | None:
    parsed = HTML(source.body or "")
    labels = parsed.labels
    if not parsed.h1 or not any(key in labels for key in ("sku", "price", "price amount")):
        return None
    def observed(field, label, value=None, marketing=False):
        raw = parsed.h1 if label == "h1" else labels.get(label)
        if not raw or not source.excerpt or raw not in source.excerpt:
            return unknown(field)
        return Observation(field=field, value=raw if value is None else value, kind="competitor_marketing_claim" if marketing else "fact",
            evidence=(Evidence(source_id=source.source_id, quote=raw, quote_hash=sha256(raw.encode()).hexdigest(), locator="text:" + label),))
    raw_price = labels.get("price amount") or labels.get("price", "")
    match = re.fullmatch(r"(?:([A-Z]{3})\s+)?([0-9]+(?:\.[0-9]{1,4})?)", raw_price)
    price = number(match[2]) if match else None
    currency = labels.get("currency") or (match[1] if match else None)
    currency = currency if currency and re.fullmatch("[A-Z]{3}", currency) else None
    raw_weight = labels.get("weight", "")
    weight_match = re.fullmatch(r"([0-9]+(?:\.[0-9]{1,4})?)\s*(g|kg)", raw_weight)
    grams = number(Decimal(weight_match[1]) * (1000 if weight_match[2] == "kg" else 1), positive=True) if weight_match else None
    raw_qty = labels.get("pack quantity", "")
    qty = int(raw_qty) if raw_qty.isdigit() and int(raw_qty) > 0 else None
    basis = labels.get("weight basis", "unknown").replace(" ", "_")
    basis = basis if basis in {"per_bar", "total_pack"} else "unknown"
    total = number(grams if basis == "total_pack" else grams * qty if basis == "per_bar" and grams is not None and qty is not None else None, positive=True)
    fields = [observed("product", "h1"), observed("sku", "sku"), observed("variant", "variant"), observed("product_type", "product type"),
        observed("ingredients", "ingredients"), observed("marketing_claim", "claims", marketing=True), observed("channels", "channels"),
        observed("public_review", "reviews", marketing=True), observed("packaging", "packaging", marketing=True), observed("positioning", "positioning", marketing=True),
        observed("audience", "audience"), observed("reported_launch", "launch", marketing=True)]
    fields.extend([observed("price", "price amount" if "price amount" in labels else "price", str(price)) if price is not None else unknown("price"),
        observed("currency", "currency") if "currency" in labels and currency else observed("currency", "price", currency) if currency else unknown("currency"),
        observed("weight_g", "weight", str(grams)) if grams is not None else unknown("weight_g"),
        observed("pack_qty", "pack quantity", qty) if qty is not None else unknown("pack_qty"),
        observed("weight_basis", "weight basis", basis) if basis != "unknown" else unknown("weight_basis", "ambiguous_pack_weight")])
    ingredients = tuple(item.strip() for item in labels["ingredients"].split(",") if item.strip()) if "ingredients" in labels else None
    ingredients = ingredients or None
    return ProductExtraction.model_validate(dict(source_id=source.source_id, locator="text:h1", name=parsed.h1, sku=labels.get("sku") or None, variant=labels.get("variant") or None,
        amount=price, currency=currency, weight_g=grams, pack_qty=qty, weight_basis=basis, total_weight_g=total, ingredients=ingredients, observations=tuple(fields)))


def contradictions(pages: tuple[PageExtraction, ...]) -> tuple[JsonValue, ...]:
    groups: dict[tuple, list] = {}
    for page in pages:
        for product in page.products:
            if product.sku is not None:
                groups.setdefault((product.sku, product.variant, product.pack_qty, product.currency), []).append(product)
    conflicts = []
    for key, values in groups.items():
        for field in ("amount", "weight_g", "ingredients"):
            known = [value for value in values if getattr(value, field) is not None]
            if len({canonical(getattr(value, field)) for value in known}) > 1:
                conflicts.append({"sku": key[0], "variant": key[1], "pack_qty": key[2], "currency": key[3], "field": field,
                    "observations": [{"source_id": str(value.source_id), "locator": value.locator, "value": json.loads(canonical(getattr(value, field)))} for value in known]})
    return tuple(conflicts)
