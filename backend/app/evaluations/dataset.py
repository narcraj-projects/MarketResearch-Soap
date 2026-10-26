from hashlib import sha256
import json
from pathlib import Path

from app.config import Settings
from app.evaluations.contracts import EvalPlan, FAILURE_COHORT, GoldenCase
from app.harness.chaos import require_isolated_engine
from app.harness.policy import PolicyDenied
from app.harness.search import ReplayMismatch

FOLDER = Path(__file__).resolve().parents[2] / "evaluations/fixtures/golden-v1"
REPO = Path(__file__).resolve().parents[3]


def require_evaluation(settings: Settings, engine=None):
    if settings.environment != "test" or not settings.evaluations_enabled or settings.mode != "replay" or settings.external_calls_enabled:
        raise PolicyDenied("evaluation_disabled")
    if engine is not None:
        require_isolated_engine(engine)


class Dataset:
    def __init__(self):
        self.manifest = json.loads((FOLDER / "manifest.json").read_text(encoding="utf8"))
        if self.manifest.get("dataset_version") != "lather-golden-v1" or self.manifest.get("label") != "DEMO":
            raise ReplayMismatch("golden_manifest_version_mismatch")
        for path, expected in self.manifest.get("references", {}).items():
            resolved = (REPO / path).resolve()
            if not resolved.is_relative_to(REPO) or sha256(resolved.read_bytes()).hexdigest() != expected:
                raise ReplayMismatch("golden_reference_hash_mismatch")
        self.manifest_hash = sha256((FOLDER / "manifest.json").read_bytes()).hexdigest()
        registry = self.read("cases.json")
        self.cases = tuple(GoldenCase.model_validate(row) for row in registry["cases"])
        if [case.id for case in self.cases] != [f"D{i:02}" for i in range(1, 18)] or tuple(registry["failure_cohort"]) != FAILURE_COHORT:
            raise ReplayMismatch("golden_case_or_failure_cohort_mismatch")
        for case in self.cases:
            self.read(case.search)
            self.read(case.web)

    def read(self, name: str) -> dict:
        if Path(name).name != name:
            raise ReplayMismatch("golden_path_denied")
        raw = (FOLDER / name).read_bytes()
        if self.manifest["sha256"].get(name) != sha256(raw).hexdigest():
            raise ReplayMismatch("golden_fixture_hash_mismatch")
        value = json.loads(raw)
        if value.get("label") != "DEMO":
            raise ReplayMismatch("golden_demo_label_required")
        return value

    def case(self, identifier: str) -> GoldenCase:
        found = next((case for case in self.cases if case.id == identifier), None)
        if found is None:
            raise PolicyDenied("golden_case_not_allowlisted")
        return found

    def plan(self, identifier: str) -> EvalPlan:
        return EvalPlan(case_id=self.case(identifier).id, manifest_hash=self.manifest_hash)

    def validate_plan(self, value: EvalPlan) -> GoldenCase:
        if value != self.plan(value.case_id):
            raise PolicyDenied("evaluation_plan_version_mismatch")
        return self.case(value.case_id)
