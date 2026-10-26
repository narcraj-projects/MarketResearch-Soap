from decimal import Decimal
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

CaseID = Literal["D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08", "D09", "D10", "D11", "D12", "D13", "D14", "D15", "D16", "D17"]
FAILURE_COHORT = ("D04", "D05", "D06", "D10", "D12")


class EvalSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class EvalPlan(EvalSchema):
    schema_version: Literal["golden-plan-1.0"] = "golden-plan-1.0"
    label: Literal["DEMO"] = "DEMO"
    dataset_version: Literal["lather-golden-v1"] = "lather-golden-v1"
    case_id: CaseID
    manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class GoldenCase(EvalSchema):
    id: CaseID
    label: Literal["DEMO"]
    title: str
    mode: Literal["graph", "rate_limit_component", "history_component"]
    search: str
    web: str
    expected_status: Literal["complete", "partial", "cancelled", "report_review", "component_complete"]
    expected_competitors: int | None = Field(ge=0, le=3)
    expected_units: dict[str, tuple[str | None, ...]] = {}
    checks: tuple[str, ...] = Field(min_length=1)
    acceptance: tuple[str, ...]
    limitations: str


class Grade(EvalSchema):
    grader_version: Literal["graders-1.0"] = "graders-1.0"
    name: str
    passed: bool
    critical: bool = True
    reason: str


class RunMeasurement(EvalSchema):
    started_at: datetime
    ended_at: datetime
    latency_ms: int = Field(ge=0)
    latency_scope: Literal["local_recorded_execution"] = "local_recorded_execution"
    completed_calls: int | None = Field(ge=0)
    reserved_calls: int | None = Field(ge=0)
    model_replay_attempts: int = Field(ge=0)
    provider_calls: Literal[0] = 0
    provider_tokens: Literal[0] = 0
    token_scope: Literal["no_provider_called_not_a_token_estimate"] = "no_provider_called_not_a_token_estimate"
    provider_cost_usd: Decimal = Field(ge=0, allow_inf_nan=False)
    cost_upper_bound_usd: Decimal | None = Field(ge=0, allow_inf_nan=False)
    virtual_retry_delays_seconds: tuple[float, ...] = ()

    @model_validator(mode="after")
    def truthful_timing(self):
        if self.started_at.utcoffset() is None or self.ended_at.utcoffset() is None or self.ended_at < self.started_at:
            raise ValueError("aware_nondecreasing_measurement_time_required")
        if self.provider_cost_usd != 0:
            raise ValueError("recorded_suite_cannot_report_provider_billing")
        return self


class CaseOutcome(EvalSchema):
    label: Literal["DEMO"] = "DEMO"
    case_id: CaseID
    run_id: UUID | None
    status: str
    grades: tuple[Grade, ...]
    measurement: RunMeasurement
    signature: dict
    diagnostics: dict

    @property
    def passed(self) -> bool:
        return bool(self.grades) and all(grade.passed for grade in self.grades)
