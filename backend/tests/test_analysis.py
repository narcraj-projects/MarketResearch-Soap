"""AN01+: normalization, grounded comparisons and independent review trajectories."""
from decimal import Decimal
from pathlib import Path
import json

import pytest
from pydantic import ValidationError

from app.agents.analyst import analyze
from app.agents.correction import correct
from app.agents.normalization import normalize_price
from app.agents.reviewer import review, review_payload
from app.harness.analysis_types import AnalysisDraft, EvidencePack
from app.harness.policy import PolicyDenied
from app.repository import digest
from tests.analysis_support import evidence_pack

FOLDER = Path(__file__).resolve().parents[1] / "evaluations/fixtures/analysis-v1"


@pytest.mark.parametrize("case", json.loads((FOLDER / "cases.json").read_text())["cases"], ids=lambda c: c["id"])
def test_an01_golden_cases(case):
    pack = evidence_pack(case["mode"], age_days=case.get("age_days", 0))
    draft = analyze(pack)
    expected = case["expected"]
    if "first_unit" in expected:
        actual = draft.normalized_prices[0].unit_price_100g
        assert actual == (Decimal(expected["first_unit"]) if expected["first_unit"] is not None else None)
    if "opportunities" in expected:
        assert len(draft.opportunities) == expected["opportunities"]
    if "price_groups" in expected:
        assert len(draft.price_comparisons) == expected["price_groups"]
    if "conflicts" in expected:
        assert len(draft.conflicts) == expected["conflicts"]
    attack = case.get("attack")
    if attack == "arithmetic":
        row = next(p for p in draft.normalized_prices if p.unit_price_100g is not None)
        changed = row.model_copy(update={"unit_price_100g": Decimal("999")})
        draft = draft.model_copy(update={"normalized_prices": tuple(changed if p == row else p for p in draft.normalized_prices)})
    elif attack == "medical_fact":
        row = next(f for f in draft.findings if f.kind == "source_claim" and "cures eczema" in str(f.value))
        changed = row.model_copy(update={"kind": "fact", "caveat": None})
        draft = draft.model_copy(update={"findings": tuple(changed if f == row else f for f in draft.findings)})
    elif attack == "irrelevant_citation":
        row = next(f for f in draft.findings if f.field == "price" and f.value is not None)
        changed = row.model_copy(update={"text": "This soap has proven clinical efficacy", "value": "DEMO invented result with a real intact citation"})
        draft = draft.model_copy(update={"findings": tuple(changed if f == row else f for f in draft.findings)})
    elif attack == "binding":
        draft = draft.model_copy(update={"input_hash": "a" * 64})
    if attack == "malformed":
        assessment = review_payload(pack, draft.model_dump(mode="json") | {"opportunities": "DEMO-not-a-list"})
    else:
        assessment = review(pack, draft, revisions_remaining=case.get("revisions_remaining", True))
    assert assessment.decision == expected["review"]
    assert assessment.genuine_support_coverage is None and assessment.semantic_support == "not_adjudicated"
    if expected.get("issue"):
        assert expected["issue"] in {i.code for i in assessment.issues}
    if assessment.decision == "revise":
        repaired, targets = correct(pack, draft, assessment)
        assert targets and review(pack, repaired, revisions_remaining=False).decision == "ready_for_human"


def test_an02_targeted_correction_preserves_every_unaffected_section():
    pack = evidence_pack()
    original = analyze(pack)
    price = next(p for p in original.normalized_prices if p.unit_price_100g is not None)
    bad = original.model_copy(update={"normalized_prices": tuple(p.model_copy(update={"unit_price_100g": Decimal(999)}) if p == price else p for p in original.normalized_prices)})
    assessment = review(pack, bad)
    fixed, targets = correct(pack, bad, assessment)
    assert targets == ("price:" + str(price.observation_id),)
    assert fixed.findings == bad.findings and fixed.opportunities == bad.opportunities and fixed.comparisons == bad.comparisons
    assert fixed.normalized_prices == tuple(sorted(original.normalized_prices, key=lambda p: str(p.observation_id)))


def test_an03_reviewer_does_not_call_or_accept_analyst_support_scores(monkeypatch):
    pack = evidence_pack()
    draft = analyze(pack)
    monkeypatch.setattr("app.agents.analyst.analyze", lambda _: (_ for _ in ()).throw(AssertionError("analyst must not grade itself")))
    assert review(pack, draft).decision == "ready_for_human"
    with pytest.raises(ValidationError):
        AnalysisDraft.model_validate(draft.model_dump() | {"support_status": "supported"})


def test_an04_citation_presence_is_not_entailment():
    pack = evidence_pack()
    draft = analyze(pack)
    finding = next(f for f in draft.findings if f.field == "price" and f.value is not None)
    invalid = finding.model_copy(update={"text": "DEMO unrelated certification proved", "value": "certified organic"})
    changed = draft.model_copy(update={"findings": tuple(invalid if f == finding else f for f in draft.findings)})
    result = review(pack, changed)
    assert result.citation_presence == result.quote_integrity == 1
    assert result.decision == "revise" and result.genuine_support_coverage is None


def test_an05_mismatched_source_variant_pack_and_tampered_evidence():
    pack = evidence_pack("pack")
    source, product = pack.research[0].sources[0], pack.research[0].pages[0].products[0]
    for changes in ({"variant": "DEMO another variant"}, {"total_weight_g": Decimal(200)}, {"pack_qty": 3}, {"amount": Decimal(24)}):
        assert normalize_price(pack.competitors[0].competitor_id, product.model_copy(update=changes), source).unit_price_100g is None
    assert normalize_price(pack.competitors[1].competitor_id, product, pack.research[1].sources[0]).unit_price_100g is None
    lane = pack.research[0].model_copy(update={"pages": (pack.research[0].pages[0].model_copy(update={"products": (product.model_copy(update={"amount": Decimal(1)}),)}),)})
    bad_pack = EvidencePack.model_validate(pack.model_dump() | {"research": (lane,) + pack.research[1:]})
    with pytest.raises(PolicyDenied, match="extraction_snapshot_mismatch"):
        analyze(bad_pack)


def test_an06_wrong_review_binding_and_missing_fields_do_not_get_auto_pass():
    pack, other = evidence_pack(), evidence_pack("medical")
    draft = analyze(pack)
    with pytest.raises(PolicyDenied, match="correction_review_binding"):
        correct(pack, draft, review(other, analyze(other)))
    removed = draft.model_copy(update={"findings": draft.findings[1:]})
    assert "missing_observation" in {i.code for i in review(pack, removed).issues}
    fixed, _ = correct(pack, removed, review(pack, removed))
    assert review(pack, fixed).decision == "ready_for_human"


@pytest.mark.parametrize("patch", [{"schema_version": "future"}, {"as_of": "2026-10-25T00:00:00"}, {"run_id": "bad"}])
def test_an07_pack_validation(patch):
    with pytest.raises(ValidationError):
        EvidencePack.model_validate(evidence_pack().model_dump() | patch)


def test_an08_deterministic_output_and_fixture_hashes():
    from hashlib import sha256
    manifest = json.loads((FOLDER / "manifest.json").read_text())
    assert manifest["sha256"]["cases.json"] == sha256((FOLDER / "cases.json").read_bytes()).hexdigest()
    pack = evidence_pack()
    assert digest(analyze(pack).model_dump(mode="json")) == digest(analyze(pack).model_dump(mode="json"))
    assert {f.kind for f in analyze(pack).findings} == {"fact", "source_claim", "interpretation"}
    assert all(o.kind == "hypothesis" and o.assumptions and o.next_step and o.evidence_finding_ids for o in analyze(pack).opportunities)


def test_an09_normalized_evidence_and_opportunity_narrative_cannot_bypass_review():
    pack = evidence_pack()
    draft = analyze(pack)
    row = draft.normalized_prices[0]
    forged = row.model_copy(update={"evidence": draft.normalized_prices[1].evidence})
    opportunity = draft.opportunities[0].model_copy(update={"potential_benefit": "DEMO promise to cure eczema"})
    bad = draft.model_copy(update={"normalized_prices": (forged,) + draft.normalized_prices[1:], "opportunities": (opportunity,) + draft.opportunities[1:]})
    result = review(pack, bad)
    assert {"normalization_provenance", "unsupported_opportunity"}.issubset({i.code for i in result.issues})
    fixed, _ = correct(pack, bad, result)
    assert review(pack, fixed).decision == "ready_for_human"


def test_an10_future_dates_are_not_used_as_current_price_or_opportunity_evidence():
    from datetime import timedelta
    pack = evidence_pack()
    lanes = tuple(lane.model_copy(update={"sources": tuple(s.model_copy(update={"retrieved_at": pack.as_of + timedelta(days=1)}) for s in lane.sources)}) for lane in pack.research)
    future = EvidencePack.model_validate(pack.model_dump() | {"research": lanes})
    draft = analyze(future)
    assert not draft.price_comparisons and not draft.opportunities
    assert "source_freshness" in {i.code for i in review(future, draft).issues}
