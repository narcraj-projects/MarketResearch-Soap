"""Conservative listing observations from first-party LIVE search snippets.

Search text remains search text. No synthetic HTML, SKU, weight, or pack is made.
"""

import re
from hashlib import sha256
from urllib.parse import urlsplit

from app.harness.research_types import Evidence, Observation, PageExtraction


def eligible(source, first_party):
    path = urlsplit(source.canonical_url).path.lower()
    return (
        source.label == "LIVE"
        and source.evidence_kind == "search_snippet"
        and source.access_status == "ok"
        and first_party
        and bool(re.search(r"/products?/|/product-page/|soap.*\.html$", path))
        and not re.search(r"/blogs?/|/collections?/", path)
    )


def extract_snippet(source):
    text = source.excerpt or ""

    def observed(field, value, quote):
        return Observation(
            field=field,
            value=value,
            kind="competitor_marketing_claim",
            evidence=(
                Evidence(
                    source_id=source.source_id,
                    quote=quote,
                    quote_hash=sha256(quote.encode()).hexdigest(),
                    locator="search:verbatim",
                ),
            ),
        )

    observations = []
    # The description is explicitly a listing excerpt, never a manufactured SKU.
    description = next(
        (line.strip() for line in text.splitlines() if "soap" in line.lower()), None
    )
    if description:
        observations.append(observed("product", description[:500], description[:500]))
    prices = list(
        re.finditer(
            r"(?:₹|\bINR\s*|\bRs\.?\s*)([0-9][0-9,]*(?:\.[0-9]{1,2})?)", text, re.I
        )
    )
    unique = {match[1].replace(",", "") for match in prices}
    if len(unique) == 1:
        match = prices[0]
        observations.extend(
            (
                observed("price", match[1].replace(",", ""), match[0]),
                observed("currency", "INR", match[0]),
            )
        )
    observations.extend(
        Observation(
            field=field,
            value=None,
            unavailable_reason="search_snippet_not_sku_verified",
        )
        for field in ("sku", "weight_g", "pack_qty", "ingredients")
    )
    if text:
        observations.append(observed("marketing_claim", text[:900], text[:900]))
    return PageExtraction(
        source_id=source.source_id,
        products=(),
        observations=tuple(observations),
        limitations=(
            "search_snippet_only_not_full_page",
            "no_sku_bound_normalization",
            "ambiguous_price" if len(unique) > 1 else "product_details_incomplete",
        ),
    )
