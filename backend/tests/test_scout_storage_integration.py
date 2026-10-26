"""Actual local Postgres discovery, approval interrupt and process restart tests."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import UUID, uuid4, uuid5

import httpx
import pytest
from sqlalchemy import update

from app import models as m
from app.adapters.tavily import TavilyAdapter
from app.api_schemas import RunCreate
from app.config import Settings
from app.harness.contracts import Role, SearchCall
from app.harness.gateway import SearchGateway
from app.harness.policy import PolicyDenied
from app.harness.recordings import RecordedTavily
from app.harness.search import SearchCost
from app.harness.search_store import PostgresSearchLedger
from app.main import create_app
from app.repository import owner_transaction
from app.services.discovery import discover, queries, search
from tests.scout_support import versions
from tests.test_storage_integration import engine as engine, local as local

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not os.environ.get("LATHER_INTEGRATION_CONFIG"), reason="explicit dedicated local Supabase required")]
FOLDER = Path(__file__).resolve().parents[1] / "evaluations/fixtures/scout-v1"


def begin(engine, local, case="SC01-clean", budget=None):
    owner = UUID(local["users"][0]["id"])
    recording = RecordedTavily(FOLDER / (case + ".json"))
    with owner_transaction(engine, owner) as repo:
        brief = repo.create(m.briefs, recording.case["brief"] | {"version": 1})
        run_id = UUID(repo.start(RunCreate(brief_id=brief["id"], budget=budget or {"max_calls": 6, "max_tokens": 0, "max_cost_usd": "0"}), str(uuid4()))["id"])
    ledger = PostgresSearchLedger(engine)
    context, brief = ledger.begin(run_id, owner, datetime.now(timezone.utc) + timedelta(minutes=5), versions())
    gateway = SearchGateway(TavilyAdapter(recording.transport), ledger, SearchCost(per_attempt_upper_bound_usd=0, pricing_version="DEMO-zero-spend"), sleep=lambda _: None)
    return owner, recording, ledger, context, brief, gateway


def test_durable_shortlist_interrupt_owner_read_and_version_bound_approval(engine, local, integration_loop):
    owner, recording, ledger, context, brief, gateway = begin(engine, local)
    call = SearchCall(operation_id=uuid5(context.run_id, f"scout:{context.versions.graph}:0"), agent=Role.SCOUT, tool="public.search", query=queries(brief)[0], limit=10)
    completed = gateway.execute(context, call)
    with owner_transaction(engine, owner) as repo:
        stored_payload = repo.get(m.tool_attempts, completed.result.payload_ref)["outcome"]["payload"]
        assert stored_payload == completed.payload.model_dump(mode="json")
    pending = discover(context, brief, gateway, ledger)
    assert pending["status"] == "shortlist_review" and pending["run_version"] == 3
    assert len(pending["artifact"]["competitor_ids"]) == 3
    with owner_transaction(engine, owner) as repo:
        sources = repo.list(m.sources, context.run_id)
        assert len(sources) == 3 and all(s["excerpt"] and s["content_hash"] and s["retrieved_at"] and s["evidence_kind"] == "search_snippet" for s in sources)
        assert len(repo.list(m.tool_attempts, context.run_id)) == len(repo.list(m.usage, context.run_id)) == 1
        assert any(event["kind"] == "approval.pending" for event in repo.list(m.events, context.run_id))
    # A new service/transaction loads the SAME pending artifact; no source call can cross the gate.
    with owner_transaction(engine, owner) as repo:
        assert ledger.snapshot(repo, context.run_id) == pending
    with pytest.raises(PolicyDenied, match="stale_run_or_gate"):
        search(context, brief, gateway)
    assert recording.ordinal == 1

    async def exercise():
        app = create_app(Settings(_env_file=None, environment="test", database_url=local["runtime_url"], supabase_url=local["supabase_url"], supabase_publishable_key=local["publishable_key"]))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                own = {"Authorization": "Bearer " + local["users"][0]["token"], "Idempotency-Key": str(uuid4())}
                other = own | {"Authorization": "Bearer " + local["users"][1]["token"]}
                route = f"/api/runs/{context.run_id}/shortlist"
                assert (await client.get(route, headers=other)).status_code == 404
                response = await client.get(route, headers=own)
                assert response.status_code == 200 and response.json()["artifact_hash"] == pending["artifact_hash"]
                body = {"request_id": pending["request_id"], "artifact_version": 1, "artifact_hash": pending["artifact_hash"], "expected_run_version": pending["run_version"], "decision": "approve"}
                decision_route = route + "-decision"
                assert (await client.post(decision_route, headers=other, json=body)).status_code == 404
                assert (await client.post(decision_route, headers=own, json=body | {"artifact_hash": "a" * 64})).status_code == 409
                first = await client.post(decision_route, headers=own, json=body)
                second = await client.post(decision_route, headers=own, json=body)
                assert first.status_code == second.status_code == 200 and first.json() == second.json()
                assert (await client.get(route, headers=own)).json()["status"] == "researching"
    integration_loop.run_until_complete(exercise())
    assert recording.ordinal == 1  # This stage never executes Researcher.


def test_fewer_or_empty_shortlist_does_not_fill_quota(engine, local):
    for case, count, status in [("SC02-fewer", 2, "shortlist_review"), ("SC03-empty", 0, "partial")]:
        owner, _, ledger, context, brief, gateway = begin(engine, local, case)
        snapshot = discover(context, brief, gateway, ledger)
        assert snapshot["status"] == status
        assert len(snapshot["artifact"]["competitor_ids"]) == count
        assert snapshot["artifact"]["insufficiency_reason"]
        with owner_transaction(engine, owner) as repo:
            assert len(repo.list(m.competitors, context.run_id)) == count
            assert len(repo.list(m.approval_requests, context.run_id)) == (1 if count else 0)


@pytest.mark.parametrize("budget,cost", [({"max_calls": 1, "max_tokens": 0, "max_cost_usd": "1"}, Decimal("0.1")), ({"max_calls": 6, "max_tokens": 0, "max_cost_usd": "0.1"}, Decimal("0.1"))])
def test_atomic_database_call_and_cost_reservations(engine, local, budget, cost):
    owner, _, ledger, context, _, _ = begin(engine, local, budget=budget)
    def reserve(_):
        call = SearchCall(operation_id=uuid4(), agent=Role.SCOUT, tool="public.search", query="DEMO race")
        try:
            ledger.reserve(context, call, "b" * 64, cost, datetime.now(timezone.utc))
            return "reserved"
        except PolicyDenied as error:
            return str(error)
    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(reserve, range(4)))
    assert outcomes.count("reserved") == 1 and outcomes.count("budget") == 3
    with owner_transaction(engine, owner) as repo:
        assert len(repo.list(m.tool_attempts, context.run_id)) == 1


def test_unknown_inflight_reservation_blocks_restart_without_refund(engine, local):
    owner, _, ledger, context, brief, _ = begin(engine, local)
    call = SearchCall(operation_id=uuid4(), agent=Role.SCOUT, tool="public.search", query="DEMO uncertain")
    assert ledger.reserve(context, call, "b" * 64, Decimal(0), datetime.now(timezone.utc)) is None
    fresh = PostgresSearchLedger(engine)
    resumed, _ = fresh.begin(context.run_id, owner, datetime.now(timezone.utc) + timedelta(hours=1), versions())
    assert resumed.budget.reserved_calls == 1 and resumed.deadline == context.deadline
    with pytest.raises(PolicyDenied, match="uncertain_attempt"):
        fresh.reserve(context, call, "b" * 64, Decimal(0), datetime.now(timezone.utc))
    with pytest.raises(PolicyDenied, match="uncertain_attempt"):
        fresh.finish(context, brief)
    with owner_transaction(engine, owner) as repo:
        assert repo.list(m.tool_attempts, context.run_id)[0]["state"] == "reserved"
        assert repo.list(m.approval_requests, context.run_id) == []


def test_other_tool_usage_counts_toward_run_budget(engine, local):
    owner, _, ledger, context, _, _ = begin(engine, local, budget={"max_calls": 1, "max_tokens": 0, "max_cost_usd": "0"})
    with owner_transaction(engine, owner) as repo:
        repo.create(m.usage, {"run_id": context.run_id, "operation_id": uuid4(), "attempt": 1, "calls": 1, "tokens": 0, "cost_usd": Decimal(0)})
    with pytest.raises(PolicyDenied, match="budget"):
        ledger.reserve(context, SearchCall(operation_id=uuid4(), agent=Role.SCOUT, tool="public.search", query="DEMO"), "b" * 64, Decimal(0), datetime.now(timezone.utc))


def test_approval_survives_actual_process_restart_and_committed_search_not_repeated(local):
    backend = Path(__file__).resolve().parents[1]
    environment = os.environ | {"LATHER_INTEGRATION_CONFIG": os.environ["LATHER_INTEGRATION_CONFIG"]}
    def invoke(*args):
        result = subprocess.run([sys.executable, "tools/scout_demo.py", "--case", "SC01-clean", *args], cwd=backend,
            env=environment, capture_output=True, text=True, timeout=30)
        # Child output is never included in failure diagnostics: it may contain a library error.
        if result.returncode not in {0, 23}:
            pytest.fail("local_DEMO_child_failed; credential details suppressed")
        return result.returncode, json.loads(result.stdout.strip().splitlines()[-1])
    code, first = invoke("--crash-after-search")
    assert code == 23 and first["dispatches"] == 1
    code, second = invoke("--run-id", first["run_id"])
    assert code == 0 and second["status"] == "shortlist_review" and second["dispatches"] == 0 and second["candidates"] == 3
    _, third = invoke("--run-id", first["run_id"])
    assert third["status"] == "shortlist_review" and third["dispatches"] == 0


def test_pending_artifact_cannot_be_tampered_into_invented_candidate(engine, local):
    owner, _, ledger, context, brief, gateway = begin(engine, local)
    snapshot = discover(context, brief, gateway, ledger)
    from app.api_schemas import DecisionCreate
    with owner_transaction(engine, owner) as repo:
        pending = repo.get(m.approval_requests, UUID(snapshot["request_id"]))
        bad = pending["artifact"] | {"competitor_ids": [str(uuid4())]}
        repo.conn.execute(update(m.approval_requests).where(m.approval_requests.c.id == pending["id"]).values(artifact=bad))
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        with owner_transaction(engine, owner) as repo:
            repo.decide(context.run_id, "shortlist", DecisionCreate(request_id=snapshot["request_id"], artifact_version=1,
                artifact_hash=snapshot["artifact_hash"], expected_run_version=snapshot["run_version"], decision="approve"), str(uuid4()))
    assert error.value.status_code == 409
