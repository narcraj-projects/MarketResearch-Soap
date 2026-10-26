"""Independent deterministic review: reads raw evidence, never trusts analyst scores.

Mechanical and narrow atomic-value validation are not general semantic adjudication.
No human approval or semantic-support labels can be granted by this module.
"""
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP, localcontext
from uuid import uuid5

from pydantic import ValidationError

from app.agents.analysis_policy import FIELD_GROUPS, MEDICAL, RULES
from app.agents.evidence_catalog import catalog
from app.agents.extraction import contradictions
from app.agents.normalization import same_item_binding
from app.harness.analysis_types import AnalysisDraft, EvidencePack, PriceComparison, NormalizedPrice, ReviewDecision, ReviewIssue, ReviewResult
from app.repository import digest

def review(pack: EvidencePack, draft: AnalysisDraft, *, revisions_remaining: bool = True) -> ReviewResult:
    trusted = {f.finding_id: f for f in catalog(pack)}
    sources = {s.source_id: s for lane in pack.research for s in lane.sources}
    findings = {f.finding_id: f for f in draft.findings}
    issues = []
    def issue(code, target, explanation, severity="correction"):
        issues.append(ReviewIssue(code=code, target=target, severity=severity, explanation=explanation))
    if draft.input_hash != digest(pack.model_dump(mode="json")) or draft.run_id != pack.run_id or draft.as_of != pack.as_of:
        issue("input_binding", "metadata", "Draft is not bound to this frozen run/evidence/time policy.", "blocker")
    for fid, expected in trusted.items():
        if fid not in findings:
            issue("missing_observation", "findings", "A collected observation/unknown was omitted; do not hide the denominator.")
    material = [f for f in draft.findings if f.value is not None and f.kind in {"fact", "source_claim"}]
    cited = sum(bool(f.evidence) for f in material)
    intact = 0
    for finding in draft.findings:
        target = "finding:" + str(finding.finding_id)
        if finding.finding_id in trusted:
            if finding != trusted[finding.finding_id]:
                issue("source_value_or_attribution", target, "Field/value/scope/quote/narrative differs from independently reconstructed source observation.")
        elif finding.kind == "interpretation":
            premises = [trusted.get(key) for key in finding.premise_ids]
            if (finding.field != "sample_price_comparison" or not premises or any(p is None or p.field != "price" or p.value is None for p in premises)
                or finding.text != PriceComparison.model_fields["caveat"].default):
                issue("unsupported_interpretation", target, "Interpretation has unsupported factual premises or is outside the current deterministic comparison contract.")
        else:
            issue("unsupported_finding", target, "No matching collected observation; a citation alone cannot establish this assertion.")
        valid = bool(finding.evidence)
        for evidence in finding.evidence:
            source = sources.get(evidence.source_id)
            from hashlib import sha256
            if (source is None or source.competitor_id != finding.competitor_id or source.access_status != "ok"
                or evidence.quote not in (source.excerpt or "") or sha256(evidence.quote.encode()).hexdigest() != evidence.quote_hash):
                issue("citation_integrity", target, "Citation is unavailable, cross-competitor or not an exact hashed source excerpt.")
                valid = False
        if finding in material and valid:
            intact += 1
        if finding.value is None:
            issue("missing_evidence", target, finding.unavailable_reason or "Unavailable; no inference made.", "warning")
        elif MEDICAL.search(str(finding.value) + " " + finding.text):
            issue("unsupported_medical_or_certification_claim", target,
                "Source wording is not efficacy/certification evidence; retain only attributed wording for human review.",
                "warning" if finding.kind == "source_claim" and finding.finding_id in trusted and finding == trusted[finding.finding_id] else "correction")
    for source in sources.values():
        if source.access_status != "ok":
            issue("inaccessible_source", "source:" + str(source.source_id), source.reason or source.access_status, "warning")
        if source.retrieved_at > pack.as_of or source.retrieved_at < pack.as_of - timedelta(days=pack.freshness_days):
            issue("source_freshness", "source:" + str(source.source_id), "Future-dated or older than the configured evidence window; not a current finding.", "warning")
    for finding in trusted.values():
        if finding.field == "published_date" and finding.value is not None:
            try:
                published = datetime.fromisoformat(str(finding.value).replace("Z", "+00:00"))
                if published.tzinfo is None or published > pack.as_of or published < pack.as_of - timedelta(days=pack.freshness_days):
                    issue("publication_freshness", "finding:" + str(finding.finding_id), "Retrieval date does not make this a recent announcement.", "warning")
            except ValueError:
                issue("publication_date_unknown", "finding:" + str(finding.finding_id), "Publication date cannot establish freshness.", "warning")
    expected_prices = {}
    for lane in pack.research:
        for page in lane.pages:
            for product in page.products:
                oid = uuid5(lane.competitor_id, f"price:{page.source_id}:{product.locator}")
                expected_prices[oid] = (product, sources[page.source_id], lane.competitor_id)
    actual_prices = {p.observation_id: p for p in draft.normalized_prices}
    if set(actual_prices) != set(expected_prices):
        issue("price_observations_missing_or_extra", "prices", "All collected purchase items, including unavailable normalized values, must remain visible.")
    eligible = {}
    for oid, observed in actual_prices.items():
        target = "price:" + str(oid)
        if oid not in expected_prices:
            continue
        product, source, cid = expected_prices[oid]
        needed = {"sku", "price", "currency", "weight_g", "weight_basis"} | ({"pack_qty"} if product.weight_basis == "per_bar" else set())
        observed_fields = {o.field: o for o in product.observations if o.value is not None}
        expected_evidence = tuple(e for key in sorted(needed) if key in observed_fields for e in observed_fields[key].evidence)
        if observed.evidence != expected_evidence:
            issue("normalization_provenance", target, "Price/weight evidence must resolve to the same verified purchase item.")
        total, unit = None, None
        if product.sku and product.amount is not None and product.currency and product.weight_g is not None and same_item_binding(product, source):
            with localcontext() as context:
                context.prec = 60
                if product.weight_basis == "total_pack":
                    total = product.weight_g
                elif product.weight_basis == "per_bar" and product.pack_qty:
                    total = product.weight_g * product.pack_qty
                if total is not None and total == product.total_weight_g:
                    unit = (product.amount / total * 100).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
                    if unit >= Decimal("10000000000000000"):
                        total, unit = None, None
                else:
                    total = None
        if (observed.source_id != source.source_id or observed.competitor_id != cid or observed.sku != product.sku or observed.variant != product.variant
            or observed.amount != product.amount or observed.currency != product.currency or observed.pack_qty != product.pack_qty
            or observed.locator != product.locator or observed.observed_at != source.retrieved_at
            or observed.total_weight_g != total or observed.unit_price_100g != unit):
            issue("sku_pack_arithmetic", target, "Reviewer recomputation does not match the same SKU/variant/offer/weight and dated source.")
        if unit is not None and pack.as_of - timedelta(days=pack.freshness_days) <= source.retrieved_at <= pack.as_of:
            # Judge dependent ranges against independently recomputed values. A bad
            # row must not make an otherwise correct comparison appear unsupported.
            eligible[oid] = observed.model_copy(update={"competitor_id": cid, "source_id": source.source_id, "locator": product.locator,
                "sku": product.sku, "variant": product.variant, "amount": product.amount, "currency": product.currency,
                "pack_qty": product.pack_qty, "total_weight_g": total, "unit_price_100g": unit, "observed_at": source.retrieved_at})
        elif unit is None:
            issue("normalization_unavailable", target, observed.unavailable_reason or "Same purchase-item basis unavailable.", "warning")
    currency_groups: dict[str | None, list[NormalizedPrice]] = {}
    for row in eligible.values():
        currency_groups.setdefault(row.currency, []).append(row)
    expected_groups = {currency: rows for currency, rows in currency_groups.items() if len({p.competitor_id for p in rows}) >= 2}
    if len(draft.price_comparisons) != len(expected_groups) or {c.currency for c in draft.price_comparisons} != set(expected_groups):
        issue("price_comparison_scope", "price_comparisons", "Compare only fresh eligible observations within one currency and at least two competitors.")
    for comparison in draft.price_comparisons:
        rows = expected_groups.get(comparison.currency, [])
        if not rows or set(comparison.observation_ids) != {p.observation_id for p in rows} or comparison.minimum != min(p.unit_price_100g for p in rows if p.unit_price_100g is not None) or comparison.maximum != max(p.unit_price_100g for p in rows if p.unit_price_100g is not None):
            issue("price_comparison_arithmetic", "price_comparisons", "Comparison range or observation scope is incorrect; no FX or stale-price substitution.")
    expected_conflicts = tuple({"competitor_id": str(lane.competitor_id), "details": c} for lane in pack.research for c in contradictions(lane.pages))
    if draft.conflicts != expected_conflicts:
        issue("conflicts_omitted", "conflicts", "Keep both contradictory observations; never silently choose a winner.")
    for conflict in expected_conflicts:
        issue("conflicting_evidence", "competitor:" + str(conflict["competitor_id"]), "Sources disagree; observations and source dates remain distinct.", "warning")
    for competitor in pack.competitors:
        matching = [c for c in draft.comparisons if c.competitor_id == competitor.competitor_id]
        if len(matching) != 1 or matching[0].name != competitor.name or len(matching[0].fields) != len(FIELD_GROUPS):
            issue("comparison_missing", "comparisons", "Every approved competitor and comparison field needs a value or explicit unavailable reason.")
            continue
        for field, members in FIELD_GROUPS.items():
            cells = [cell for cell in matching[0].fields if cell.field == field]
            expected_ids = {f.finding_id for f in trusted.values() if f.competitor_id == competitor.competitor_id and f.field in members}
            available = any(trusted[key].value is not None for key in expected_ids)
            if len(cells) != 1 or set(cells[0].finding_ids) != expected_ids or bool(cells[0].unavailable_reason) == available:
                issue("comparison_grounding", "comparisons", "Comparison contains wrong entity/field references or hides missing data.")
    if {c.competitor_id for c in draft.comparisons} != {c.competitor_id for c in pack.competitors}:
        issue("comparison_entity", "comparisons", "Unapproved or omitted competitor in comparison.")
    seen_rules = set()
    for opportunity in draft.opportunities:
        target = "opportunity:" + str(opportunity.opportunity_id)
        premises = [trusted.get(key) for key in opportunity.evidence_finding_ids]
        field = {"price_testing": "price", "pack_clarity": "weight_g", "disclosure": "ingredients", "positioning_test": "positioning", "feedback_test": "public_review"}[opportunity.rule]
        valid = bool(premises) and all(p is not None and p.field == field for p in premises)
        known = [p for p in premises if p is not None and p.value is not None]
        fresh = all(p is not None and p.source_id in sources and pack.as_of - timedelta(days=pack.freshness_days) <= sources[p.source_id].retrieved_at <= pack.as_of for p in premises)
        valid = valid and fresh and opportunity.rule not in seen_rules
        seen_rules.add(opportunity.rule)
        if opportunity.rule in {"pack_clarity", "disclosure"}:
            valid = valid and bool(known) and len({p.competitor_id for p in premises if p is not None}) >= 2 and (any(p is not None and p.value is None for p in premises) or len({str(p.value) for p in known}) > 1)
        else:
            valid = valid and len({p.competitor_id for p in known}) >= 2
            if opportunity.rule == "positioning_test":
                valid = valid and len({str(p.value) for p in known}) >= 2
            if opportunity.rule == "price_testing":
                supported_rows = [p for p in eligible.values() if any(f is not None and f.product_locator == p.locator and f.competitor_id == p.competitor_id and any(e.source_id == p.source_id for e in f.evidence) for f in premises)]
                valid = valid and any(len({p.competitor_id for p in supported_rows if p.currency == currency}) >= 2 and
                    len({p.unit_price_100g for p in supported_rows if p.currency == currency}) > 1 for currency in expected_groups)
        template = RULES[opportunity.rule]
        if (opportunity.title, opportunity.rationale, opportunity.potential_benefit, opportunity.assumptions, opportunity.next_step) != (template[0], template[1], template[2], (template[3],), template[4]):
            valid = False
        if opportunity.caveat != type(opportunity).model_fields["caveat"].default or opportunity.opportunity_id != uuid5(pack.run_id, "opportunity:" + opportunity.rule):
            valid = False
        if not valid:
            issue("unsupported_opportunity", target, "Hypothesis contains an unsupported premise, stale/irrelevant citation or unreviewed factual narrative.")
    for comparison in draft.price_comparisons:
        if comparison.caveat != PriceComparison.model_fields["caveat"].default:
            issue("comparison_narrative", "price_comparisons", "Unreviewed factual narrative in comparison caveat.")
    if any(MEDICAL.search(text) for text in draft.limitations):
        issue("medical_narrative", "limitations", "Unsupported medical narrative outside attributed source observations.")
    unique = tuple({(i.code, i.target, i.severity): i for i in issues}.values())
    corrections = any(i.severity == "correction" for i in unique)
    decision: ReviewDecision = "unresolved" if any(i.severity == "blocker" for i in unique) or (corrections and not revisions_remaining) else "revise" if corrections else "ready_for_human"
    return ReviewResult(input_hash=digest(pack.model_dump(mode="json")), draft_hash=digest(draft.model_dump(mode="json")), decision=decision, issues=unique,
        citation_presence=cited / len(material) if material else None, quote_integrity=intact / len(material) if material else None)


def review_payload(pack: EvidencePack, payload: dict, *, revisions_remaining: bool = True) -> ReviewResult:
    try:
        draft = AnalysisDraft.model_validate(payload)
    except ValidationError:
        return ReviewResult(input_hash=digest(pack.model_dump(mode="json")), draft_hash=digest(payload), decision="unresolved",
            issues=(ReviewIssue(code="schema_invalid", target="draft", severity="blocker", explanation="Malformed analysis output; input details suppressed."),),
            citation_presence=None, quote_integrity=None)
    return review(pack, draft, revisions_remaining=revisions_remaining)
