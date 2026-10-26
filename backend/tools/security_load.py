"""Bounded local recorded-worker benchmark; automated approvals are DEMO only."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
from statistics import median
from threading import Lock
from time import perf_counter, sleep
from uuid import UUID, uuid4

from sqlalchemy import create_engine, select

from app import models as m
from app.api_schemas import BriefCreate, DecisionCreate, RunCreate
from app.repository import owner_transaction
from app.worker import run_once
from app.workflow import Workflow
from tools.workflow_demo import local_config


def seed(engine, owner):
    fixture = json.loads(Path("evaluations/fixtures/scout-v1/SC01-clean.json").read_text())
    with owner_transaction(engine, owner) as repo:
        brief = repo.create(m.briefs, BriefCreate.model_validate(fixture["brief"]).model_dump(mode="json") | {"version": 1})
        run = repo.start(RunCreate(brief_id=brief["id"], budget={"max_calls": 100, "max_tokens": 0, "max_cost_usd": "0"}), str(uuid4()))
        repo.control(UUID(str(run["id"])), "resume", 1, str(uuid4()))
        return UUID(str(run["id"]))


def demo_approve(engine, owner, run_id, gate):
    with owner_transaction(engine, owner) as repo:
        run = repo.get(m.runs, run_id)
        request = repo.conn.execute(select(m.approval_requests).where(m.approval_requests.c.run_id == run_id,
            m.approval_requests.c.owner_id == owner, m.approval_requests.c.gate == gate, m.approval_requests.c.state == "pending")).mappings().one()
        body = DecisionCreate(request_id=request["id"], artifact_version=request["artifact_version"], artifact_hash=request["artifact_hash"],
            expected_run_version=run["version"], decision="approve")
        repo.decide(run_id, gate, body, str(uuid4()))


class DelayedRecordedWorkflow(Workflow):
    def __init__(self, engine, lease, deadline, scout, web):
        web.before_request = lambda _: sleep(0.01)
        super().__init__(engine, lease, deadline, scout, web)


def measure(engine, owner, workers, count=4):
    if workers not in {1, 2, 4} or not 1 <= count <= 8:
        raise ValueError("bounded_local_load_only")
    runs = [seed(engine, owner) for _ in range(count)]
    lock = Lock()
    active, peak, calls, latencies, waits, event_counts = 0, 0, 0, [], [], []
    began = perf_counter()
    def work(run_id):
        nonlocal active, peak, calls
        started = perf_counter()
        with lock:
            active += 1
            peak = max(peak, active)
            waits.append(round((started - began) * 1000, 2))
        dispatches = 0
        try:
            for gate in ("shortlist", "report", None):
                result = run_once(engine, owner, run_id=run_id, workflow_factory=DelayedRecordedWorkflow)
                assert result["actual_external_calls"] == 0
                assert result["state"] == ("approval_pending" if gate else "finished")
                dispatches += result.get("recorded_search_dispatches", 0) + result.get("recorded_web_dispatches", 0)
                if gate:
                    demo_approve(engine, owner, run_id, gate)
            with owner_transaction(engine, owner) as repo:
                assert repo.get(m.runs, run_id)["status"] == "complete"
                assert len(repo.list(m.research_tasks, run_id)) == 3
                assert len(repo.list(m.reports, run_id)) == 1
                events = repo.list(m.events, run_id, limit=10000)
                assert sum(row["kind"] == "worker.claimed" for row in events) == 3
            with lock:
                calls += dispatches
                event_counts.append(len(events))
                latencies.append(round((perf_counter() - started) * 1000, 2))
        finally:
            with lock:
                active -= 1
    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(work, runs))
    elapsed = perf_counter() - began
    ordered = sorted(latencies)
    return {"workers": workers, "completed_runs": count, "elapsed_seconds": round(elapsed, 3), "runs_per_second": round(count / elapsed, 3),
        "run_latency_ms": {"p50": median(latencies), "p95_nearest_rank": ordered[-1], "samples": latencies},
        "queue_start_wait_ms": waits, "peak_active_workers": peak, "recorded_tool_dispatches": calls, "persisted_event_counts": event_counts,
        "completed_research_lanes": count * 3, "actual_provider_calls": 0, "actual_provider_tokens": 0, "provider_cost_usd": "0"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cfg = local_config()  # Includes independent dedicated-instance marker check.
    engine = create_engine(cfg["runtime_url"], hide_parameters=True, pool_size=5, max_overflow=5, pool_timeout=10)
    try:
        results = [measure(engine, UUID(cfg["users"][0]["id"]), workers) for workers in (1, 2, 4)]
        report = {"schema_version": "local-load-1.0", "label": "DEMO", "measured_at": datetime.now(timezone.utc).isoformat(),
            "platform": platform.system(), "python": platform.python_version(), "database": "dedicated loopback Supabase Postgres; non-bypass runtime role",
            "dataset": "SC01-clean / R21-parallel recorded fixtures", "mock_delay_per_web_dispatch_ms": 10,
            "approvals": "automated DEMO owner decisions through real repository gates; no human think-time",
            "limits": {"owner_outstanding_runs_including_approvals": 128, "owner_active_leases": 4, "db_pool": 5, "db_max_overflow": 5, "db_wait_seconds": 10},
            "results": results, "limitations": ["four runs per condition; p95 is nearest-rank maximum of four samples", "one local owner; no tenant-fairness or distributed ingress benchmark", "recorded research and rule analysis, no model/network latency", "no production capacity or million-user claim"]}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
        for row in results:
            print(f"DEMO workers={row['workers']}: {row['completed_runs']} completed in {row['elapsed_seconds']}s; {row['runs_per_second']} runs/s; peak={row['peak_active_workers']}; provider calls=0")
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit(f"Local load check failed ({type(error).__name__}); private details suppressed") from None
