"""Trusted server-only scenario policy and pinned DEMO fixtures; no arbitrary fault payloads."""
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.config import Settings
from .policy import PolicyDenied
from .search import ReplayMismatch

Scenario = Literal["timeout", "rate_limit", "empty_results", "inaccessible_page", "conflicting_price", "missing_weight", "malformed_json", "reviewer_rejection", "interrupted_worker"]
FOLDER = Path(__file__).resolve().parents[2] / "evaluations/fixtures/chaos-v1"


class ChaosSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class ChaosCreate(ChaosSchema):
    scenario: Scenario


class ChaosPlan(ChaosSchema):
    schema_version: Literal["chaos-1.0"] = "chaos-1.0"
    label: Literal["DEMO"] = "DEMO"
    scenario: Scenario
    dataset_version: Literal["chaos-demo-v1"] = "chaos-demo-v1"
    manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class ChaosChoice(ChaosSchema):
    scenario: Scenario
    title: str


class ChaosCapabilities(ChaosSchema):
    enabled: bool
    label: Literal["DEMO"] = "DEMO"
    scenarios: list[ChaosChoice]


class ChaosQueued(ChaosSchema):
    label: Literal["DEMO"] = "DEMO"
    run_id: UUID
    scenario: Scenario
    worker_required: Literal[True] = True


def require_test_mode(settings: Settings):
    if settings.environment != "test" or not settings.chaos_enabled or settings.mode != "replay" or settings.external_calls_enabled:
        raise PolicyDenied("chaos_disabled")


def require_isolated_engine(engine):
    if engine is None or engine.url.host != "127.0.0.1" or engine.url.port != 57422:
        raise PolicyDenied("dedicated_local_chaos_database_required")


def read_fixture(name: str) -> dict:
    # Name comes only from the checked-in scenario registry, never a user path.
    if Path(name).name != name:
        raise ReplayMismatch("fixture_path_denied")
    manifest = json.loads((FOLDER / "manifest.json").read_text(encoding="utf8"))
    raw = (FOLDER / name).read_bytes()
    if manifest.get("dataset_version") != "chaos-demo-v1" or manifest["sha256"].get(name) != sha256(raw).hexdigest():
        raise ReplayMismatch("chaos_fixture_hash_mismatch")
    value = json.loads(raw)
    if value.get("label") != "DEMO":
        raise ReplayMismatch("demo_label_required")
    return value


def plan(scenario: Scenario) -> ChaosPlan:
    registry = read_fixture("scenarios.json")
    if scenario not in {row["scenario"] for row in registry["scenarios"]}:
        raise PolicyDenied("unknown_scenario")
    return ChaosPlan(scenario=scenario, manifest_hash=sha256((FOLDER / "manifest.json").read_bytes()).hexdigest())


def scenario_files(value: ChaosPlan, settings: Settings) -> dict:
    require_test_mode(settings)
    if value != plan(value.scenario):
        raise PolicyDenied("chaos_plan_version_mismatch")
    selected = next(row for row in read_fixture("scenarios.json")["scenarios"] if row["scenario"] == value.scenario)
    for key in ("search", "web"):
        read_fixture(selected[key])
    return selected
