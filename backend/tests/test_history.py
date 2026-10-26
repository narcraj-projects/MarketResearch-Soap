"""History golden cases exercise dated raw evidence with no network or model calls."""
from hashlib import sha256
import json
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException
import pytest

from app.history import compare, stable_brand, stable_product
from tests.history_support import history_document

FOLDER = Path(__file__).parents[1] / "evaluations/fixtures/history-v1"
CASES = json.loads((FOLDER / "cases.json").read_text())


@pytest.mark.parametrize("case", CASES["cases"], ids=lambda c: c["id"])
def test_history_golden(case):
    old, old_meta = history_document(case.get("before_mode", "same"))
    new, new_meta = history_document(case["mode"], later=True)
    value = compare(old, new, old_meta, new_meta)
    affected = [row for row in value.changes if row.brand == "DEMO Maker A" and row.field == case["field"]]
    assert case["expected"] in {row.status for row in affected}
    assert value.counts["gone"] == case.get("gone", 0)
    assert value == compare(old, new, old_meta, new_meta)  # no wall clock, new sources or writes
    assert sum(value.counts.values()) == len(value.changes)
    if case["mode"] == "price":
        price = next(row for row in affected if row.status == "changed")
        assert price.before.values[0]["amount"] == "120" and price.after.values[0]["amount"] == "140"
        assert price.before.evidence[0].source.retrieved_at < price.after.evidence[0].source.retrieved_at
    if case["mode"] == "unavailable":
        assert any(ref.source.access_status == "unavailable" for row in affected for ref in row.after.evidence)
        assert not value.counts["gone"]


def test_hv14_stable_identity_changes_local_ids_and_preserves_source_sku_case():
    old, om = history_document()
    new, nm = history_document(later=True)
    assert old.snapshot.analysis.comparisons[0].competitor_id != new.snapshot.analysis.comparisons[0].competitor_id
    assert compare(old, new, om, nm).counts["changed"] == 0
    bid, _ = stable_brand("DEMO Maker A", "https://www.demo-a.invalid/a?utm_source=demo")
    assert bid == stable_brand(" demo MAKER A ", "http://demo-a.invalid/b")[0]
    assert bid != stable_brand("DEMO Other Maker", "https://demo-a.invalid/")[0]
    assert stable_product(bid, "sku", None) != stable_product(bid, "SKU", None)
    assert stable_product(bid, "sku", "rose") != stable_product(bid, "sku", "lime")


def test_hv15_identity_unknowns_and_rebrands_never_become_gone_or_launches():
    old, om = history_document()
    for mode in ("no_sku", "rebrand"):
        new, nm = history_document(mode, later=True)
        result = compare(old, new, om, nm)
        assert result.counts["gone"] == result.counts["new"] == 0
        assert result.counts["unknown"] > 0


def test_hv16_gate_scope_and_time_checks():
    old, om = history_document()
    new, nm = history_document(later=True)
    with pytest.raises(HTTPException, match="distinct_chronological"):
        compare(new, old, nm, om)
    with pytest.raises(HTTPException, match="distinct_chronological"):
        compare(old, old, om, om)
    with pytest.raises(HTTPException, match="approved_saved"):
        compare(old, new.model_copy(update={"export_allowed": False}), om, nm)
    changed = new.snapshot.model_copy(update={"brief": new.snapshot.brief.model_copy(update={"geography": "DEMO elsewhere"})})
    with pytest.raises(HTTPException, match="incompatible_research_scope"):
        compare(old, new.model_copy(update={"snapshot": changed}), om, nm)


def test_hv17_fixture_manifest_and_immutable_inputs():
    manifest = json.loads((FOLDER / "manifest.json").read_text())
    for name, expected in manifest["sha256"].items():
        assert sha256((FOLDER / name).read_bytes()).hexdigest() == expected
    old, om = history_document()
    new, nm = history_document("price", later=True)
    original = old.model_dump_json(), new.model_dump_json()
    compare(old, new, om, nm)
    assert original == (old.model_dump_json(), new.model_dump_json())
    with pytest.raises(Exception):
        old.version = 99


def test_hv18_different_pack_currency_conflicts_and_missing_sku_never_zero_or_false_match():
    old, om = history_document()
    for mode in ("pack", "currency", "conflict", "no_sku"):
        new, nm = history_document(mode, later=True, run_id=UUID(int=9300))
        result = compare(old, new, om, nm)
        assert not any(row.field == "price" and row.brand == "DEMO Maker A" and row.status in {"changed", "gone", "new"} for row in result.changes)


def test_hv23_different_listing_context_cannot_masquerade_as_a_price_increase():
    old, om = history_document()
    new, nm = history_document("price", later=True)
    cid = new.snapshot.analysis.comparisons[0].competitor_id
    # A legitimate alternate listing must not be treated as the same observed offer.
    sources = tuple(source.model_copy(update={"canonical_url": "https://demo-other-store.invalid/soap"}) if source.competitor_id == cid else source for source in new.snapshot.sources)
    new = new.model_copy(update={"snapshot": new.snapshot.model_copy(update={"sources": sources})})
    result = compare(old, new, om, nm)
    row = next(row for row in result.changes if row.field == "price" and row.brand == "DEMO Maker A")
    assert row.status == "unknown" and row.reason == "source_or_offer_context_changed"
    assert row.before.values[0]["amount"] == "120" and row.after.values[0]["amount"] == "140"
