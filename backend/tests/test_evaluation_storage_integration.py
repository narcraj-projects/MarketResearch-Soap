"""ER: real Auth/owner isolation and hash-bound human review protocol. DEMO only."""
import os
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.exc import ProgrammingError

from app import models as m
from app.config import Settings
from app.evaluations.dataset import Dataset
from app.evaluations.review import CHECKS, coverage, packet
from app.evaluations.runner import GoldenRunner
from app.main import create_app
from app.repository import owner_transaction
from app.worker import run_once
from tests.test_storage_integration import engine as engine, local as local

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not os.environ.get("LATHER_INTEGRATION_CONFIG"), reason="dedicated local configuration required")]


def settings(local, *, granted=True):
    owner = UUID(local["users"][0]["id"])
    return Settings(_env_file=None, environment="test", evaluations_enabled=True, chaos_enabled=True,
        trusted_reviewer_ids=(owner,) if granted else (), business_owner_ids=(owner,) if granted else (),
        database_url=local["runtime_url"], supabase_url=local["supabase_url"], supabase_publishable_key=local["publishable_key"])


def prepared(engine, local, *, saved=False):
    cfg = settings(local)
    runner = GoldenRunner(engine, UUID(local["users"][0]["id"]), UUID(local["users"][1]["id"]), cfg)
    case = Dataset().case("D01")
    identifier = runner.create(case)
    runner.worker(case, identifier)
    runner.approve(identifier, "shortlist")
    runner.worker(case, identifier)
    if saved:
        runner.approve(identifier, "report")
        runner.worker(case, identifier)
    with owner_transaction(engine, runner.owner) as repo:
        report = repo.report(identifier)
        current = packet(repo, identifier, report["id"])
    return runner, identifier, report, current


def support_body(report, current):
    claim = next(row for row in current["claims"] if row["evidence"] and all(ref["provenance_intact"] for ref in row["evidence"]))
    return {"report_id": str(report["id"]), "report_hash": report["content_hash"], "claim_id": claim["claim_id"], "statement_hash": claim["statement_hash"],
        "disposition": "insufficient", "source_ids": [claim["evidence"][0]["source_id"]], "checks_completed": list(CHECKS),
        "rationale": "DEMO fixture only, not a human support adjudication.", "purpose": "demo_fixture",
        "attestation": "I personally reviewed every factual component and its evidence"}


def test_er01_real_auth_role_owner_hash_idempotency_and_no_fixture_score(local, engine, integration_loop):
    runner, run_id, report, current = prepared(engine, local)
    async def exercise():
        app = create_app(settings(local))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                path = f"/api/runs/{run_id}/claim-reviews"
                headers = {"Authorization": "Bearer " + local["users"][0]["token"], "Idempotency-Key": str(uuid4())}
                body = support_body(report, current)
                assert (await client.post(path, json=body, headers={"Idempotency-Key": str(uuid4())})).status_code == 401
                other = {"Authorization": "Bearer " + local["users"][1]["token"]}
                assert (await client.get(f"/api/runs/{run_id}/review-packet?report_id={report['id']}", headers=other)).status_code == 404
                first = await client.post(path, json=body, headers=headers)
                repeated = await client.post(path, json=body, headers=headers)
                assert first.status_code == repeated.status_code == 201 and first.json() == repeated.json()
                assert (await client.post(path, json=body | {"rationale": "DEMO changed payload conflicts"}, headers=headers)).status_code == 409
                assert (await client.post(path, json=body | {"report_hash": "0" * 64}, headers=headers | {"Idempotency-Key": str(uuid4())})).status_code == 409
                assert (await client.post(path, json=body | {"source_ids": [str(uuid4())]}, headers=headers | {"Idempotency-Key": str(uuid4())})).status_code == 409
                assert (await client.post(path, json=body | {"reviewer_id": local["users"][0]["id"]}, headers=headers)).status_code == 422
                measured = await client.get(f"/api/runs/{run_id}/review-metrics?report_id={report['id']}", headers=headers)
                assert measured.status_code == 200 and measured.json()["support_coverage"] is None
    integration_loop.run_until_complete(exercise())
    with owner_transaction(engine, runner.owner) as repo:
        rows = repo.list(m.evaluation_results, run_id, limit=1000)
        assert coverage(current, rows, settings(local).trusted_reviewer_ids)["support_coverage"] is None
        assert repo.get(m.reports, report["id"])["data"] == report["data"]


def test_er02_authenticated_owner_without_server_grant_cannot_self_certify(local, engine, integration_loop):
    _, run_id, report, current = prepared(engine, local)
    async def exercise():
        app = create_app(settings(local, granted=False))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                response = await client.post(f"/api/runs/{run_id}/claim-reviews", json=support_body(report, current),
                    headers={"Authorization": "Bearer " + local["users"][0]["token"], "Idempotency-Key": str(uuid4())})
                assert response.status_code == 403 and response.json()["detail"] == "trusted_human_reviewer_required"
    integration_loop.run_until_complete(exercise())


def test_er03_owner_rating_requires_saved_version_and_fixture_rating_is_explicit(local, engine, integration_loop):
    runner, run_id, report, _ = prepared(engine, local)
    body = {"report_id": str(report["id"]), "report_hash": report["content_hash"], "useful": True, "purpose": "demo_fixture",
        **{field: "DEMO protocol fixture, not a real owner opinion" for field in ["relevance", "evidence_clarity", "comparability", "actionable_hypotheses", "limitations"]},
        "attestation": "I am the business owner and personally assessed this report"}
    async def send(expected):
        app = create_app(settings(local))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                response = await client.post(f"/api/runs/{run_id}/owner-ratings", json=body,
                    headers={"Authorization": "Bearer " + local["users"][0]["token"], "Idempotency-Key": str(uuid4())})
                assert response.status_code == expected
                if expected == 201:
                    assert response.json()["purpose"] == "demo_fixture"
    integration_loop.run_until_complete(send(409))
    runner.approve(run_id, "report")
    runner.worker(Dataset().case("D01"), run_id)
    integration_loop.run_until_complete(send(201))


def test_er04_review_receipts_cannot_be_overwritten_by_runtime_role(local, engine):
    runner, run_id, _, _ = prepared(engine, local, saved=True)
    with owner_transaction(engine, runner.owner) as repo:
        receipt = repo.list(m.evaluation_results, run_id)[0]
    with pytest.raises(ProgrammingError):
        with owner_transaction(engine, runner.owner) as repo:
            repo.conn.execute(update(m.evaluation_results).where(m.evaluation_results.c.id == receipt["id"]).values(outcome="fake_pass"))


def test_er05_production_worker_rejects_persisted_evaluation_plan_before_tools(local, engine):
    runner = GoldenRunner(engine, UUID(local["users"][0]["id"]), UUID(local["users"][1]["id"]), settings(local))
    identifier = runner.create(Dataset().case("D01"))
    response = run_once(engine, runner.owner, run_id=identifier, settings=Settings(_env_file=None, environment="production"))
    assert response["state"] == "stopped" and response["actual_external_calls"] == 0
    with owner_transaction(engine, runner.owner) as repo:
        assert not repo.list(m.tool_attempts, identifier) and not repo.list(m.sources, identifier)


def test_er06_timeout_wait_precedes_origin_lock_when_third_lane_arrives_first(local, engine, monkeypatch):
    from threading import Event
    import app.agents.researcher as researchers
    arrived = Event()
    class ObservedGate:
        def __init__(self):
            self.ready = Event()
        def wait(self, timeout):
            arrived.set()
            return self.ready.wait(timeout)
        def set(self):
            self.ready.set()
    original = researchers.research_one
    def third_first(context, competitor, gateway, store):
        if competitor["name"] != "DEMO Maker C":
            assert arrived.wait(5)
        return original(context, competitor, gateway, store)
    monkeypatch.setattr("app.evaluations.workflow.Event", ObservedGate)
    monkeypatch.setattr(researchers, "research_one", third_first)
    runner = GoldenRunner(engine, UUID(local["users"][0]["id"]), UUID(local["users"][1]["id"]), settings(local))
    outcome = runner.execute(Dataset().case("D04"))
    assert outcome.passed
    assert outcome.measurement.virtual_retry_delays_seconds == (0.5, 1.0)
