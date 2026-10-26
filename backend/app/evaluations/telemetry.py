"""Allowlisted trace projection and explicitly approved LangSmith SDK export.

No raw events, prompts, claims, URLs, exceptions, owners, credentials or arbitrary
metadata can cross this boundary. Export is never called implicitly by a worker.
"""
from datetime import datetime
from typing import Literal
from uuid import UUID, NAMESPACE_URL, uuid5

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.evaluations.contracts import CaseOutcome, EvalSchema
from app.harness.policy import PolicyDenied

NODES = frozenset({"validate", "discover", "research", "normalize", "analyze", "review", "revise", "save"})
TOOLS = frozenset({"public.search", "public.retrieve", "public.news", "model.generate"})


class SafeStep(EvalSchema):
    ordinal: int = Field(ge=1)
    name: Literal["validate", "discover", "research", "normalize", "analyze", "review", "revise", "save", "public.search", "public.retrieve", "public.news", "model.generate"]
    kind: Literal["node", "tool"]
    attempt: int = Field(ge=1, le=3, default=1)
    occurred_at: datetime


class SafeTrace(EvalSchema):
    schema_version: Literal["sanitized-trace-1.0"] = "sanitized-trace-1.0"
    label: Literal["DEMO"] = "DEMO"
    trace_id: UUID
    case_id: str = Field(pattern=r"^D(?:0[1-9]|1[0-7])$")
    dataset_version: Literal["lather-golden-v1"] = "lather-golden-v1"
    graph_version: Literal["workflow-1.2"] = "workflow-1.2"
    provider: Literal["none"] = "none"
    model: Literal["none"] = "none"
    prompt_version: Literal["DEMO-frozen-analysis-1.0"] = "DEMO-frozen-analysis-1.0"
    passed: bool
    latency_ms: int = Field(ge=0)
    started_at: datetime
    ended_at: datetime
    provider_tokens: Literal[0] = 0
    provider_calls: Literal[0] = 0
    cost_usd: Literal["0"] = "0"
    steps: tuple[SafeStep, ...] = Field(max_length=1000)


def sanitize(outcome: CaseOutcome, events: list[dict], batch_id: UUID) -> SafeTrace:
    if outcome.measurement.provider_cost_usd != 0:
        raise PolicyDenied("nonzero_provider_cost_in_recorded_trace")
    steps: list[SafeStep] = []
    for event in events:
        data = event.get("data", {})
        name = None
        kind: Literal["node", "tool"] | None = None
        if event["kind"] == "workflow.node" and data.get("node") in NODES:
            name, kind = data["node"], "node"
        if event["kind"] == "tool.completed" and data.get("tool") in TOOLS:
            name, kind = data["tool"], "tool"
        if event["kind"] == "model.replay_validated":
            name, kind = "model.generate", "tool"
        if name and kind is not None:
            steps.append(SafeStep(ordinal=len(steps) + 1, name=name, kind=kind, attempt=data.get("attempt", 1), occurred_at=event["created_at"]))
    return SafeTrace(trace_id=uuid5(NAMESPACE_URL, str(batch_id) + ":" + outcome.case_id), case_id=outcome.case_id,
        passed=outcome.passed, latency_ms=outcome.measurement.latency_ms, started_at=outcome.measurement.started_at,
        ended_at=outcome.measurement.ended_at, steps=tuple(steps))


class ExportSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LATHER_TRACE_", extra="ignore", hide_input_in_errors=True)
    enabled: bool = False
    export_approved: bool = False
    api_key: SecretStr | None = None
    existing_project_id: UUID | None = None
    max_runs: int = Field(default=0, ge=0, le=10000)
    endpoint: Literal["https://api.smith.langchain.com", "https://eu.api.smith.langchain.com"] = "https://api.smith.langchain.com"

    @model_validator(mode="after")
    def explicit_consent(self):
        if self.enabled and (not self.export_approved or self.api_key is None or self.existing_project_id is None or self.max_runs < 1):
            raise ValueError("trace_export_requires_approval_key_existing_project_and_run_cap")
        return self


def export_langsmith(trace: SafeTrace, settings: ExportSettings, *, client=None):
    settings = ExportSettings.model_validate(settings.model_dump())
    if not settings.enabled or not settings.export_approved or settings.api_key is None or settings.existing_project_id is None:
        raise PolicyDenied("langsmith_export_not_approved")
    # Validate again: model_copy and untrusted JSON must not bypass the allowlist.
    trace = SafeTrace.model_validate(trace.model_dump())
    if 1 + len(trace.steps) > settings.max_runs:
        raise PolicyDenied("langsmith_approved_run_cap_exceeded")
    if client is None:
        from langsmith import Client
        client = Client(api_url=settings.endpoint, api_key=settings.api_key.get_secret_value(), auto_batch_tracing=False,
            timeout_ms=5000, omit_traced_runtime_info=True, disable_prompt_cache=True, cache=False,
            hide_metadata=lambda _: {})
    client.create_run(id=trace.trace_id, trace_id=trace.trace_id, session_id=settings.existing_project_id,
        name="Lather Lens " + trace.case_id, run_type="chain", start_time=trace.started_at, inputs={"label": "DEMO", "case_id": trace.case_id,
            "dataset_version": trace.dataset_version, "graph_version": trace.graph_version, "provider": trace.provider, "model": trace.model, "prompt_version": trace.prompt_version},
        outputs={"passed": trace.passed, "latency_ms": trace.latency_ms, "provider_calls": 0, "provider_tokens": 0, "cost_usd": "0"})
    for step in trace.steps:
        identifier = uuid5(trace.trace_id, str(step.ordinal))
        client.create_run(id=identifier, trace_id=trace.trace_id, parent_run_id=trace.trace_id, session_id=settings.existing_project_id,
            name=step.name, run_type="tool" if step.kind == "tool" else "chain", start_time=step.occurred_at,
            inputs={"label": "DEMO", "ordinal": step.ordinal, "attempt": step.attempt, "timing": "persisted_completion_event_not_measured_span"}, outputs={"recorded": True})
        client.update_run(identifier, end_time=step.occurred_at)
    client.update_run(trace.trace_id, end_time=trace.ended_at)
