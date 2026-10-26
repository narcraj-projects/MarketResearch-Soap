from app.harness.analysis_types import ReviewResult
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from app.agents.scout import DiscoveryArtifact
from app.harness.research_types import CompetitorResearch


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, hide_input_in_errors=True, str_strip_whitespace=True)


class BriefCreate(Schema):
    category: str = Field(min_length=1, max_length=300)
    geography: str = Field(min_length=1, max_length=300)
    customer: str = Field(min_length=1, max_length=1000)
    objective: str = Field(min_length=1, max_length=2000)
    known_competitors: list[Annotated[str, Field(min_length=1, max_length=300)]] = Field(default_factory=list, max_length=20)
    preferences: "BriefPreferences" = Field(default_factory=lambda: BriefPreferences())


class BriefPreferences(Schema):
    price_segment: Literal["Let agent find out", "Everyday", "Mid-premium", "Gifting / luxe"] = "Let agent find out"
    own_price: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    own_weight_g: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    currency: Literal["INR"] = "INR"


class BriefRecord(BriefCreate):
    id: UUID
    owner_id: UUID
    created_at: datetime
    version: int


class RunBudget(Schema):
    max_calls: int = Field(ge=1, le=1000, strict=True)
    max_tokens: int = Field(ge=0, le=1000000, strict=True)
    max_cost_usd: Decimal = Field(ge=0, le=1000, allow_inf_nan=False)


class RunCreate(Schema):
    brief_id: UUID
    budget: RunBudget


class RunRecord(Schema):
    id: UUID
    owner_id: UUID
    created_at: datetime
    brief_id: UUID
    status: Literal["queued", "shortlist_review", "researching", "report_review", "complete", "cancelled", "partial", "failed"]
    version: int
    budget: dict[str, Any]
    checkpoint: dict[str, Any] | None
    failure_code: str | None


class DecisionCreate(Schema):
    request_id: UUID
    artifact_version: int = Field(gt=0)
    artifact_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    expected_run_version: int = Field(gt=0)
    decision: Literal["approve", "reject", "request_changes"]


class DecisionRecord(Schema):
    id: UUID
    owner_id: UUID
    run_id: UUID
    created_at: datetime
    request_id: UUID
    decision: str
    artifact_version: int
    artifact_hash: str


class ResourceRecord(BaseModel):
    """Read-only data envelope; database-owned fields are never writable inputs."""
    id: UUID
    owner_id: UUID
    run_id: UUID
    created_at: datetime
    data: dict[str, Any]


class EventRecord(ResourceRecord):
    sequence: int
    kind: str


class OwnedRecord(Schema):
    id: UUID
    owner_id: UUID
    run_id: UUID
    created_at: datetime


class CompetitorRecord(OwnedRecord):
    name: str
    canonical_url: str


class SourceRecord(OwnedRecord):
    canonical_url: str
    title: str
    publisher: str
    retrieved_at: datetime
    content_hash: str | None
    access_status: Literal["ok", "denied", "unavailable"]
    excerpt: str | None
    evidence_kind: Literal["search_snippet", "page_excerpt", "robots_policy"]


class ClaimRecord(OwnedRecord):
    text: str
    kind: Literal["fact", "interpretation", "hypothesis", "competitor_marketing_claim"]
    material: bool
    review_status: str


class ProductRecord(OwnedRecord):
    competitor_id: UUID
    sku: str | None
    name: str
    ingredients: list[str] | None
    attributes: dict[str, Any]


class PriceRecord(OwnedRecord):
    product_id: UUID
    source_id: UUID
    amount: Decimal
    currency: str
    total_weight_g: Decimal | None
    pack_qty: int | None
    observed_at: datetime
    unit_price_100g: Decimal | None
    normalization_data: dict[str, Any] | None = None




class ReportRecord(OwnedRecord):
    version: int
    content_hash: str
    data: dict[str, Any]
    review: ReviewResult | None = None


class ApprovalRequestRecord(OwnedRecord):
    gate: Literal["shortlist", "report"]
    artifact_version: int
    artifact_hash: str
    state: Literal["pending", "decided", "superseded"]
    artifact: dict[str, Any]


class EvaluationRecord(OwnedRecord):
    case_id: UUID
    outcome: str
    data: dict[str, Any]


class UsageRecord(OwnedRecord):
    operation_id: UUID
    attempt: int
    calls: int
    tokens: int
    cost_usd: Decimal


class Me(Schema):
    user_id: UUID


class ShortlistSnapshot(Schema):
    run_id: UUID
    run_version: int = Field(gt=0)
    status: Literal["shortlist_review", "researching", "report_review", "complete", "partial", "cancelled", "failed"]
    request_id: UUID | None
    artifact_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    artifact_version: int = Field(gt=0)
    artifact: DiscoveryArtifact


class Error(Schema):
    detail: str


class ResearchRecord(OwnedRecord):
    competitor_id: UUID
    state: Literal["complete", "partial"]
    data: CompetitorResearch


class ClaimEvidenceRecord(OwnedRecord):
    claim_id: UUID
    source_id: UUID
    quote: str
    excerpt_hash: str
    locator: str | None


class RunControl(Schema):
    expected_run_version: int = Field(gt=0)


class RunResume(RunControl):
    deadline_seconds: int = Field(default=3600, ge=30, le=86400)
