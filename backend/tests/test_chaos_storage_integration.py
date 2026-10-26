"""CI: actual local durable scenario trajectories and lost worker process."""
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import update

from app import models as m
from app.config import Settings
from app.harness.chaos import ChaosCreate, read_fixture
from app.harness.checkpointer import OwnerPostgresSaver
from app.harness.lease import JobQueue
from app.harness.policy import PolicyDenied
from app.main import create_app
from app.repository import owner_transaction
from app.services.chaos import create_demo
from app.worker import run_once
from tests.test_storage_integration import engine as engine, local as local
from tests.test_workflow_storage_integration import decide

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not os.environ.get("LATHER_INTEGRATION_CONFIG"), reason="dedicated local config required")]
SETTINGS = Settings(_env_file=None, environment="test", chaos_enabled=True)
SCENARIOS = [row["scenario"] for row in read_fixture("scenarios.json")["scenarios"] if row["scenario"] != "interrupted_worker"]


def configured(engine, local, scenario):
    owner = UUID(local["users"][0]["id"])
    with owner_transaction(engine, owner) as repo:
        result = create_demo(repo, ChaosCreate(scenario=scenario), str(uuid4()), SETTINGS)
    return owner, UUID(result["run_id"])


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_ci01_real_scenario_graph_and_truthful_outcomes(local, engine, scenario):
    owner, run_id = configured(engine, local, scenario)
    first = run_once(engine, owner, run_id=run_id, settings=SETTINGS)
    with owner_transaction(engine, owner) as repo:
        run = repo.get(m.runs, run_id)
        attempts = repo.list(m.tool_attempts, run_id, limit=1000)
        events = repo.list(m.events, run_id, limit=1000)
        assert all(row["attempt"] <= 3 and row["state"] == "completed" for row in attempts)
        if scenario == "empty_results":
            assert run["status"] == "partial" and not repo.list(m.competitors, run_id) and not repo.list(m.reports, run_id)
            assert first["recorded_search_dispatches"] == 2  # existing bounded discovery refinement
            return
        assert run["status"] == "shortlist_review" and first["state"] == "approval_pending"
        if scenario in {"timeout", "rate_limit"}:
            assert first["recorded_search_dispatches"] == 2
            assert sum(e["kind"] == "tool.retryable_failure" for e in events) == 1
            assert sum(e["kind"] == "tool.recovered" for e in events) == 1
    decide(engine, owner, run_id, "shortlist")
    result = run_once(engine, owner, run_id=run_id, settings=SETTINGS)
    with owner_transaction(engine, owner) as repo:
        run = repo.get(m.runs, run_id)
        assert result["state"] == "approval_pending" and run["status"] == "report_review"
        tasks = repo.list(m.research_tasks, run_id)
        assert len(tasks) == 3
        report = repo.report(run_id)
        analysis = report["data"]["analysis"]
        lane = next(row for row in tasks if any(source["canonical_url"] == "https://demo-a.invalid/soap" for source in row["data"]["sources"]))
        if scenario == "inaccessible_page":
            assert any(source["access_status"] == "denied" for source in lane["data"]["sources"])
            assert all(page["products"] == [] for page in lane["data"]["pages"])
        if scenario == "conflicting_price":
            assert lane["data"]["conflicts"] and {row["amount"] for row in analysis["normalized_prices"] if row["competitor_id"] == str(lane["competitor_id"])} == {"120", "160"}
        if scenario == "missing_weight":
            prices = [row for row in analysis["normalized_prices"] if row["competitor_id"] == str(lane["competitor_id"])]
            assert prices and all(row["unit_price_100g"] is None for row in prices)
        events = repo.list(m.events, run_id, limit=1000)
        if scenario == "malformed_json":
            assert sum(e["kind"] == "model.output_invalid" for e in events) == 1
            assert any(e["kind"] == "model.replay_validated" and e["data"]["repaired"] for e in events)
        if scenario == "reviewer_rejection":
            reports = repo.list(m.reports, run_id)
            assert len(reports) == 2 and report["version"] == 2
            receipts = repo.list(m.evaluation_results, run_id)
            assert {row["outcome"] for row in receipts} == {"revise", "ready_for_human"}
            assert sum(e["kind"] == "workflow.node" and e["data"]["node"] == "revise" for e in events) == 1
        assert report["review"]["genuine_support_coverage"] is None
    decide(engine, owner, run_id, "report")
    run_once(engine, owner, run_id=run_id, settings=SETTINGS)
    with owner_transaction(engine, owner) as repo:
        assert repo.get(m.runs, run_id)["status"] == "complete"
        assert all(row["tokens"] == 0 and row["cost_usd"] == 0 for row in repo.list(m.usage, run_id, limit=1000))


def process(run_id):
    env = dict(os.environ, LATHER_ENVIRONMENT="test", LATHER_CHAOS_ENABLED="true", LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false")
    return subprocess.run([sys.executable, "-m", "tools.chaos_worker", "--run-id", str(run_id), "--lease-seconds", "2"], env=env, capture_output=True, text=True, timeout=60)


def test_ci02_actual_interrupted_process_and_fresh_process_recovery(local, engine):
    owner, run_id = configured(engine, local, "interrupted_worker")
    assert process(run_id).returncode == 0
    decide(engine, owner, run_id, "shortlist")
    lost = process(run_id)
    assert lost.returncode == 23, "DEMO worker interruption failed; details suppressed"
    with owner_transaction(engine, owner) as repo:
        before = repo.list(m.research_tasks, run_id)
        assert len(before) == 1
        hashes = {str(s["id"]): s["content_hash"] for s in repo.list(m.sources, run_id, limit=1000)}
    time.sleep(2.2)
    resumed = process(run_id)
    assert resumed.returncode == 0, "DEMO worker restart failed; details suppressed"
    assert json.loads(resumed.stdout)["recorded_web_dispatches"] == 6
    with owner_transaction(engine, owner) as repo:
        after = repo.list(m.research_tasks, run_id)
        assert len(after) == 3 and next(row for row in after if row["id"] == before[0]["id"]) == before[0]
        current = {str(s["id"]): s["content_hash"] for s in repo.list(m.sources, run_id, limit=1000)}
        assert all(current[key] == value for key, value in hashes.items())
        events = repo.list(m.events, run_id, limit=1000)
        assert any(e["kind"] == "worker.claimed" and e["data"]["recovered"] for e in events)
        assert any(e["kind"] == "chaos.worker_recovered" and e["data"]["preserved_lanes"] == 1 for e in events)
        assert repo.get(m.runs, run_id)["status"] == "report_review"
    decide(engine, owner, run_id, "report")
    assert process(run_id).returncode == 0


def test_ci03_production_worker_rejects_persisted_test_plan(local, engine):
    owner, run_id = configured(engine, local, "timeout")
    result = run_once(engine, owner, run_id=run_id, settings=Settings(_env_file=None, environment="production"))
    assert result["state"] == "stopped" and result["actual_external_calls"] == 0
    with owner_transaction(engine, owner) as repo:
        assert not repo.list(m.tool_attempts, run_id) and not repo.list(m.sources, run_id)


def test_ci04_api_auth_idempotency_and_no_mutation_of_existing_run(local, engine, integration_loop):
    async def exercise():
        settings = Settings(_env_file=None, environment="test", chaos_enabled=True, database_url=local["runtime_url"], supabase_url=local["supabase_url"], supabase_publishable_key=local["publishable_key"])
        app = create_app(settings)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                assert (await client.post("/api/chaos/runs", headers={"Idempotency-Key": "DEMO-auth-required"}, json={"scenario": "timeout"})).status_code == 401
                headers = {"Authorization": "Bearer " + local["users"][0]["token"], "Idempotency-Key": str(uuid4())}
                first = await client.post("/api/chaos/runs", headers=headers, json={"scenario": "timeout"})
                replay = await client.post("/api/chaos/runs", headers=headers, json={"scenario": "timeout"})
                assert first.status_code == replay.status_code == 201 and first.json() == replay.json()
                assert (await client.post("/api/chaos/runs", headers=headers, json={"scenario": "rate_limit"})).status_code == 409
                assert (await client.post("/api/chaos/runs", headers=headers, json={"scenario": "timeout", "run_id": first.json()["run_id"]})).status_code == 422
                other = {"Authorization": "Bearer " + local["users"][1]["token"]}
                assert (await client.get("/api/workspace?run_id=" + first.json()["run_id"], headers=other)).status_code == 404
    integration_loop.run_until_complete(exercise())


@pytest.mark.parametrize("failure", ["repair_exhausted", "budget_exhausted"])
def test_ci05_invalid_model_output_never_fabricates_fallback_or_bypasses_bounds(local, engine, monkeypatch, failure):
    owner, run_id = configured(engine, local, "malformed_json")
    run_once(engine, owner, run_id=run_id, settings=SETTINGS)
    decide(engine, owner, run_id, "shortlist")
    if failure == "repair_exhausted":
        # Unit-test replacement only: the HTTP API cannot accept raw templates or paths.
        monkeypatch.setattr("app.harness.model_replay.read_fixture", lambda _: {"schema_version": "model-fixtures-1.0", "malformed_json": [{"raw": "{"}, {"raw": "{"}]})
    else:
        with owner_transaction(engine, owner) as repo:
            run = repo.get(m.runs, run_id)
            # Clean trajectory uses 1 search + 9 retrieval + 1 model attempt.
            repo.conn.execute(update(m.runs).where(m.runs.c.id == run_id).values(budget=run["budget"] | {"max_calls": 11}))
    result = run_once(engine, owner, run_id=run_id, settings=SETTINGS)
    assert result["state"] == "stopped" and result["actual_external_calls"] == 0
    with owner_transaction(engine, owner) as repo:
        assert len(repo.list(m.research_tasks, run_id)) == 3
        assert not repo.list(m.reports, run_id)
        report_requests = {row["id"] for row in repo.list(m.approval_requests, run_id) if row["gate"] == "report"}
        assert not any(row["request_id"] in report_requests for row in repo.list(m.approval_decisions, run_id))
        invalid = [e for e in repo.list(m.events, run_id, limit=1000) if e["kind"] == "model.output_invalid"]
        assert len(invalid) == (2 if failure == "repair_exhausted" else 1)
        assert len(repo.list(m.tool_attempts, run_id, limit=1000)) == (12 if failure == "repair_exhausted" else 11)


def test_ci06_pending_writes_can_arrive_before_parent_checkpoint_commit(local, engine, monkeypatch):
    from langgraph.checkpoint.base import empty_checkpoint
    owner, run_id = configured(engine, local, "empty_results")
    lease = JobQueue(engine, owner).claim(uuid4(), 30, run_id)
    saver = OwnerPostgresSaver(engine, lease)
    checkpoint = empty_checkpoint()
    config = {"configurable": {"thread_id": str(run_id)}}
    pending_config = saver._ref("", checkpoint["id"])
    observed = Event()
    original = saver._parent_exists
    def parent_exists(namespace, identifier):
        present = original(namespace, identifier)
        if not present:
            observed.set()
        return present
    monkeypatch.setattr(saver, "_parent_exists", parent_exists)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(saver.put_writes, pending_config, [("DEMO-channel", "DEMO-preserved")], "DEMO-task")
        assert observed.wait(3) and not pending.done()
        saver.put(config, checkpoint, {"source": "input", "step": -1, "parents": {}}, {})
        pending.result(timeout=5)
    stored = saver.get_tuple(pending_config)
    assert stored.pending_writes == [("DEMO-task", "DEMO-channel", "DEMO-preserved")]
    # New saver/process uses the durable parent, with no dependency on old notification memory.
    fresh = OwnerPostgresSaver(engine, lease)
    fresh.put_writes(pending_config, [("DEMO-channel", "DEMO-preserved")], "DEMO-task")
    assert fresh.get_tuple(pending_config).pending_writes == stored.pending_writes
    JobQueue(engine, owner).release(lease)


def test_ci07_missing_parent_wait_is_bounded_without_placeholder_or_orphan_write(local, engine, monkeypatch):
    owner, run_id = configured(engine, local, "empty_results")
    lease = JobQueue(engine, owner).claim(uuid4(), 30, run_id)
    saver = OwnerPostgresSaver(engine, lease)
    times = iter((0.0, 6.0))
    monkeypatch.setattr("app.harness.checkpointer.monotonic", lambda: next(times))
    with pytest.raises(PolicyDenied, match="checkpoint_parent_not_durable"):
        saver.put_writes(saver._ref("", "DEMO-missing-parent"), [("DEMO-channel", "DEMO-value")], "DEMO-task")
    with owner_transaction(engine, owner) as repo:
        assert not repo.list(m.graph_checkpoints, run_id) and not repo.list(m.graph_writes, run_id)
    JobQueue(engine, owner).release(lease)
