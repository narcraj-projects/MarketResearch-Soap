"""W06+: real local Postgres graph/lease tests and fresh operating-system workers."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
import json
import os
import subprocess
import sys
import time
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from fastapi import HTTPException
import httpx
import pytest
from sqlalchemy import func, select, update

from app import models as m
from app.api_schemas import BriefCreate, DecisionCreate, RunCreate
from app.config import Settings
from app.harness.checkpointer import OwnerPostgresSaver
from app.harness.lease import JobQueue
from app.harness.policy import PolicyDenied
from app.harness.recordings import RecordedTavily
from app.harness.search_store import PostgresSearchLedger
from app.main import create_app
from app.repository import owner_transaction
from app.worker import heartbeat, run_once
from app.workflow import Workflow
from app.workflow import build_graph
import tests.test_storage_integration as storage

engine = storage.engine
local = storage.local

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not os.environ.get("LATHER_INTEGRATION_CONFIG"), reason="explicit dedicated local config required")]


def prepared(engine, local):
    owner = UUID(local["users"][0]["id"])
    recording = RecordedTavily(Path("evaluations/fixtures/scout-v1/SC01-clean.json"))
    brief = BriefCreate.model_validate(recording.case["brief"])
    with owner_transaction(engine, owner) as repo:
        brief = repo.create(m.briefs, brief.model_dump(mode="json") | {"version": 1})
        run = repo.start(RunCreate(brief_id=brief["id"], budget={"max_calls": 100, "max_tokens": 0, "max_cost_usd": "0"}), str(uuid4()))
        run_id = UUID(str(run["id"]))
        first = repo.control(run_id, "resume", 1, "DEMO-resume-key")
        assert first == repo.control(run_id, "resume", 1, "DEMO-resume-key")
        with pytest.raises(HTTPException) as conflict:
            repo.control(run_id, "resume", 2, "DEMO-resume-key")
        assert conflict.value.status_code == 409
    return owner, run_id


def read(engine, owner, run_id):
    with owner_transaction(engine, owner) as repo:
        return repo.get(m.runs, run_id)


def decide(engine, owner, run_id, gate, decision="approve"):
    with owner_transaction(engine, owner) as repo:
        run = repo.get(m.runs, run_id)
        pending = repo.conn.execute(select(m.approval_requests).where(m.approval_requests.c.run_id == run_id,
            m.approval_requests.c.owner_id == owner, m.approval_requests.c.gate == gate, m.approval_requests.c.state == "pending")).mappings().one()
        body = DecisionCreate(request_id=pending["id"], artifact_version=pending["artifact_version"], artifact_hash=pending["artifact_hash"],
            expected_run_version=run["version"], decision=decision)
        result = repo.decide(run_id, gate, body, "DEMO-" + gate + "-key")
        assert result == repo.decide(run_id, gate, body, "DEMO-" + gate + "-key")
        return pending, result


def process(run_id, *, crash=False):
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    env["LANGSMITH_TRACING"] = "false"
    env["LANGCHAIN_TRACING_V2"] = "false"
    if crash:
        env["LATHER_WORKFLOW_FAULT"] = "DEMO-process-crash"
    args = [sys.executable, "tests/helpers/workflow_crash.py", str(run_id)] if crash else [sys.executable, "-m", "tools.workflow_demo", "--run-id", str(run_id)]
    result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=50)
    assert result.returncode == (23 if crash else 0), "DEMO worker process failed; input/credential details suppressed"
    return {} if crash else json.loads(result.stdout)


def test_w06_process_restart_mid_parallel_research_and_both_pending_gates(local, engine):
    owner, run_id = prepared(engine, local)
    start = process(run_id)
    assert start["state"] == "approval_pending" and start["recorded_search_dispatches"] == 1
    assert start["recorded_web_dispatches"] == 0
    before = read(engine, owner, run_id)
    assert before["status"] == "shortlist_review"
    assert process(run_id)["state"] == "idle"  # a new process cannot bypass the durable gate
    assert read(engine, owner, run_id) == before
    with owner_transaction(engine, owner) as repo:
        assert repo.list(m.graph_checkpoints, run_id) and repo.list(m.graph_writes, run_id)
        with pytest.raises(HTTPException) as pending:
            repo.control(run_id, "resume", before["version"], str(uuid4()))
        assert pending.value.detail == "approval_pending"
    decide(engine, owner, run_id, "shortlist")
    process(run_id, crash=True)
    with owner_transaction(engine, owner) as repo:
        completed = repo.list(m.research_tasks, run_id)
        assert len(completed) == 1
        first = completed[0]
        sources_before = {str(s["id"]): s["content_hash"] for s in repo.list(m.sources, run_id, limit=1000)}
        attempts_before = repo.list(m.tool_attempts, run_id, limit=1000)
        assert all(row["state"] == "completed" for row in attempts_before)
    time.sleep(2.1)  # Real database-clock lease expiry; no test clock substitution.
    recovered = process(run_id)
    assert recovered["state"] == "approval_pending" and recovered["recorded_search_dispatches"] == 0
    assert recovered["recorded_web_dispatches"] == 6  # two remaining lanes, three wires each
    with owner_transaction(engine, owner) as repo:
        tasks = repo.list(m.research_tasks, run_id)
        assert len(tasks) == 3 and next(t for t in tasks if t["id"] == first["id"]) == first
        sources_after = {str(s["id"]): s["content_hash"] for s in repo.list(m.sources, run_id, limit=1000)}
        assert all(sources_after[key] == value for key, value in sources_before.items())
        attempts = repo.list(m.tool_attempts, run_id, limit=1000)
        assert len(attempts) == 10 and len({(a["operation_id"], a["attempt"]) for a in attempts}) == 10
        assert len(repo.list(m.reports, run_id)) == 1
    review = read(engine, owner, run_id)
    assert review["status"] == "report_review"
    assert process(run_id)["state"] == "idle"
    assert read(engine, owner, run_id) == review
    decide(engine, owner, run_id, "report")
    assert read(engine, owner, run_id)["status"] == "report_review"  # approval itself cannot save
    saved = process(run_id)
    assert saved["state"] == "finished" and saved["recorded_web_dispatches"] == saved["recorded_search_dispatches"] == 0
    assert read(engine, owner, run_id)["status"] == "complete"
    assert process(run_id)["state"] == "idle"
    with owner_transaction(engine, owner) as repo:
        events = repo.list(m.events, run_id, limit=1000)
        assert [e["sequence"] for e in events] == list(range(1, len(events) + 1))
        assert sum(e["kind"] == "run.completed" for e in events) == 1
        assert any(e["kind"] == "worker.claimed" and e["data"]["recovered"] for e in events)
        assert len(repo.list(m.approval_decisions, run_id)) == 2


def test_w07_lease_claim_heartbeat_takeover_and_stale_fence(local, engine):
    owner, run_id = prepared(engine, local)
    queue = JobQueue(engine, owner)
    with ThreadPoolExecutor(max_workers=2) as pool:
        leases = list(pool.map(lambda _: queue.claim(uuid4(), 2, run_id), range(2)))
    assert sum(lease is not None for lease in leases) == 1
    lease = next(lease for lease in leases if lease)
    with owner_transaction(engine, owner) as repo:
        original_deadline = repo.conn.execute(select(m.jobs.c.deadline).where(m.jobs.c.run_id == run_id)).scalar_one()
    queue.heartbeat(lease, 3)
    assert queue.claim(uuid4(), 2, run_id) is None
    with owner_transaction(engine, owner) as repo:
        # Expiry of disposable local DEMO job; production has no fault-injection route.
        repo.conn.execute(update(m.jobs).where(m.jobs.c.run_id == run_id).values(lease_until=func.clock_timestamp() - timedelta(seconds=1)))
    replacement = queue.claim(uuid4(), 5, run_id)
    assert replacement and replacement.generation == lease.generation + 1
    for action in (lambda: queue.heartbeat(lease), lambda: queue.release(lease),
        lambda: OwnerPostgresSaver(engine, lease).get_tuple({"configurable": {"thread_id": str(run_id)}})):
        with pytest.raises(PolicyDenied, match="lease_lost"):
            action()
    with owner_transaction(engine, owner) as repo:
        assert repo.conn.execute(select(m.jobs.c.deadline).where(m.jobs.c.run_id == run_id)).scalar_one() == original_deadline
        with pytest.raises(PolicyDenied, match="worker_lease_required"):
            PostgresSearchLedger.locked(repo, run_id)
    queue.release(replacement)


def test_w08_cancellation_invalidates_lease_and_pending_approval(local, engine):
    owner, run_id = prepared(engine, local)
    assert run_once(engine, owner, run_id=run_id)["state"] == "approval_pending"
    before = read(engine, owner, run_id)
    with owner_transaction(engine, owner) as repo:
        result = repo.control(run_id, "cancel", before["version"], "DEMO-cancel-key")
        assert result == repo.control(run_id, "cancel", before["version"], "DEMO-cancel-key")
        assert result["status"] == "cancelled"
        assert all(row["state"] == "superseded" for row in repo.list(m.approval_requests, run_id))
        with pytest.raises(HTTPException, match="terminal_run"):
            repo.control(run_id, "resume", result["version"], str(uuid4()))
    assert run_once(engine, owner, run_id=run_id)["state"] == "idle"
    owner, run_id = prepared(engine, local)
    queue = JobQueue(engine, owner)
    lease = queue.claim(uuid4(), 30, run_id)
    assert lease
    with owner_transaction(engine, owner) as repo:
        run = repo.get(m.runs, run_id)
        repo.control(run_id, "cancel", run["version"], str(uuid4()))
    with pytest.raises(PolicyDenied, match="lease_lost_or_cancelled"):
        lease.check(engine)


def test_w09_owner_api_sse_polling_cursor_and_controls(local, engine, integration_loop):
    owner, run_id = prepared(engine, local)
    assert run_once(engine, owner, run_id=run_id)["state"] == "approval_pending"
    settings = Settings(_env_file=None, environment="test", database_url=local["runtime_url"], supabase_url=local["supabase_url"], supabase_publishable_key=local["publishable_key"])
    async def exercise():
        app = create_app(settings)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                headers = {"Authorization": "Bearer " + local["users"][0]["token"]}
                other = {"Authorization": "Bearer " + local["users"][1]["token"]}
                base = f"/api/runs/{run_id}"
                polling = (await client.get(base + "/events?after=2", headers=headers)).json()
                stream = await client.get(base + "/events/stream?follow_seconds=0", headers=headers | {"Last-Event-ID": "2"})
                assert stream.status_code == 200 and stream.headers["content-type"].startswith("text/event-stream")
                frames = [json.loads(line[6:]) for line in stream.text.splitlines() if line.startswith("data: ")]
                assert frames == polling and all(frame["sequence"] > 2 for frame in frames)
                last = frames[-1]["sequence"]
                empty = await client.get(base + "/events/stream?follow_seconds=0", headers=headers | {"Last-Event-ID": str(last)})
                assert empty.status_code == 200 and not empty.text
                assert (await client.get(base + "/events/stream?follow_seconds=0", headers=other)).status_code == 404
                assert (await client.get(base + "/events/stream?follow_seconds=0", headers=headers | {"Last-Event-ID": "-1"})).status_code == 400
                assert (await client.post(base + "/cancel", headers=other | {"Idempotency-Key": str(uuid4())}, json={"expected_run_version": 1})).status_code == 404
                assert (await client.post(base + "/resume", headers=headers | {"Idempotency-Key": str(uuid4())}, json={"expected_run_version": read(engine, owner, run_id)["version"]})).status_code == 409
    integration_loop.run_until_complete(exercise())


@pytest.mark.parametrize("decision", ["reject", "request_changes"])
@pytest.mark.parametrize("gate", ["shortlist", "report"])
def test_w10_negative_decisions_never_save(local, engine, decision, gate):
    owner, run_id = prepared(engine, local)
    run_once(engine, owner, run_id=run_id)
    if gate == "report":
        decide(engine, owner, run_id, "shortlist")
        assert run_once(engine, owner, run_id=run_id)["state"] == "approval_pending"
    decide(engine, owner, run_id, gate, decision)
    result = run_once(engine, owner, run_id=run_id)
    assert result["state"] == "finished" and result["recorded_web_dispatches"] == 0
    assert read(engine, owner, run_id)["status"] == "partial"
    with owner_transaction(engine, owner) as repo:
        if gate == "shortlist":
            assert not repo.list(m.research_tasks, run_id) and not repo.list(m.reports, run_id)
        assert not any(e["kind"] == "run.completed" for e in repo.list(m.events, run_id, limit=1000))


@pytest.mark.parametrize("failures", [1, 2])
def test_w11_bounded_real_graph_revision_preserves_immutable_versions(local, engine, failures):
    class ReviseOnce(Workflow):
        def review(self, state):
            result = super().review(state)
            if state.revision < failures:
                return result | {"review_ok": False, "issues": ["DEMO-forced-review-failure"]}
            return result
    owner, run_id = prepared(engine, local)
    run_once(engine, owner, run_id=run_id)
    decide(engine, owner, run_id, "shortlist")
    result = run_once(engine, owner, run_id=run_id, workflow_factory=ReviseOnce)
    assert result["state"] == ("approval_pending" if failures == 1 else "finished")
    with owner_transaction(engine, owner) as repo:
        reports = repo.list(m.reports, run_id)
        requests = [r for r in repo.list(m.approval_requests, run_id) if r["gate"] == "report"]
        assert {r["version"] for r in reports} == {1, 2} and len(requests) == (1 if failures == 1 else 0)
        if failures == 1:
            assert requests[0]["artifact_version"] == 2
        else:
            assert repo.get(m.runs, run_id)["status"] == "partial"
        assert all(r["data"]["support_status"] == "unreviewed" for r in reports)


def test_w12_decision_racing_interrupt_release_is_requeued(local, engine):
    owner, run_id = prepared(engine, local)
    run_once(engine, owner, run_id=run_id)
    with owner_transaction(engine, owner) as repo:
        repo.conn.execute(update(m.jobs).where(m.jobs.c.run_id == run_id).values(state="queued"))
    queue = JobQueue(engine, owner)
    lease = queue.claim(uuid4(), 30, run_id)
    assert lease
    request, _ = decide(engine, owner, run_id, "shortlist")
    queue.release(lease, waiting_request=request["id"])
    with owner_transaction(engine, owner) as repo:
        assert repo.conn.execute(select(m.jobs.c.state).where(m.jobs.c.run_id == run_id)).scalar_one() == "queued"


def test_w14_worker_heartbeat_prevents_takeover_until_process_stops(local, engine):
    owner, run_id = prepared(engine, local)
    queue = JobQueue(engine, owner)
    lease = queue.claim(uuid4(), 2, run_id)
    assert lease
    with heartbeat(queue, lease, 2) as lost:
        time.sleep(2.4)
        assert not lost.is_set()
        lease.check(engine)
        assert queue.claim(uuid4(), 2, run_id) is None
    time.sleep(2.1)
    recovered = queue.claim(uuid4(), 5, run_id)
    assert recovered and recovered.generation == lease.generation + 1
    queue.release(recovered)


def test_w15_cancel_between_reservation_and_dispatch_never_calls_transport(local, engine):
    from app.adapters.tavily import TavilyAdapter
    from app.harness.contracts import Versions
    from app.harness.gateway import SearchGateway
    from app.harness.search import SearchCost
    from app.services.discovery import search
    owner, run_id = prepared(engine, local)
    queue = JobQueue(engine, owner)
    lease = queue.claim(uuid4(), 30, run_id)
    assert lease
    ledger = PostgresSearchLedger(engine, lease)
    versions = Versions(graph="scout-1.0", model="none", provider="none", prompt="deterministic-scout-1.0", tools="tavily-search-1.0", dataset="scout-demo-v1")
    context, brief = ledger.begin(run_id, owner, queue.deadline(run_id), versions)
    recording = RecordedTavily(Path("evaluations/fixtures/scout-v1/SC01-clean.json"))
    def cancel_at_dispatch():
        with owner_transaction(engine, owner) as repo:
            run = repo.get(m.runs, run_id)
            repo.control(run_id, "cancel", run["version"], str(uuid4()))
        lease.check(engine)
    gateway = SearchGateway(TavilyAdapter(recording.transport), ledger, SearchCost(per_attempt_upper_bound_usd="0", pricing_version="DEMO-zero-spend"), guard=cancel_at_dispatch)
    with pytest.raises(PolicyDenied, match="lease_lost_or_cancelled"):
        search(context, brief, gateway)
    assert recording.ordinal == 0
    with owner_transaction(engine, owner) as repo:
        attempts = repo.list(m.tool_attempts, run_id)
        assert len(attempts) == 1 and attempts[0]["state"] == "reserved"
        assert not repo.list(m.sources, run_id)


def test_w16_forged_graph_resume_cannot_substitute_for_durable_decision(local, engine):
    from langgraph.types import Command
    from app.adapters.public_web import RecordedWeb
    owner, run_id = prepared(engine, local)
    assert run_once(engine, owner, run_id=run_id)["state"] == "approval_pending"
    with owner_transaction(engine, owner) as repo:
        repo.conn.execute(update(m.jobs).where(m.jobs.c.run_id == run_id).values(state="queued"))
    queue = JobQueue(engine, owner)
    lease = queue.claim(uuid4(), 30, run_id)
    assert lease
    workflow = Workflow(engine, lease, queue.deadline(run_id), RecordedTavily(Path("evaluations/fixtures/scout-v1/SC01-clean.json")),
        RecordedWeb(Path("evaluations/fixtures/research-v1/R21-parallel.json")))
    graph = build_graph(workflow, OwnerPostgresSaver(engine, lease))
    with pytest.raises(PolicyDenied, match="durable_approval_required"):
        graph.invoke(Command(resume="approve"), {"configurable": {"thread_id": str(run_id)}}, durability="sync")
    queue.release(lease)
    with owner_transaction(engine, owner) as repo:
        assert not repo.list(m.research_tasks, run_id)
        assert not repo.list(m.approval_decisions, run_id)
    decide(engine, owner, run_id, "shortlist")
    # The deliberately corrupted internal resume history is not erased/reinterpreted.
    # HTTP commands never accept this graph payload; tampering must fail closed.
    assert run_once(engine, owner, run_id=run_id)["state"] == "stopped"
    assert read(engine, owner, run_id)["status"] == "partial"
    with owner_transaction(engine, owner) as repo:
        assert not repo.list(m.research_tasks, run_id) and not repo.list(m.reports, run_id)


def test_z_w13_checkpoint_migration_rollback_preserves_domain_evidence(local, engine, monkeypatch):
    owner, run_id = prepared(engine, local)
    run_once(engine, owner, run_id=run_id)
    decide(engine, owner, run_id, "shortlist")
    run_once(engine, owner, run_id=run_id)
    with owner_transaction(engine, owner) as repo:
        reports = repo.list(m.reports, run_id)
        sources = repo.list(m.sources, run_id)
        approvals = repo.list(m.approval_requests, run_id)
    config = Config("alembic.ini")
    monkeypatch.setenv("LATHER_DATABASE_URL", local["admin_url"])
    command.downgrade(config, "0004")
    command.upgrade(config, "head")
    with owner_transaction(engine, owner) as repo:
        assert repo.list(m.reports, run_id) == reports
        assert repo.list(m.sources, run_id) == sources
        assert repo.list(m.approval_requests, run_id) == approvals
        assert not repo.list(m.graph_checkpoints, run_id)
