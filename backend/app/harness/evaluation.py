"""Counts adjudicated links, never infers semantic support from citation presence."""
from .contracts import Claim


def claim_metrics(claims: tuple[Claim, ...]) -> dict[str, float | int | None]:
    # Marketing attribution is factual ("the brand says X"), not efficacy evidence.
    material = [c for c in claims if c.material and c.kind in {"fact", "competitor_marketing_claim"}]
    if len({c.claim_id for c in claims}) != len(claims):
        raise ValueError("duplicate_claim_id")
    cited = sum(bool(c.evidence) for c in material)
    supported = sum(any(e.support == "supported" for e in c.evidence) and not any(e.support == "contradicted" for e in c.evidence) for c in material)
    count = len(material)
    return {"material_facts": count, "cited": cited, "supported": supported, "citation_presence": cited / count if count else None, "support_coverage": supported / count if count else None}
