"""Synthetic DEMO evidence builder using the existing manifest-verified product recording."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from uuid import UUID, uuid5

from app.adapters.public_web import RecordedWeb
from app.agents.extraction import extract, parse_html
from app.harness.analysis_types import Competitor, EvidencePack
from app.harness.research_types import CompetitorResearch, RetrievedSource
from tests.research_support import FOLDER

AS_OF = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)


def evidence_pack(mode="rich", *, age_days=0):
    base = RecordedWeb(FOLDER / "R01-complete.json").case
    original = base["responses"]["GET https://demo-a.invalid/soap"][0]["reply"]["body"]
    template = parse_html(original, "https://demo-a.invalid/soap")[2][0]
    competitors, research = [], []
    for ordinal, letter in enumerate("ABC"):
        cid = UUID(int=101 + ordinal)
        name, url = f"DEMO Maker {letter}", f"https://demo-{letter.lower()}.invalid/soap"
        competitors.append(Competitor(competitor_id=cid, name=name, canonical_url=url))
        node = deepcopy(template)
        node["name"], node["brand"], node["sku"] = f"DEMO {letter} soap bar", {"name": name}, f"DEMO-{letter}-100"
        node["offers"]["price"] = str((120, 150, 210)[ordinal])
        for prop in node["additionalProperty"]:
            if prop["name"] == "Positioning":
                prop["value"] = ("DEMO ingredient-led", "DEMO gifting-led", "DEMO minimal packaging")[ordinal]
            if prop["name"] == "Ingredients":
                prop["value"] = None if ordinal == 1 else ("DEMO olive oil, water" if ordinal == 0 else "DEMO coconut oil, water")
        if mode == "rich" and ordinal == 1:
            node.pop("weight")
        if mode == "pack" and ordinal == 0:
            node["numberOfItems"], node["weight"]["value"], node["offers"]["price"] = 2, "80", "240"
            node["additionalProperty"][0]["value"] = "per_bar"
        if mode in {"rounding", "zero"} and ordinal == 0:
            node["offers"]["price"] = "1" if mode == "rounding" else "0"
            node["weight"]["value"] = "20000000000" if mode == "rounding" else "100"
        if mode == "no_sku" and ordinal == 0:
            node.pop("sku")
        if mode == "ambiguous" and ordinal == 0:
            node["additionalProperty"][0]["value"] = "unknown"
        if mode == "wrong_offer" and ordinal == 0:
            node["offers"]["itemOffered"] = {"sku": "DEMO-different-purchase-item"}
        if mode == "currency":
            node["offers"]["priceCurrency"] = ("INR", "USD", "EUR")[ordinal]
        if mode == "medical" and ordinal == 0:
            node["description"] = "DEMO marketing claims this bar cures eczema. Unverified advertising fixture."
        sources, pages = [], []
        variants = [node, deepcopy(node)] if mode == "conflict" and ordinal == 0 else [node]
        if len(variants) == 2:
            variants[1]["offers"]["price"] = "140"
        for index, value in enumerate(variants):
            page_url = url if index == 0 else url + "-later"
            body = '<html><title>DEMO listing</title><script type="application/ld+json">' + json.dumps(value) + '</script><body>DEMO synthetic evidence</body></html>'
            if mode == "empty":
                body = "<html><title>DEMO unavailable detail</title><body>No structured product supplied in this DEMO fixture.</body></html>"
            title, excerpt, structured, links, _ = parse_html(body, page_url)
            source = RetrievedSource(source_id=uuid5(cid, page_url), competitor_id=cid, canonical_url=page_url, requested_url=page_url,
                retrieved_at=AS_OF - timedelta(days=age_days + index), title=title, publisher=f"demo-{letter.lower()}.invalid",
                access_status="ok", evidence_kind="page_excerpt", body=body, excerpt=excerpt, structured=structured, links=links,
                content_hash=sha256(body.encode()).hexdigest(), text_hash=sha256(excerpt.encode()).hexdigest())
            sources.append(source)
            pages.append(extract(source, name, first_party=True))
        research.append(CompetitorResearch(competitor_id=cid, state="complete", sources=tuple(sources), pages=tuple(pages)))
    return EvidencePack(run_id=UUID(int=800), as_of=AS_OF, competitors=tuple(competitors), research=tuple(research))
