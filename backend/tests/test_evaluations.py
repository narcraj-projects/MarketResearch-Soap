"""EG: grading, dataset, privacy and baseline negatives. All examples are DEMO."""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.evaluations import baseline
from app.evaluations.contracts import CaseOutcome, RunMeasurement
from app.evaluations.dataset import Dataset, require_evaluation
from app.evaluations.graders import grade_math, grade_tools, grade_trajectory, failure_gate, result
from app.evaluations.review import CHECKS, SupportReview, coverage, owner_gate
from app.evaluations.telemetry import ExportSettings, SafeTrace, sanitize, export_langsmith
from app.harness.policy import PolicyDenied


def measured():
    at = datetime(2026, 10, 25, tzinfo=timezone.utc)
    return RunMeasurement(started_at=at, ended_at=at, latency_ms=1, completed_calls=1, reserved_calls=0,
        model_replay_attempts=0, provider_cost_usd=Decimal(0), cost_upper_bound_usd=Decimal(0))


def outcome(case="D01", passed=True):
    return CaseOutcome(case_id=case, run_id=UUID(int=1), status="complete", grades=(result("safety", passed, "DEMO"),),
        measurement=measured(), signature={"nodes": ["validate", "discover"]}, diagnostics={"DEMO_private": "DEMO_SECRET_CANARY"})


def test_eg01_predeclared_17_cases_cohorts_pins_and_unknown_paths():
    suite = Dataset()
    assert len(suite.cases) == 17
    assert suite.read("cases.json")["failure_cohort"] == ["D04", "D05", "D06", "D10", "D12"]
    assert len(suite.read("cases.json")["owner_report_cohort"]) == 5
    for case in suite.cases:
        assert suite.validate_plan(suite.plan(case.id)) == case
    with pytest.raises(ValueError):
        suite.read("../scout-v1/SC01-clean.json")
    with pytest.raises(PolicyDenied):
        suite.case("D99")
    with pytest.raises(PolicyDenied):
        suite.validate_plan(suite.plan("D01").model_copy(update={"manifest_hash": "0" * 64}))


@pytest.mark.parametrize("environment", ["local", "production"])
def test_eg02_live_or_production_evaluation_is_rejected(environment):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment=environment, evaluations_enabled=True)
    with pytest.raises(PolicyDenied):
        require_evaluation(Settings(_env_file=None, environment=environment))


@pytest.mark.parametrize("price,weight,unit,sku,reason,expected", [
    ("125", "75", "166.66666667", "DEMO-SKU", None, True),
    ("0", "100", "0", "DEMO-SKU", None, True),
    ("125", "75", "167", "DEMO-SKU", None, False),
    ("125", None, None, "DEMO-SKU", "missing_weight", True),
    ("125", None, "125", "DEMO-SKU", None, False),
    ("125", "100", "125", None, None, False),
])
def test_eg03_independent_decimal_and_null_arithmetic(price, weight, unit, sku, reason, expected):
    row = {"amount": price, "total_weight_g": weight, "unit_price_100g": unit, "sku": sku, "unavailable_reason": reason}
    assert grade_math([row], {}).passed is expected


def test_eg04_permission_and_trajectory_mutations_cannot_pass():
    bad = [{"kind": "tool.reserved", "sequence": 1, "data": {"agent": "researcher", "tool": "publish"}}]
    assert not grade_tools(bad, [], 10)[0].passed
    assert not grade_trajectory(bad, "complete", [], []).passed
    before_approval = [{"kind": "tool.reserved", "sequence": 1, "data": {"agent": "researcher", "tool": "public.retrieve"}}]
    assert not grade_trajectory(before_approval, "report_review", [], []).passed
    forged = [{"kind": "approval.decided", "sequence": 1, "data": {"gate": "report", "decision_id": "DEMO-forged"}}, {"kind": "run.completed", "sequence": 2, "data": {}}]
    assert not grade_trajectory(forged, "complete", [], []).passed


def test_eg05_failure_denominator_fixed_and_missing_cases_unknown():
    assert failure_gate([outcome("D04")])["status"] == "not_evaluated"
    cases = [outcome(case, case != "D10") for case in ["D04", "D05", "D06", "D10", "D12"]]
    assert failure_gate(cases)["handled"] == 4 and failure_gate(cases)["denominator"] == 5
    # Aggregate recovery threshold does not turn the failing critical case into a CI pass.
    assert not all(case.passed for case in cases)


def test_eg06_baseline_detects_mutations_versions_missing_cases_and_budgets(tmp_path):
    first = baseline.snapshot([outcome()], "a" * 64)
    path = tmp_path / "baseline.json"
    baseline.record(path, first)
    assert not baseline.compare(path, first)["critical_regression"]
    with pytest.raises(PolicyDenied):
        baseline.record(path, first)
    for field, value in [("manifest_hash", "b" * 64), ("cases", {}), ("grader_version", "changed")]:
        candidate = deepcopy(first)
        candidate[field] = value
        assert baseline.compare(path, candidate)["critical_regression"]
    candidate = deepcopy(first)
    candidate["cases"]["D01"]["signature"]["nodes"] = ["save"]
    assert baseline.compare(path, candidate)["critical_regression"]
    assert baseline.compare(path, first)["release_baseline_reviewed"] is False


def test_eg07_trace_allowlist_drops_all_raw_research_and_owner_data():
    event = {"kind": "tool.completed", "created_at": measured().started_at, "data": {"tool": "public.search", "attempt": 1,
        "query": "DEMO_SECRET_CANARY", "api_key": "DEMO_SECRET_CANARY", "owner_id": "DEMO_SECRET_CANARY", "url": "https://private.invalid/DEMO_SECRET_CANARY"}}
    trace = sanitize(outcome(), [event], uuid4())
    encoded = trace.model_dump_json()
    assert "DEMO_SECRET_CANARY" not in encoded and "owner_id" not in encoded and len(trace.steps) == 1
    with pytest.raises(ValidationError):
        SafeTrace.model_validate(trace.model_dump() | {"api_key": "DEMO_SECRET_CANARY"})
    with pytest.raises(PolicyDenied):
        export_langsmith(trace, ExportSettings())
    with pytest.raises(ValidationError):
        ExportSettings(enabled=True)


def test_eg08_actual_langsmith_sdk_receives_only_sanitized_payload_without_network(monkeypatch):
    from langsmith import Client
    import requests
    captured = []
    class Session(requests.Session):
        def request(self, method, url, **kwargs):
            raw = kwargs.get("data", b"")
            captured.append(raw.decode() if isinstance(raw, bytes) else str(raw))
            response = requests.Response()
            response.status_code = 200
            response._content = b'{}'
            response.url = url
            return response
    monkeypatch.setenv("LANGSMITH_METADATA", '{"secret":"DEMO_SECRET_CANARY"}')
    client = Client(api_url="https://api.smith.langchain.com", api_key="DEMO-test-only", session=Session(), auto_batch_tracing=False,
        omit_traced_runtime_info=True, hide_metadata=lambda _: {}, info={})
    trace = sanitize(outcome(), [], uuid4())
    settings = ExportSettings(enabled=True, export_approved=True, api_key="DEMO-test-only", existing_project_id=UUID(int=42), max_runs=2)
    export_langsmith(trace, settings, client=client)
    assert captured and "DEMO_SECRET_CANARY" not in "".join(captured)
    assert "D01" in "".join(captured)
    client.close()


def test_eg09_presence_never_becomes_support_and_untrusted_fixture_labels_cannot_count():
    owner = UUID(int=11)
    packet = {"run_id": str(UUID(int=1)), "report_id": str(UUID(int=2)), "report_hash": "a" * 64,
        "claims": [{"claim_id": str(UUID(int=3)), "statement_hash": "b" * 64}]}
    data = {"schema_version": "human-review-1.0", "kind": "claim_support", "purpose": "human_review", "reviewer_id": str(owner),
        "report_id": packet["report_id"], "report_hash": packet["report_hash"], "claim_id": packet["claims"][0]["claim_id"],
        "statement_hash": "b" * 64, "disposition": "supported"}
    receipt = {"owner_id": owner, "run_id": UUID(int=1), "data": data}
    assert coverage(packet, [], (owner,))["support_coverage"] is None
    assert coverage(packet, [data], (owner,))["support_coverage"] is None  # bare self-labelled JSON is not a receipt
    assert coverage(packet, [receipt], ())["support_coverage"] is None
    assert coverage(packet, [receipt], (owner,))["support_coverage"] == 1
    for key, value in [("purpose", "demo_fixture"), ("report_hash", "c" * 64), ("statement_hash", "c" * 64)]:
        assert coverage(packet, [receipt | {"data": data | {key: value}}], (owner,))["support_coverage"] is None
    contradicted = receipt | {"data": data | {"disposition": "contradicted"}}
    assert coverage(packet, [contradicted], (owner,))["status"] == "failed"


def test_eg10_owner_gate_needs_five_distinct_trusted_human_report_ratings():
    owner = UUID(int=11)
    cohort = [{"run_id": str(UUID(int=i)), "report_id": str(UUID(int=i + 10)), "report_hash": str(i) * 64} for i in range(1, 6)]
    ratings = [{"owner_id": owner, "data": {"schema_version": "human-review-1.0", "kind": "owner_usefulness", "purpose": "human_review", "reviewer_id": str(owner),
        "report_id": row["report_id"], "report_hash": row["report_hash"], "useful": index < 4}} for index, row in enumerate(cohort)]
    assert owner_gate(cohort, [], (owner,))["useful"] is None
    assert owner_gate(cohort, ratings[:4], (owner,))["status"] == "not_evaluated"
    assert owner_gate(cohort, ratings, (owner,))["status"] == "passed"
    assert owner_gate(cohort, ratings, ())["status"] == "not_evaluated"
    assert owner_gate(cohort + [cohort[0]], ratings, (owner,))["status"] == "not_evaluated"


def test_eg11_human_submission_cannot_self_assign_reviewer_identity_or_skip_scope_checks():
    body = dict(report_id=UUID(int=1), report_hash="a" * 64, claim_id=UUID(int=2), statement_hash="b" * 64,
        disposition="supported", source_ids=(UUID(int=3),), checks_completed=CHECKS, rationale="DEMO manual rationale", purpose="demo_fixture",
        attestation="I personally reviewed every factual component and its evidence")
    SupportReview.model_validate(body)
    for update in ({"reviewer_id": str(UUID(int=4))}, {"checks_completed": []}, {"source_ids": []}):
        with pytest.raises(ValidationError):
            SupportReview.model_validate(body | update)


def test_eg12_unmeasured_semantics_and_owner_gates_block_release_even_with_green_ci():
    from app.evaluations.acceptance import gates, release_blockers
    cases = [outcome(f"D{i:02}") for i in range(1, 18)]
    measured_gates = gates(cases, {}, {"status": "not_evaluated", "rated": 0, "useful": None})
    assert measured_gates["A05"]["handled"] == 5
    assert measured_gates["A02"]["status"] == measured_gates["A04"]["status"] == "not_evaluated"
    assert release_blockers(measured_gates, {"critical_regression": False, "release_baseline_reviewed": False})
    failed = [outcome(f"D{i:02}", passed=i != 13) for i in range(1, 18)]
    assert gates(failed, {}, {"status": "not_evaluated"})["A06"]["status"] == "failed"
