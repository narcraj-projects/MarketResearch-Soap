"""Deterministic comparison/opportunity baseline. No provider selection or external calls."""
from datetime import timedelta
from uuid import uuid5

from app.agents.analysis_policy import FIELD_GROUPS, RULES
from app.agents.evidence_catalog import catalog
from app.agents.extraction import contradictions
from app.agents.normalization import normalize_price
from app.harness.analysis_types import AnalysisDraft, Comparison, ComparisonField, EvidencePack, Finding, Opportunity, PriceComparison
from app.repository import digest


def fresh(finding: Finding, pack: EvidencePack) -> bool:
    sources = {s.source_id: s for lane in pack.research for s in lane.sources}
    ids = {e.source_id for e in finding.evidence} | ({finding.source_id} if finding.source_id else set())
    return bool(ids) and all(pack.as_of - timedelta(days=pack.freshness_days) <= sources[sid].retrieved_at <= pack.as_of for sid in ids)


def analyze(pack: EvidencePack) -> AnalysisDraft:
    findings = catalog(pack)
    prices = tuple(normalize_price(lane.competitor_id, product, next(s for s in lane.sources if s.source_id == page.source_id))
        for lane in pack.research for page in lane.pages for product in page.products)
    comparisons = tuple(Comparison(competitor_id=c.competitor_id, name=c.name, fields=tuple(
        ComparisonField(field=field, finding_ids=tuple(f.finding_id for f in findings if f.competitor_id == c.competitor_id and f.field in members),
            unavailable_reason=None if any(f.competitor_id == c.competitor_id and f.field in members and f.value is not None for f in findings) else "not_available_in_retrieved_evidence")
        for field, members in FIELD_GROUPS.items())) for c in pack.competitors)
    price_comparisons = []
    for currency in sorted({p.currency for p in prices if p.currency}):
        rows = [p for p in prices if p.currency == currency and p.unit_price_100g is not None and
            pack.as_of - timedelta(days=pack.freshness_days) <= p.observed_at <= pack.as_of]
        if len({p.competitor_id for p in rows}) >= 2:
            values = [p.unit_price_100g for p in rows if p.unit_price_100g is not None]
            price_comparisons.append(PriceComparison(currency=currency, observation_ids=tuple(p.observation_id for p in rows), minimum=min(values), maximum=max(values)))
    known = [f for f in findings if f.value is not None and fresh(f, pack)]
    opportunities = []
    for rule, (title, rationale, benefit, assumption, next_step) in RULES.items():
        field = {"price_testing": "price", "pack_clarity": "weight_g", "disclosure": "ingredients", "positioning_test": "positioning", "feedback_test": "public_review"}[rule]
        evidence = [f for f in findings if f.field == field and fresh(f, pack)]
        observed = [f for f in known if f.field == field]
        enough = len({f.competitor_id for f in observed}) >= 2
        if rule == "price_testing":
            enough = any(p.maximum > p.minimum for p in price_comparisons)
            valid = {(p.source_id, p.locator, p.competitor_id) for p in prices if p.unit_price_100g is not None}
            evidence = [f for f in evidence if f.value is not None and any((e.source_id, f.product_locator, f.competitor_id) in valid for e in f.evidence)]
        elif rule in {"pack_clarity", "disclosure"}:
            enough = bool(observed) and len({f.competitor_id for f in evidence}) >= 2 and (any(f.value is None for f in evidence) or len({str(f.value) for f in observed}) > 1)
        elif rule == "positioning_test":
            enough = enough and len({str(f.value) for f in observed}) >= 2
        if enough and evidence:
            opportunities.append(Opportunity(opportunity_id=uuid5(pack.run_id, "opportunity:" + rule), rule=rule, title=title,
                evidence_finding_ids=tuple(f.finding_id for f in evidence), rationale=rationale, potential_benefit=benefit,
                assumptions=(assumption,), next_step=next_step))
    interpretations = []
    for comparison in price_comparisons:
        premise = tuple(f.finding_id for f in known if f.field == "price" and any(p.currency == comparison.currency and
            p.locator == f.product_locator and p.competitor_id == f.competitor_id for p in prices if p.unit_price_100g is not None))
        if premise:
            interpretations.append(Finding(finding_id=uuid5(pack.run_id, "interpretation:price:" + comparison.currency),
                competitor_id=next(c.competitor_id for c in pack.competitors), field="sample_price_comparison", value=comparison.currency,
                kind="interpretation", text=comparison.caveat, premise_ids=premise, caveat="No inference about market share, demand or product equivalence."))
    limits = ("DEMO recorded evidence only; no live model selected or evaluated." if pack.label == "DEMO" else "LIVE retrieved evidence; provisional model configuration, no completed quality benchmark.", "Ingredients are disclosed lists, not assumed complete.",
        "Public feedback is source-reported, may be biased and is not representative.", "Retrieval time is not publication time; listings and prices can change.",
        "Rule-based hypotheses require testing; no inferred market size, proven demand, certification or medical efficacy.", "Genuine semantic support remains independently unadjudicated.")
    return AnalysisDraft(label=pack.label, run_id=pack.run_id, input_hash=digest(pack.model_dump(mode="json")), as_of=pack.as_of,
        findings=findings + tuple(interpretations), normalized_prices=prices, comparisons=comparisons,
        price_comparisons=tuple(price_comparisons), opportunities=tuple(opportunities),
        conflicts=tuple({"competitor_id": str(lane.competitor_id), "details": conflict} for lane in pack.research for conflict in contradictions(lane.pages)),
        insufficiency_reason="Fewer than three rule triggers have sufficient fresh sampled evidence; do not fill the quota." if len(opportunities) < 3 else None,
        limitations=limits + tuple(dict.fromkeys(limit for lane in pack.research for limit in lane.limitations)))
