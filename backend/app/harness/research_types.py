"""Research/evidence contracts. No agent can assign trusted support labels."""
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Protocol
from typing import ContextManager
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from .contracts import Role, RunContext


class ResearchSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    schema_version: Literal["research-1.0"] = "research-1.0"


class ResearchCall(ResearchSchema):
    agent: Literal[Role.RESEARCHER] = Role.RESEARCHER
    operation_id: UUID
    competitor_id: UUID
    tool: Literal["public.retrieve", "public.news", "public.search"]
    url: str = Field(min_length=1, max_length=4000)
    kind: Literal["page", "robots", "news"]
    query: str | None = Field(default=None, max_length=2000)
    timeout_seconds: int = Field(default=15, ge=1, le=30, strict=True)

    @model_validator(mode="after")
    def call_shape(self):
        if (self.tool in {"public.news", "public.search"}) != (self.kind == "news") or (self.kind == "news") != (self.query is not None):
            raise ValueError("tool_arguments_mismatch")
        return self


class WireReply(ResearchSchema):
    status: int = Field(ge=0, le=599, strict=True)
    body: str | None = Field(default=None, max_length=256000)
    content_type: str = Field(default="text/html", max_length=100)
    robots_tag: str | None = Field(default=None, max_length=200)
    encoding: Literal["identity", "unsupported"] = "identity"
    location: str | None = Field(default=None, max_length=4000)
    retry_after: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    peer_ip: str | None = None
    failure: Literal["timeout", "network", "peer_mismatch", "response_limit", "unsafe_redirect"] | None = None


class RetrievedSource(ResearchSchema):
    label: Literal["DEMO", "LIVE"] = "DEMO"
    source_id: UUID
    competitor_id: UUID
    canonical_url: str
    requested_url: str
    retrieved_at: datetime
    title: str
    publisher: str
    access_status: Literal["ok", "denied", "unavailable"]
    evidence_kind: Literal["page_excerpt", "search_snippet", "robots_policy"]
    content_hash: str | None
    text_hash: str | None
    body: str | None = Field(default=None, max_length=256000)
    excerpt: str | None = Field(default=None, max_length=256000)
    structured: tuple[JsonValue, ...] = ()
    links: tuple[str, ...] = ()
    reason: str | None = Field(default=None, max_length=80)
    support: Literal["unreviewed"] = "unreviewed"

    @model_validator(mode="after")
    def coherent(self):
        from hashlib import sha256
        if self.retrieved_at.utcoffset() is None:
            raise ValueError("timezone_required")
        if self.access_status == "ok":
            if self.body is None or self.excerpt is None or sha256(self.body.encode()).hexdigest() != self.content_hash or sha256(self.excerpt.encode()).hexdigest() != self.text_hash:
                raise ValueError("source_hash_mismatch")
        elif self.body is not None or self.excerpt is not None or self.content_hash is not None or self.text_hash is not None or not self.reason:
            raise ValueError("failed_source_has_no_content")
        return self


class WireOutcome(ResearchSchema):
    competitor_id: UUID
    reply: WireReply
    source: RetrievedSource | None = None


class Evidence(ResearchSchema):
    source_id: UUID
    quote: str = Field(min_length=1, max_length=10000)
    quote_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    locator: str = Field(min_length=1, max_length=1000)


class Observation(ResearchSchema):
    field: str = Field(min_length=1, max_length=80)
    value: JsonValue = None
    evidence: tuple[Evidence, ...] = ()
    unavailable_reason: str | None = Field(default=None, max_length=100)
    kind: Literal["fact", "competitor_marketing_claim"] = "fact"

    @model_validator(mode="after")
    def grounded_or_unknown(self):
        if self.value is None:
            if not self.unavailable_reason or self.evidence:
                raise ValueError("unknown_requires_reason")
        elif not self.evidence or self.unavailable_reason is not None:
            raise ValueError("value_requires_evidence")
        return self


FinitePrice = Annotated[Decimal, Field(ge=0, allow_inf_nan=False, max_digits=18, decimal_places=4)]
Weight = Annotated[Decimal, Field(gt=0, allow_inf_nan=False, max_digits=18, decimal_places=4)]


class ProductExtraction(ResearchSchema):
    source_id: UUID
    locator: str
    name: str
    sku: str | None
    variant: str | None = None
    amount: FinitePrice | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    weight_g: Weight | None = None
    pack_qty: int | None = Field(default=None, gt=0, strict=True)
    weight_basis: Literal["per_bar", "total_pack", "unknown"] = "unknown"
    total_weight_g: Weight | None = None
    ingredients: tuple[str, ...] | None = None
    observations: tuple[Observation, ...]


class PageExtraction(ResearchSchema):
    source_id: UUID
    products: tuple[ProductExtraction, ...]
    observations: tuple[Observation, ...]
    limitations: tuple[str, ...] = ()


class CompetitorResearch(ResearchSchema):
    label: Literal["DEMO", "LIVE"] = "DEMO"
    competitor_id: UUID
    state: Literal["complete", "partial"]
    sources: tuple[RetrievedSource, ...]
    pages: tuple[PageExtraction, ...]
    conflicts: tuple[JsonValue, ...] = ()
    limitations: tuple[str, ...] = ()


class ResearchJournal(Protocol):
    def reserve(self, context: RunContext, call: ResearchCall, attempt: int, fingerprint: str, cost: Decimal, now: datetime) -> WireOutcome | None: ...
    def complete(self, context: RunContext, call: ResearchCall, attempt: int, fingerprint: str, outcome: WireOutcome, now: datetime) -> None: ...


class ResearchState(Protocol):
    def lane(self, context: RunContext, competitor_id: UUID) -> ContextManager[None]: ...
    def cached_task(self, context: RunContext, cid: UUID) -> CompetitorResearch | None: ...
    def save_task(self, context: RunContext, cid: UUID, sources: tuple[RetrievedSource, ...], limitations: tuple[str, ...]) -> CompetitorResearch: ...
    def finish(self, context: RunContext) -> None: ...
