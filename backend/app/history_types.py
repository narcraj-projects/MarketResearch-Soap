"""Versioned immutable history projections; statuses describe sampled evidence only."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, JsonValue

from app.report_types import ViewSchema, SourceView


class HistoricalVersion(ViewSchema):
    report_id: UUID
    run_id: UUID
    version: int
    content_hash: str
    created_at: datetime
    as_of: datetime | None
    approval: str
    comparable: bool
    label: Literal["DEMO", "LIVE"] | None


class VersionList(ViewSchema):
    entries: list[HistoricalVersion]
    total: int


class DatedEvidence(ViewSchema):
    source: SourceView
    quote: str | None = None
    quote_hash: str | None = None
    locator: str | None = None


class HistoricalValue(ViewSchema):
    values: tuple[JsonValue, ...] = ()
    evidence: tuple[DatedEvidence, ...] = ()
    kinds: tuple[str, ...] = ()
    reason: str | None = None
    usable: bool = False


ChangeKind = Literal["new", "changed", "gone", "unchanged", "unknown", "stale"]


class HistoricalChange(ViewSchema):
    change_id: UUID
    brand_id: UUID | None
    product_id: UUID | None
    brand: str
    product: str | None
    color_index: int | None = Field(default=None, ge=0, le=2)
    field: str
    status: ChangeKind
    reason: str
    before: HistoricalValue
    after: HistoricalValue
    caveat: str = "Dated source observations, not independently established market truth. New means newly observed in this sample; gone requires an explicit first-party discontinued status."


class HistoryDiff(ViewSchema):
    schema_version: Literal["history-diff-1.0"] = "history-diff-1.0"
    identity_version: Literal["history-identity-1.0"] = "history-identity-1.0"
    label: Literal["DEMO", "LIVE"] = "DEMO"
    before: HistoricalVersion
    after: HistoricalVersion
    counts: dict[ChangeKind, int]
    changes: tuple[HistoricalChange, ...]
    freshness_days: int = Field(default=30, ge=1, le=365)
    count_definition: str = "One row per stable brand/product and field, not a count of launches, products, businesses or discontinued brands. All evidence is historical as of the selected reports."
    limitations: tuple[str, ...]
