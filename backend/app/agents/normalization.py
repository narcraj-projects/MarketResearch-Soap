"""Same purchase-item arithmetic. No cross-source joins, inferred packs or implicit FX."""
from decimal import Decimal, ROUND_HALF_UP, localcontext
from hashlib import sha256
from uuid import UUID, uuid5
from typing import Any

from app.harness.analysis_types import NormalizedPrice
from app.harness.research_types import ProductExtraction, RetrievedSource


def same_item_binding(product: ProductExtraction, source: RetrievedSource) -> bool:
    """Check the purchase item against the raw page, not just a quoted number."""
    from app.agents.extraction import canonical, parse_html, visible_product
    try:
        _, excerpt, structured, _, restricted = parse_html(source.body or "", source.canonical_url)
        if restricted or excerpt != source.excerpt or structured != source.structured:
            return False
        if product.locator == "text:h1":
            return visible_product(source) == product
        def pointer(path):
            value: Any = structured
            for token in path.strip("/").split("/"):
                token = token.replace("~1", "/").replace("~0", "~")
                value = value[int(token)] if isinstance(value, (list, tuple)) else value[token]
            return value
        parent_path = product.locator.split("/offers", 1)[0]
        parent, offer = pointer(parent_path), pointer(product.locator)
        if not isinstance(parent, dict) or not isinstance(offer, dict) or offer.get("@type") == "AggregateOffer" or "eligibleQuantity" in offer:
            return False
        if parent.get("sku") != product.sku or parent.get("model") != product.variant:
            return False
        item = offer.get("itemOffered")
        if item is not None and (not isinstance(item, dict) or any(item.get(k) is not None and item[k] != parent.get(k) for k in ("sku", "model", "@id", "numberOfItems", "weight"))):
            return False
        if Decimal(str(offer.get("price"))) != product.amount or offer.get("priceCurrency") != product.currency:
            return False
        weight = parent.get("weight", {})
        if weight.get("unitCode") not in {"GRM", "g"} or Decimal(str(weight.get("value"))) != product.weight_g:
            return False
        if parent.get("numberOfItems") != product.pack_qty:
            return False
        props = parent.get("additionalProperty", [])
        props = [props] if isinstance(props, dict) else props
        if not any(isinstance(prop, dict) and str(prop.get("name")).casefold() == "weight basis" and prop.get("value") == product.weight_basis for prop in props):
            return False
        for observation in product.observations:
            for evidence in observation.evidence:
                if evidence.source_id != source.source_id or evidence.quote_hash != sha256(evidence.quote.encode()).hexdigest() or evidence.quote not in excerpt:
                    return False
                if not evidence.locator.startswith("json:") or canonical(pointer(evidence.locator[5:])) != evidence.quote:
                    return False
                if not evidence.locator[5:].startswith(parent_path + "/"):
                    return False
        return True
    except (ValueError, TypeError, KeyError, IndexError, ArithmeticError, AttributeError):
        return False


def normalize_price(cid: UUID, product: ProductExtraction, source: RetrievedSource) -> NormalizedPrice:
    fields = {o.field: o for o in product.observations if o.value is not None}
    needed = {"sku", "price", "currency", "weight_g", "weight_basis"}
    if product.weight_basis == "per_bar":
        needed.add("pack_qty")
    evidence = tuple(e for key in sorted(needed) if key in fields for e in fields[key].evidence)
    reason = None
    total = None
    if source.source_id != product.source_id or source.competitor_id != cid or source.access_status != "ok" or source.evidence_kind != "page_excerpt":
        reason = "source_item_mismatch"
    elif product.sku is None or not product.sku.strip():
        reason = "sku_unavailable"
    elif product.amount is None or product.currency is None:
        reason = "price_or_currency_unavailable"
    elif product.weight_g is None or product.weight_basis == "unknown":
        reason = "weight_or_pack_basis_unavailable"
    elif product.weight_basis == "per_bar" and product.pack_qty is None:
        reason = "pack_quantity_unavailable"
    elif not needed.issubset(fields) or any(e.source_id != source.source_id for e in evidence):
        reason = "same_item_evidence_unavailable"
    elif not same_item_binding(product, source):
        reason = "purchase_item_scope_mismatch"
    else:
        # Bind typed values to the extraction observations before using their arithmetic.
        expected: dict[str, object] = {"sku": product.sku, "price": str(product.amount), "currency": product.currency,
            "weight_g": str(product.weight_g), "weight_basis": product.weight_basis}
        if product.weight_basis == "per_bar":
            expected["pack_qty"] = product.pack_qty
        if any(str(fields[key].value) != str(value) for key, value in expected.items()):
            reason = "extracted_value_mismatch"
        else:
            with localcontext() as context:
                context.prec = 60
                total = product.weight_g if product.weight_basis == "total_pack" else product.weight_g * (product.pack_qty or 1)
            if total != product.total_weight_g:
                reason = "pack_total_mismatch"
                total = None
    unit = None
    if reason is None and total is not None and product.amount is not None:
        with localcontext() as context:
            context.prec = 60
            unit = (product.amount * Decimal(100) / total).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
            if unit >= Decimal("10000000000000000"):
                unit, total, reason = None, None, "normalized_value_out_of_storage_range"
    return NormalizedPrice(observation_id=uuid5(cid, f"price:{source.source_id}:{product.locator}"), competitor_id=cid,
        source_id=source.source_id, locator=product.locator, sku=product.sku, variant=product.variant, amount=product.amount,
        currency=product.currency, pack_qty=product.pack_qty, total_weight_g=total, unit_price_100g=unit,
        observed_at=source.retrieved_at, evidence=evidence, unavailable_reason=reason)
