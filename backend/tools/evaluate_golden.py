"""Execute predeclared DEMO evals. Baseline writes/export are separate explicit actions."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import importlib.metadata
import json
from pathlib import Path
from time import perf_counter
import traceback
from uuid import UUID, uuid4

from langsmith import tracing_context
from sqlalchemy import create_engine

from app import models as m
from app.config import Settings
from app.evaluations import baseline
from app.evaluations.contracts import CaseOutcome, RunMeasurement
from app.evaluations.dataset import Dataset, require_evaluation
from app.evaluations.graders import result
from app.evaluations.acceptance import gates as acceptance_gates, release_blockers
from app.evaluations.review import packet, coverage, owner_gate
from app.evaluations.runner import GoldenRunner
from app.evaluations.telemetry import sanitize
from app.repository import owner_transaction
from tools.workflow_demo import local_config


def main():
    parser = argparse.ArgumentParser(description="Dedicated local, zero-provider-spend recorded evaluation")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--record-proposed-baseline", type=Path)
    parser.add_argument("--case", choices=[f"D{i:02}" for i in range(1, 18)], action="append")
    parser.add_argument("--release-check", action="store_true")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if args.live:
        raise SystemExit("Paid live evaluation is unavailable here; use the separately approved model benchmark runbook.")
    settings = Settings()
    require_evaluation(settings)
    config = local_config()
    engine = create_engine(config["runtime_url"], hide_parameters=True)
    runner = GoldenRunner(engine, UUID(config["users"][0]["id"]), UUID(config["users"][1]["id"]), settings)
    dataset = Dataset()
    batch = uuid4()
    outcomes, traces, packets, owner_cohort = [], [], [], []
    try:
        with tracing_context(enabled=False):
            for case in dataset.cases:
                if args.case and case.id not in args.case:
                    continue
                began, started = datetime.now(timezone.utc), perf_counter()
                try:
                    outcome = runner.execute(case)
                except Exception as error:
                    # Never log arbitrary exception messages/SQL/parameters. Unknown
                    # accounting is null rather than an invented zero after failure.
                    frames = [{"file": Path(frame.filename).name, "line": frame.lineno} for frame in traceback.extract_tb(error.__traceback__) if "site-packages" not in frame.filename]
                    outcome = CaseOutcome(case_id=case.id, run_id=None, status="execution_failed", grades=(result("execution", False, type(error).__name__),),
                        measurement=RunMeasurement(started_at=began, ended_at=datetime.now(timezone.utc), latency_ms=round((perf_counter() - started) * 1000),
                            completed_calls=None, reserved_calls=None, model_replay_attempts=0, provider_cost_usd=Decimal(0), cost_upper_bound_usd=None),
                        signature={"status": "execution_failed"}, diagnostics={"exception_class": type(error).__name__, "code_locations": frames})
                outcomes.append(outcome)
                traces.append(sanitize(outcome, runner.events.get(case.id, []), batch).model_dump(mode="json"))
                print(f"{'PASS' if outcome.passed else 'FAIL'} DEMO {case.id}: {outcome.status}; graders {sum(g.passed for g in outcome.grades)}/{len(outcome.grades)}", flush=True)
                if outcome.run_id and outcome.status == "complete":
                    with owner_transaction(engine, runner.owner) as repo:
                        report = repo.report(outcome.run_id)
                        current_packet = packet(repo, outcome.run_id, report["id"])
                        receipts = repo.list(m.evaluation_results, outcome.run_id, limit=10000)
                        current_packet["trusted_support_measurement"] = coverage(current_packet, receipts, settings.trusted_reviewer_ids)
                        packets.append(current_packet)
                        if case.id in dataset.read("cases.json")["owner_report_cohort"]:
                            owner_cohort.append({"case_id": case.id, "run_id": str(outcome.run_id), "report_id": str(report["id"]), "report_hash": report["content_hash"], "label": "DEMO"})
        candidate = baseline.snapshot(outcomes, dataset.manifest_hash)
        if args.record_proposed_baseline:
            if args.case:
                raise ValueError("baseline_requires_full_predeclared_suite")
            baseline.record(args.record_proposed_baseline, candidate)
        regression = baseline.compare(args.baseline, candidate) if args.baseline else {"status": "not_compared", "critical_regression": None}
        with owner_transaction(engine, runner.owner) as repo:
            ratings = repo.list(m.evaluation_results, limit=10000)
        useful = owner_gate(owner_cohort, ratings, settings.business_owner_ids)
        support = {row["report_id"]: row["trusted_support_measurement"] for row in packets}
        gates = acceptance_gates(outcomes, support, useful)
        complete = len(outcomes) == 17
        ci_ok = complete and all(row.passed for row in outcomes) and regression.get("critical_regression") is not True
        report = {"schema_version": "evaluation-report-1.0", "label": "DEMO", "dataset_version": "lather-golden-v1", "manifest_hash": dataset.manifest_hash,
            "versions": {"graph": "workflow-1.2", "provider": "none", "model": "none", "prompt": "DEMO-frozen-analysis-1.0", "tools": ["tavily-search-1.0", "public-research-1.0", "model-replay-1.0"], "graders": "graders-1.0", "langsmith_sdk": importlib.metadata.version("langsmith")},
            "sample_size": len(outcomes), "passed": sum(row.passed for row in outcomes), "ci_deterministic_pass": ci_ok,
            "release_ready": False, "release_blockers": release_blockers(gates, regression),
            "gates": gates, "regression": regression, "owner_report_cohort": owner_cohort,
            "actual_provider_calls": 0, "actual_provider_tokens": 0, "provider_cost_usd": "0", "langsmith_remote_exports": 0,
            "model_fixture_origin": "synthetic frozen rule projections, not captured provider responses", "cases": [row.model_dump(mode="json") for row in outcomes]}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
        args.output.with_suffix(".traces.json").write_text(json.dumps({"schema_version": "sanitized-trace-batch-1.0", "label": "DEMO", "remote_exports": 0, "traces": traces}, indent=2) + "\n", encoding="utf8")
        # Review packets contain private report text/excerpts: keep them local and
        # do not include them in traces or commit/CI-upload public artifacts.
        root = Path(__file__).resolve().parents[2]
        if not args.case:
            (root / ".cache/evaluation-review-packets.json").write_text(json.dumps({"label": "DEMO", "packets": packets, "owner_cohort": owner_cohort}, indent=2) + "\n", encoding="utf8")
        print(f"DEMO evals: {report['passed']}/{len(outcomes)} passed; failure cohort {gates['A05']['handled']}/5; owner ratings {useful['rated']}/5; support unmeasured; no provider calls/remote export")
        if args.release_check:
            raise SystemExit(2)  # Missing real/human acceptance is never a release pass.
        if not ci_ok and not args.case:
            raise SystemExit(1)
        if args.case and not all(row.passed for row in outcomes):
            raise SystemExit(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit(f"Golden evaluation command failed ({type(error).__name__}); input/credential details suppressed.") from None
