"""Versioned search payloads. Snippets are unreviewed, never verified page content."""
from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field, model_validator

from .contracts import Contract, Digest, Money, RunContext, SearchCall, ToolResult


class SearchSource(Contract):
    source_id: UUID
    canonical_url: str = Field(min_length=1, max_length=4000)
    domain: str = Field(min_length=1, max_length=253)
    title: str = Field(min_length=1, max_length=500)
    publisher: str = Field(min_length=1, max_length=253)
    excerpt: str = Field(min_length=1, max_length=10000)
    retrieved_at: datetime
    content_hash: Digest
    access_status: Literal["ok"] = "ok"
    evidence_kind: Literal["search_snippet"] = "search_snippet"
    support: Literal["unreviewed"] = "unreviewed"

    @model_validator(mode="after")
    def aware(self):
        if self.retrieved_at.utcoffset() is None:
            raise ValueError("timezone_required")
        return self


class SearchPayload(Contract):
    label: Literal["DEMO", "LIVE"] = "DEMO"
    sources: tuple[SearchSource, ...] = Field(default=(), max_length=10)
    rejected_urls: int = Field(default=0, ge=0, strict=True)


class AttemptOutcome(Contract):
    status: Literal["ok", "timeout", "rate_limited", "denied", "unavailable", "invalid"]
    retryable: bool = Field(strict=True, default=False)
    retry_after_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    payload: SearchPayload | None = None

    @model_validator(mode="after")
    def coherent(self):
        if (self.status == "ok") != (self.payload is not None):
            raise ValueError("payload_status_mismatch")
        if self.retryable and self.status not in {"timeout", "rate_limited", "unavailable"}:
            raise ValueError("nontransient_retry")
        return self


class SearchExecution(Contract):
    result: ToolResult
    payload: SearchPayload | None = None
    stop_reason: Literal["complete", "exhausted", "budget", "deadline", "uncertain_attempt"]


class SearchCost(Contract):
    # No dollar price is inferred from credits. None fails before dispatch.
    per_attempt_upper_bound_usd: Money | None = Field(default=None, decimal_places=8, max_digits=18)
    pricing_version: str = Field(min_length=1, max_length=100)
    accounting: Literal["DEMO_conservative_reservation"] = "DEMO_conservative_reservation"


class SearchLedger(Protocol):
    def reserve(self, context: RunContext, call: SearchCall, fingerprint: str, cost: Decimal, now: datetime) -> AttemptOutcome | None: ...
    def complete(self, context: RunContext, call: SearchCall, fingerprint: str, outcome: AttemptOutcome, now: datetime) -> None: ...


class ReplayMismatch(ValueError):
    """Exact non-sensitive mismatch code; never include request/response values."""
