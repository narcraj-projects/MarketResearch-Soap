"""Report presentation/export controls; synthetic evidence only, no network."""
import csv
from io import StringIO
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.agents.analyst import analyze
from app.agents.reviewer import review
from app.harness.analysis_types import Finding
from app.reporting import citation_coverage, positions, safe_link, snapshot
from app.report_exports import csv_text, export_report
from app.report_types import ApprovalView, ReportView
from tests.analysis_support import AS_OF, evidence_pack


def example(mode="rich", saved=True):
    pack = evidence_pack(mode)
    analysis = analyze(pack)
    rows = [{"id": source.source_id, "competitor_id": lane.competitor_id, **{key: getattr(source, key) for key in ("canonical_url", "title", "publisher", "retrieved_at", "content_hash", "access_status", "evidence_kind", "excerpt")}} for lane in pack.research for source in lane.sources]
    brief = {"id": uuid4(), "owner_id": uuid4(), "created_at": AS_OF, "version": 1, "category": "DEMO handmade soap", "geography": "DEMO India", "customer": "DEMO buyer", "objective": '<script>alert("DEMO")</script>', "known_competitors": [], "preferences": {}}
    document = snapshot(brief, analysis, rows)
    result = ReportView(id=uuid4(), version=1, content_hash="a" * 64, created_at=AS_OF, snapshot=document,
        review=review(pack, analysis), approval=ApprovalView(state="saved" if saved else "pending", artifact_hash="a" * 64, artifact_version=1), export_allowed=saved, projection="persisted")
    return result, rows


def test_r01_correct_denominator_keeps_uncited_and_unsupported_assertions():
    view, rows = example()
    analysis = view.snapshot.analysis
    initial = citation_coverage(analysis, {row["id"]: row for row in rows})
    unsupported = Finding(finding_id=uuid4(), competitor_id=analysis.comparisons[0].competitor_id, field="unsupported", value="DEMO invented assertion",
        kind="fact", text="DEMO attack", premise_ids=(analysis.findings[0].finding_id,))
    changed = analysis.model_copy(update={"findings": analysis.findings + (unsupported,)})
    result = citation_coverage(changed, {row["id"]: row for row in rows})
    assert result.material_facts == initial.material_facts + 1
    assert result.intact_quotes == initial.intact_quotes and result.quote_coverage < initial.quote_coverage
    assert result.genuine_support_coverage is None
    factual = next(f for f in analysis.findings if f.kind == "fact" and f.value is not None)
    irrelevant = factual.model_copy(update={"text": "DEMO unrelated efficacy assertion"})
    changed = analysis.model_copy(update={"findings": tuple(irrelevant if f == factual else f for f in analysis.findings)})
    assert citation_coverage(changed, {row["id"]: row for row in rows}).quote_coverage == initial.quote_coverage  # diagnostics, not entailment


def test_r02_empty_denominator_is_unavailable_and_completeness_is_separate():
    view, _ = example("empty")
    metrics = view.snapshot.coverage
    assert metrics.material_facts == 0 and metrics.citation_presence is None and metrics.quote_coverage is None
    assert metrics.populated_fields == 0 and metrics.unavailable_fields == metrics.comparison_fields == 27


def test_r03_cross_competitor_or_missing_sources_do_not_earn_intact_quote_credit():
    view, rows = example()
    assert citation_coverage(view.snapshot.analysis, {}).intact_quotes == 0
    invalid = {row["id"]: row | {"competitor_id": UUID(int=9999)} for row in rows}
    assert citation_coverage(view.snapshot.analysis, invalid).intact_quotes == 0


def test_r04_unknown_position_axes_are_not_inferred_from_price():
    view, _ = example()
    points = positions(view.snapshot.analysis)
    assert points[0].y is None and points[1].y == "gifting"  # only explicit wording supplies this axis
    row = next(f for f in view.snapshot.analysis.findings if f.field == "positioning" and f.value is not None)
    changed = row.model_copy(update={"value": "DEMO ingredient-led everyday soap"})
    analysis = view.snapshot.analysis.model_copy(update={"findings": tuple(changed if f == row else f for f in view.snapshot.analysis.findings)})
    point = next(point for point in positions(analysis) if point.competitor_id == row.competitor_id)
    assert point.x == "ingredient_led" and point.y == "everyday" and row.finding_id in point.premise_ids


@pytest.mark.parametrize("format", ["html", "csv"])
def test_r05_draft_exports_are_denied(format):
    view, _ = example(saved=False)
    with pytest.raises(HTTPException, match="approved_saved_report_required"):
        export_report(view, format)


def test_r06_html_is_self_contained_escaped_and_traceable():
    view, _ = example()
    content = export_report(view, "html")
    assert '<script>alert' not in content and '&lt;script&gt;' in content
    assert 'default-src &#39;none&#39;' in content and '<script src=' not in content and '<link rel=' not in content
    for section in ("Executive summary", "Scope and methodology", "Source coverage", "Competitor comparison", "Price per 100g", "Opportunities", "Dated sources"):
        assert section in content
    assert view.content_hash in content and 'not adjudicated' in content and 'source-' in content
    assert content == export_report(view, "html")


@pytest.mark.parametrize("text", ['=HYPERLINK("https://example.invalid")', '+1+1', '-1+1', '@SUM(1)', '\t=1+1', '  =1+1'])
def test_r07_csv_formula_prefixes_are_neutralized(text):
    assert csv_text(text).startswith("'")


def test_r08_csv_contains_structured_values_and_explicit_missing():
    view, _ = example()
    rows = list(csv.DictReader(StringIO(export_report(view, "csv"))))
    assert {"cover", "coverage", "approval", "finding", "price", "opportunity", "positioning", "source", "issue", "limitation"}.issubset({row["section"] for row in rows})
    assert any(row["section"] == "price" and row["value"] == "unavailable" for row in rows)
    assert all(row["label"] == "DEMO" and row["content_hash"] == view.content_hash for row in rows)
    assert export_report(view, "csv") == export_report(view, "csv")


@pytest.mark.parametrize("value", ["javascript:alert(1)", "file:///private", "https://user:secret@example.invalid/", "https://example.invalid/\nscript", "https://example.invalid/\"onclick=bad"])
def test_r09_unsafe_source_links_are_not_clickable(value):
    assert safe_link(value) is None
