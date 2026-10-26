"""Run all nine isolated DEMO trajectories and save measured, credential-free evidence."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from uuid import UUID, uuid4

from sqlalchemy import create_engine, select

from app import models as m
from app.api_schemas import DecisionCreate
from app.config import Settings
from app.harness.chaos import ChaosCreate, plan, read_fixture, require_test_mode
from app.repository import owner_transaction
from app.services.chaos import create_demo
from app.worker import run_once
from tools.workflow_demo import local_config


def main():
    parser = argparse.ArgumentParser(description="Dedicated local recorded chaos regression; no paid providers")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    settings = Settings()
    require_test_mode(settings)
    cfg = local_config()
    engine = create_engine(cfg["runtime_url"], hide_parameters=True)
    owner = UUID(cfg["users"][0]["id"])
    root = Path(__file__).resolve().parents[2]
    results, ids = [], {}

    def approve_shortlist(run_id):
        # Explicit scripted DEMO owner decision; never an automatic approval in the worker.
        with owner_transaction(engine, owner) as repo:
            run = repo.get(m.runs, run_id)
            pending = repo.conn.execute(select(m.approval_requests).where(m.approval_requests.c.run_id == run_id,
                m.approval_requests.c.owner_id == owner, m.approval_requests.c.gate == "shortlist", m.approval_requests.c.state == "pending")).mappings().one()
            repo.decide(run_id, "shortlist", DecisionCreate(request_id=pending["id"], artifact_version=pending["artifact_version"],
                artifact_hash=pending["artifact_hash"], expected_run_version=run["version"], decision="approve"), str(uuid4()))

    def process(run_id):
        value = subprocess.run([sys.executable, "-m", "tools.chaos_worker", "--run-id", str(run_id), "--lease-seconds", "2"],
            env=dict(os.environ), capture_output=True, text=True, timeout=60)
        if value.returncode not in {0, 23}:
            raise ValueError("local_worker_failed")
        return value.returncode, json.loads(value.stdout) if value.returncode == 0 else None

    try:
        for choice in read_fixture("scenarios.json")["scenarios"]:
            scenario = choice["scenario"]
            with owner_transaction(engine, owner) as repo:
                created = create_demo(repo, ChaosCreate(scenario=scenario), str(uuid4()), settings)
            run_id = UUID(created["run_id"])
            ids[scenario] = str(run_id)
            if scenario == "interrupted_worker":
                exit_code, first = process(run_id)
                assert exit_code == 0
            else:
                first = run_once(engine, owner, run_id=run_id, settings=settings)
            calls = [first]
            preserved = None
            if scenario != "empty_results":
                assert calls[-1]["state"] == "approval_pending"
                approve_shortlist(run_id)
                if scenario == "interrupted_worker":
                    exit_code, _ = process(run_id)
                    assert exit_code == 23
                    with owner_transaction(engine, owner) as repo:
                        saved = repo.list(m.research_tasks, run_id)
                        hashes = {str(row["id"]): row["content_hash"] for row in repo.list(m.sources, run_id, limit=1000)}
                        assert len(saved) == 1
                    time.sleep(2.2)  # Actual dedicated DB lease expiry, not a synthetic recovery event.
                    exit_code, resumed = process(run_id)
                    assert exit_code == 0 and resumed["recorded_web_dispatches"] == 6
                    calls.append(resumed)
                    with owner_transaction(engine, owner) as repo:
                        after = repo.list(m.research_tasks, run_id)
                        current = {str(row["id"]): row["content_hash"] for row in repo.list(m.sources, run_id, limit=1000)}
                        preserved = next(row for row in after if row["id"] == saved[0]["id"]) == saved[0] and all(current[key] == value for key, value in hashes.items())
                        assert preserved
                else:
                    calls.append(run_once(engine, owner, run_id=run_id, settings=settings))
                # No report decision: demonstrate that replay/recovery cannot bypass final approval.
                if scenario == "interrupted_worker":
                    exit_code, pending = process(run_id)
                    assert exit_code == 0
                else:
                    pending = run_once(engine, owner, run_id=run_id, settings=settings)
                assert pending["state"] == "idle"  # The durable pending approval has not queued another job.
                calls.append(pending)
            with owner_transaction(engine, owner) as repo:
                run = repo.get(m.runs, run_id)
                events = repo.list(m.events, run_id, limit=10000)
                attempts = repo.list(m.tool_attempts, run_id, limit=1000)
                tasks = repo.list(m.research_tasks, run_id)
                reports = repo.list(m.reports, run_id)
                usage = repo.list(m.usage, run_id, limit=1000)
                expected = "partial" if scenario == "empty_results" else "report_review"
                assert run["status"] == expected and all(row["attempt"] <= 3 for row in attempts)
                assert all(item["actual_external_calls"] == 0 for item in calls)
                report_requests = {row["id"] for row in repo.list(m.approval_requests, run_id) if row["gate"] == "report"}
                assert not any(row["request_id"] in report_requests for row in repo.list(m.approval_decisions, run_id))
                results.append({"label": "DEMO", "scenario": scenario, "run_id": str(run_id), "expected_status": expected, "actual_status": run["status"],
                    "plan": plan(scenario).model_dump(mode="json"), "graph_version": "workflow-1.2", "outcome": "pass", "completed_lanes": len(tasks),
                    "report_versions": len(reports), "final_approval": "pending" if reports else "not_reached", "preserved_lane_and_source_hashes": preserved,
                    "attempts": len(attempts), "max_attempt": max((row["attempt"] for row in attempts), default=0),
                    "event_counts": {kind: sum(row["kind"] == kind for row in events) for kind in sorted({row["kind"] for row in events})},
                    "actual_external_calls": sum(item["actual_external_calls"] for item in calls), "actual_model_tokens": sum(row["tokens"] for row in usage),
                    "cost_usd": str(sum(row["cost_usd"] for row in usage)), "genuine_support_coverage": None,
                    "worker_passes": calls})
            print(f"PASS DEMO {scenario}: {expected}; final approval not bypassed", flush=True)
        (root / ".cache/chaos-ui.json").write_text(json.dumps(ids, indent=2) + "\n", encoding="utf8")
        output = args.output if args.output is not None else root / ".cache/current-chaos-results.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"label": "DEMO", "scope": "nine controlled recorded scenarios, not the predeclared A05 cohort or a live model benchmark",
            "model_response_origin": "synthetic frozen rule-output projections; no provider outputs captured", "cases": results}, indent=2) + "\n", encoding="utf8")
        print("PASS 9 isolated recorded DEMO scenarios; final approval retained; measured results saved; credentials suppressed")
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        frames = [frame for frame in traceback.extract_tb(error.__traceback__) if Path(frame.filename).resolve() == Path(__file__).resolve()]
        location = frames[-1].lineno if frames else 0
        raise SystemExit(f"Local chaos DEMO failed ({type(error).__name__}, driver line {location}); input/credential details suppressed.") from None
