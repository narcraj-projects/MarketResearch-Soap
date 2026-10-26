"""Bounded local corrections to named targets; never retrieve, broaden or manufacture data."""
from typing import Any
from uuid import UUID

from app.agents.analyst import analyze
from app.harness.analysis_types import AnalysisDraft, EvidencePack, ReviewResult
from app.harness.policy import PolicyDenied
from app.repository import digest


def correct(pack: EvidencePack, draft: AnalysisDraft, assessment: ReviewResult) -> tuple[AnalysisDraft, tuple[str, ...]]:
    if assessment.draft_hash != digest(draft.model_dump(mode="json")) or assessment.input_hash != draft.input_hash:
        raise PolicyDenied("correction_review_binding")
    canonical = analyze(pack)
    targets = tuple(sorted({i.target for i in assessment.issues if i.severity == "correction"}))
    changes: dict[str, Any] = {}
    for section, prefix, key in (("findings", "finding:", "finding_id"), ("normalized_prices", "price:", "observation_id"), ("opportunities", "opportunity:", "opportunity_id")):
        selected = {UUID(target[len(prefix):]) for target in targets if target.startswith(prefix)}
        full = {"findings": "findings", "normalized_prices": "prices", "opportunities": "opportunities"}[section] in targets
        if selected or full:
            original = {getattr(row, key): row for row in getattr(draft, section)}
            expected = {getattr(row, key): row for row in getattr(canonical, section)}
            if full:
                selected |= set(expected) - set(original)
            for identifier in selected:
                if identifier in expected:
                    original[identifier] = expected[identifier]
                else:
                    original.pop(identifier, None)  # Remove an unsupported assertion, not the underlying evidence.
            changes[section] = tuple(original[k] for k in sorted(original, key=str))
    for section in ("comparisons", "price_comparisons", "conflicts", "limitations"):
        if section in targets:
            changes[section] = getattr(canonical, section)
    if "opportunities" in changes and len(changes["opportunities"]) < 3:
        changes["insufficiency_reason"] = "Targeted correction removed unsupported hypotheses; fewer than three remain."
    corrected = AnalysisDraft.model_validate(draft.model_dump() | changes)
    return corrected, targets
