"""Version-one boundary schemas, not a workflow or persistence implementation."""
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator

Count = Annotated[int, Field(strict=True, ge=0)]
Positive = Annotated[int, Field(strict=True, gt=0)]
Text = Annotated[str, Field(min_length=1, max_length=2000)]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Money = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)
    schema_version: Literal["1.0"] = "1.0"


class Versions(Contract):
    graph: Text
    model: Text
    provider: Text
    prompt: Text
    tools: Text
    dataset: Text


class Role(StrEnum):
    ORCHESTRATOR = "orchestrator"
    SCOUT = "scout"
    RESEARCHER = "researcher"
    ANALYST = "analyst"
    REVIEWER = "reviewer"


class Phase(StrEnum):
    DISCOVER = "discover"
    SHORTLIST_REVIEW = "shortlist_review"
    RESEARCH = "research"
    ANALYZE = "analyze"
    REVIEW = "review"
    REPORT_REVIEW = "report_review"
    COMPLETE = "complete"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


class Budget(Contract):
    max_calls: Positive
    used_calls: Count = 0
    reserved_calls: Count = 0
    max_tokens: Count
    used_tokens: Count = 0
    reserved_tokens: Count = 0
    max_cost: Money
    used_cost: Money = Decimal("0")
    reserved_cost: Money = Decimal("0")
    currency: Literal["USD"] = "USD"

    @model_validator(mode="after")
    def within_limits(self):
        for kind in ("calls", "tokens", "cost"):
            if getattr(self, "used_" + kind) + getattr(self, "reserved_" + kind) > getattr(self, "max_" + kind):
                raise ValueError("budget_overcommitted")
        return self


class Approval(Contract):
    request_id: UUID
    decision_id: UUID
    run_id: UUID
    owner_id: UUID
    artifact_hash: Digest
    artifact_version: Positive
    gate: Literal["shortlist", "report"]
    decision: Literal["approve", "reject", "request_changes"]
    decided_at: datetime

    @model_validator(mode="after")
    def aware_time(self):
        if self.decided_at.utcoffset() is None:
            raise ValueError("timezone_required")
        return self


class RunContext(Contract):
    run_id: UUID
    user_id: UUID
    trace_id: UUID
    brief_version: Positive
    run_version: Positive
    versions: Versions
    phase: Phase
    deadline: datetime
    budget: Budget
    mode: Literal["replay", "live"] = "replay"
    live_authorization_id: UUID | None = None
    checkpoint_id: UUID | None = None
    shortlist_hash: Digest | None = None
    shortlist_version: Positive | None = None
    report_hash: Digest | None = None
    report_version: Positive | None = None
    approvals: tuple[Approval, ...] = ()

    @model_validator(mode="after")
    def coherent(self):
        if (self.mode == "live") != (self.live_authorization_id is not None):
            raise ValueError("live_context_requires_authorization_reference")
        if self.deadline.utcoffset() is None:
            raise ValueError("timezone_required")
        for kind in ("shortlist", "report"):
            if (getattr(self, kind + "_hash") is None) != (getattr(self, kind + "_version") is None):
                raise ValueError("artifact_version_pair_required")
        if any(a.run_id != self.run_id or a.owner_id != self.user_id for a in self.approvals):
            raise ValueError("approval_scope_mismatch")
        if len({a.request_id for a in self.approvals}) != len(self.approvals):
            raise ValueError("duplicate_approval_request")
        return self


class Call(Contract):
    operation_id: UUID
    agent: Role
    attempt: Annotated[int, Field(strict=True, ge=1, le=3)] = 1
    timeout_seconds: Annotated[int, Field(strict=True, ge=1, le=60)] = 30


class SearchCall(Call):
    tool: Literal["public.search"]
    query: Text
    limit: Annotated[int, Field(strict=True, ge=1, le=10)] = 5


class RetrieveCall(Call):
    tool: Literal["public.retrieve"]
    url: AnyHttpUrl  # syntactic validation only; gateway must validate DNS/redirects


class ModelCall(Call):
    tool: Literal["model.generate"]
    prompt_id: Text
    input_hash: Digest  # raw prompts are not telemetry
    max_output_tokens: Positive


class NormalizeCall(Call):
    tool: Literal["normalize"]
    observation_ids: tuple[UUID, ...] = Field(min_length=1)


ToolCall = Annotated[SearchCall | RetrieveCall | ModelCall | NormalizeCall, Field(discriminator="tool")]


class Usage(Contract):
    calls: Count
    tokens: Count
    cost: Money


class ToolResult(Contract):
    operation_id: UUID
    attempt: Positive
    status: Literal["ok", "timeout", "rate_limited", "denied", "unavailable", "invalid"]
    payload_ref: UUID | None = None
    error_code: Literal["timeout", "429", "access_denied", "missing", "schema_invalid"] | None = None
    usage: Usage

    @model_validator(mode="after")
    def result_shape(self):
        codes = {"timeout": "timeout", "rate_limited": "429", "denied": "access_denied", "unavailable": "missing", "invalid": "schema_invalid"}
        if self.status == "ok":
            if self.payload_ref is None or self.error_code is not None:
                raise ValueError("success_requires_payload_only")
        elif self.payload_ref is not None or self.error_code != codes[self.status]:
            raise ValueError("failure_requires_matching_code_only")
        return self


class Checkpoint(Contract):
    checkpoint_id: UUID
    run_id: UUID
    owner_id: UUID
    graph_version: Text
    run_version: Positive
    fencing_generation: Positive
    event_sequence: Count
    completed_operations: tuple[UUID, ...]
    state_hash: Digest

    @model_validator(mode="after")
    def unique_operations(self):
        if len(set(self.completed_operations)) != len(self.completed_operations):
            raise ValueError("duplicate_completed_operation")
        return self


class Event(Contract):
    event_id: UUID
    run_id: UUID
    trace_id: UUID
    sequence: Positive
    occurred_at: datetime
    kind: Literal["node.started", "tool.completed", "policy.denied", "checkpoint.saved", "approval.pending", "run.stopped"]
    agent: Role
    operation_id: UUID | None = None
    code: Literal["ok", "denied", "timeout", "budget", "deadline", "cancelled", "pending"]
    versions: Versions

    @model_validator(mode="after")
    def event_shape(self):
        if self.occurred_at.utcoffset() is None:
            raise ValueError("timezone_required")
        if self.kind == "tool.completed" and self.operation_id is None:
            raise ValueError("tool_event_requires_operation")
        return self


class ReplayRecord(Contract):
    label: Literal["DEMO"]
    dataset_version: Text
    ordinal: Positive
    versions: Versions
    call: ToolCall
    result: ToolResult

    @model_validator(mode="after")
    def matching_operation(self):
        if self.call.operation_id != self.result.operation_id or self.call.attempt != self.result.attempt:
            raise ValueError("replay_operation_mismatch")
        if self.dataset_version != self.versions.dataset:
            raise ValueError("replay_dataset_mismatch")
        return self


class FaultConfig(Contract):
    environment: Literal["test", "isolated_demo", "production"]
    enabled: bool = Field(strict=True, default=False)
    authorized: bool = Field(strict=True, default=False)
    label: Literal["DEMO"] = "DEMO"
    fault: Literal["timeout", "blocked", "conflict", "malformed", "restart"] | None = None

    @model_validator(mode="after")
    def isolated(self):
        if self.environment == "production" and (self.enabled or self.fault is not None):
            raise ValueError("production_fault_forbidden")
        if self.enabled != (self.fault is not None) or (self.enabled and not self.authorized):
            raise ValueError("fault_requires_server_authorization")
        return self


class EvidenceLink(Contract):
    source_id: UUID
    excerpt_hash: Digest
    quote: Text
    support: Literal["unreviewed", "supported", "contradicted", "insufficient"] = "unreviewed"
    adjudicator: Literal["golden_human", "human"] | None = None
    rationale: Text | None = None

    @model_validator(mode="after")
    def adjudicated(self):
        if self.support != "unreviewed" and (self.adjudicator is None or self.rationale is None):
            raise ValueError("support_requires_adjudication")
        return self


class Claim(Contract):
    claim_id: UUID
    text: Text
    kind: Literal["fact", "interpretation", "hypothesis", "competitor_marketing_claim"]
    material: bool = Field(strict=True)
    evidence: tuple[EvidenceLink, ...] = ()  # unsupported claims must remain measurable
