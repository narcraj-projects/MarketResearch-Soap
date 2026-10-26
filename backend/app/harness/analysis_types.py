"""Provider-neutral, immutable analysis handoffs. Agents cannot certify semantic support."""
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from .research_types import CompetitorResearch, Evidence

FindingKind = Literal["fact", "source_claim", "interpretation", "hypothesis"]
OpportunityRule = Literal["price_testing", "pack_clarity", "disclosure", "positioning_test", "feedback_test"]
ReviewDecision = Literal["ready_for_human", "revise", "unresolved"]


class AnalysisSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    schema_version: Literal["analysis-1.0"] = "analysis-1.0"


class Competitor(AnalysisSchema):
    competitor_id: UUID
    name: str = Field(min_length=1)
    canonical_url: str


class EvidencePack(AnalysisSchema):
    label: Literal["DEMO", "LIVE"] = "DEMO"
    run_id: UUID
    as_of: datetime
    freshness_days: int = Field(default=30, ge=1, le=365)
    competitors: tuple[Competitor, ...] = Field(min_length=1, max_length=3)
    research: tuple[CompetitorResearch, ...]

    @model_validator(mode="after")
    def scoped(self):
        ids = [c.competitor_id for c in self.competitors]
        if self.as_of.utcoffset() is None or len(ids) != len(set(ids)):
            raise ValueError("invalid_pack_identity_or_time")
        if set(ids) != {r.competitor_id for r in self.research} or len(ids) != len(self.research):
            raise ValueError("research_lane_mismatch")
        source_ids: list[UUID] = []
        for lane in self.research:
            if any(s.competitor_id != lane.competitor_id for s in lane.sources):
                raise ValueError("cross_competitor_source")
            source_ids.extend(s.source_id for s in lane.sources)
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("duplicate_source")
        return self


class NormalizedPrice(AnalysisSchema):
    observation_id: UUID
    competitor_id: UUID
    source_id: UUID
    locator: str
    sku: str | None
    variant: str | None
    amount: Decimal | None = Field(ge=0, allow_inf_nan=False)
    currency: str | None
    pack_qty: int | None
    total_weight_g: Decimal | None = Field(gt=0, allow_inf_nan=False)
    unit_price_100g: Decimal | None = Field(ge=0, allow_inf_nan=False)
    observed_at: datetime
    evidence: tuple[Evidence, ...]
    unavailable_reason: str | None

    @model_validator(mode="after")
    def known_or_unknown(self):
        if (self.unit_price_100g is None) != (self.unavailable_reason is not None):
            raise ValueError("normalization_value_or_reason")
        return self


class Finding(AnalysisSchema):
    finding_id: UUID
    competitor_id: UUID
    source_id: UUID | None = None
    product_locator: str | None = None
    field: str
    value: JsonValue
    kind: FindingKind
    text: str = Field(min_length=1)
    evidence: tuple[Evidence, ...] = ()
    premise_ids: tuple[UUID, ...] = ()
    unavailable_reason: str | None = None
    caveat: str | None = None

    @model_validator(mode="after")
    def grounding(self):
        if self.value is None:
            if not self.unavailable_reason:
                raise ValueError("missing_value_requires_reason")
        elif not self.evidence and not self.premise_ids:
            raise ValueError("finding_requires_grounding")
        return self


class ComparisonField(AnalysisSchema):
    field: str
    finding_ids: tuple[UUID, ...]
    unavailable_reason: str | None = None


class Comparison(AnalysisSchema):
    competitor_id: UUID
    name: str
    fields: tuple[ComparisonField, ...]


class PriceComparison(AnalysisSchema):
    currency: str
    observation_ids: tuple[UUID, ...]
    minimum: Decimal
    maximum: Decimal
    kind: Literal["interpretation"] = "interpretation"
    caveat: str = "Sampled listed prices per 100g; different products, not a market-wide or like-for-like ranking. No FX conversion."


class Opportunity(AnalysisSchema):
    opportunity_id: UUID
    rule: OpportunityRule
    kind: Literal["hypothesis"] = "hypothesis"
    title: str
    evidence_finding_ids: tuple[UUID, ...] = Field(min_length=1)
    rationale: str
    potential_benefit: str
    assumptions: tuple[str, ...] = Field(min_length=1)
    next_step: str
    caveat: str = "Hypothesis about the sampled evidence; demand and commercial benefit are unproven."


class AnalysisDraft(AnalysisSchema):
    label: Literal["DEMO", "LIVE"] = "DEMO"
    run_id: UUID
    input_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    as_of: datetime
    findings: tuple[Finding, ...]
    normalized_prices: tuple[NormalizedPrice, ...]
    comparisons: tuple[Comparison, ...]
    price_comparisons: tuple[PriceComparison, ...]
    opportunities: tuple[Opportunity, ...] = Field(max_length=5)
    conflicts: tuple[JsonValue, ...] = ()
    insufficiency_reason: str | None = None
    limitations: tuple[str, ...]
    support_status: Literal["unreviewed"] = "unreviewed"

    @model_validator(mode="after")
    def count_and_ids(self):
        if len(self.opportunities) < 3 and not self.insufficiency_reason:
            raise ValueError("opportunity_shortfall_requires_reason")
        for rows, key in ((self.findings, "finding_id"), (self.normalized_prices, "observation_id"), (self.opportunities, "opportunity_id")):
            if len(rows) != len({getattr(row, key) for row in rows}):
                raise ValueError("duplicate_analysis_id")
        return self


class ReviewIssue(AnalysisSchema):
    code: str
    target: str
    severity: Literal["correction", "warning", "blocker"]
    explanation: str


class ReviewResult(AnalysisSchema):
    reviewer_version: Literal["independent-review-1.0"] = "independent-review-1.0"
    input_hash: str
    draft_hash: str
    decision: ReviewDecision
    issues: tuple[ReviewIssue, ...]
    citation_presence: float | None
    quote_integrity: float | None
    genuine_support_coverage: None = None
    semantic_support: Literal["not_adjudicated"] = "not_adjudicated"
