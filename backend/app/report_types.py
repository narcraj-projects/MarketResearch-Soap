"""Versioned report presentation; citation diagnostics are not semantic-support scores."""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.api_schemas import BriefRecord, RunRecord, EventRecord, ShortlistSnapshot, CompetitorRecord
from app.harness.analysis_types import AnalysisDraft, ReviewResult
from app.agents.scout import DiscoveryArtifact
from app.harness.chaos import ChaosPlan
from app.harness.live_types import LiveNarrative


class ViewSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class Coverage(ViewSchema):
    material_facts: int
    linked: int
    intact_quotes: int
    citation_presence: float | None
    quote_coverage: float | None
    genuine_support_coverage: None = None
    semantic_support: Literal["not_adjudicated"] = "not_adjudicated"
    denominator_definition: str = "All non-null fact and source_claim finding IDs, including unsupported or uncited assertions. Unknowns, interpretations and hypotheses are excluded; their factual premises remain included."
    comparison_fields: int
    populated_fields: int
    unavailable_fields: int


class Position(ViewSchema):
    competitor_id: UUID
    x: Literal["ingredient_led", "mixed", "results_led"] | None
    y: Literal["everyday", "mixed", "gifting"] | None
    premise_ids: tuple[UUID, ...]
    explanation: str


class SourceView(ViewSchema):
    id: UUID
    competitor_id: UUID | None = None
    canonical_url: str | None
    title: str
    publisher: str
    retrieved_at: datetime
    content_hash: str | None
    access_status: str
    evidence_kind: str
    excerpt: str | None = None

    @field_validator("canonical_url")
    @classmethod
    def public_link(cls, value):
        if value:
            from urllib.parse import urlsplit
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("invalid_source_link")
        return value


class ReportSnapshot(ViewSchema):
    schema_version: Literal["report-presentation-1.0"] = "report-presentation-1.0"
    label: Literal["DEMO", "LIVE"]
    live_narrative: LiveNarrative | None = None
    brief: BriefRecord
    summary: str
    scope: str
    analysis: AnalysisDraft
    coverage: Coverage
    positioning: tuple[Position, ...]
    sources: tuple[SourceView, ...]
    shortlist: DiscoveryArtifact | None = None


class ApprovalView(ViewSchema):
    state: Literal["pending", "approved_awaiting_save", "saved", "rejected", "unavailable"]
    request_id: UUID | None = None
    decision_id: UUID | None = None
    decision: str | None = None
    decided_at: datetime | None = None
    artifact_version: int
    artifact_hash: str
    can_decide: bool = False


class ReportView(ViewSchema):
    id: UUID
    version: int
    content_hash: str
    created_at: datetime
    snapshot: ReportSnapshot | None
    unavailable_reason: str | None = None
    review: ReviewResult | None
    approval: ApprovalView
    export_allowed: bool
    projection: Literal["persisted", "legacy_immutable_inputs", "unavailable"]


class RunView(ViewSchema):
    schema_version: Literal["run-view-1.0"] = "run-view-1.0"
    label: Literal["DEMO", "LIVE"] | None = None
    run: RunRecord | None
    brief: BriefRecord | None = None
    shortlist: ShortlistSnapshot | None = None
    competitors: list[CompetitorRecord] = []
    sources: list[SourceView] = []
    research: list[dict[str, Any]] = []
    events: list[EventRecord] = []
    event_count: int = 0
    checkpoint_at: datetime | None = None
    completed_nodes: list[str] = []
    usage: dict[str, Any] = {}
    report: ReportView | None = None
    chaos: ChaosPlan | None = None
    recovery: dict[str, int] = {}


class HistoryEntry(ViewSchema):
    id: UUID
    created_at: datetime
    status: str
    category: str
    geography: str
    competitors: int
    report_id: UUID | None
    report_version: int | None
    label: Literal["DEMO", "LIVE"] | None
    saved_report_version: int | None = None
    saved_as_of: datetime | None = None
    report_versions: int = 0


class HistoryView(ViewSchema):
    entries: list[HistoryEntry]
    total: int
