"""Synthetic boundary cases, no network. LIVE tag exercises the live-only parser."""

from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

from app.agents.snippet_extraction import eligible, extract_snippet
from app.harness.research_types import RetrievedSource


def source(text, url="https://maker.invalid/product-page/DEMO-soap", label="LIVE"):
    return RetrievedSource(
        label=label,
        source_id=uuid4(),
        competitor_id=uuid4(),
        canonical_url=url,
        requested_url=url,
        retrieved_at=datetime.now(timezone.utc),
        title="DEMO soap",
        publisher="maker.invalid",
        access_status="ok",
        evidence_kind="search_snippet",
        content_hash=sha256(text.encode()).hexdigest(),
        text_hash=sha256(text.encode()).hexdigest(),
        body=text,
        excerpt=text,
    )


def test_single_price_is_attributed_without_sku_normalization():
    row = source("DEMO soap\nPrice ₹275.00\nWeight: 115 g")
    parsed = extract_snippet(row)
    assert eligible(row, True) and not parsed.products
    fields = {o.field: o for o in parsed.observations}
    assert fields["price"].value == "275.00" and fields["weight_g"].value is None
    assert fields["price"].kind == "competitor_marketing_claim"
    assert all(e.quote in row.excerpt for o in parsed.observations for e in o.evidence)


def test_multiple_prices_remain_ambiguous():
    parsed = extract_snippet(source("DEMO soap ₹275 and another soap ₹300"))
    assert not any(o.field == "price" for o in parsed.observations)
    assert "ambiguous_price" in parsed.limitations


def test_third_party_blog_and_demo_cannot_enter_live_listing_parser():
    assert not eligible(source("DEMO soap"), False)
    assert not eligible(
        source("DEMO soap", url="https://maker.invalid/blog/soap.html"), True
    )
    assert not eligible(source("DEMO soap", label="DEMO"), True)
