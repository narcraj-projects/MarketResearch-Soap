"""Actual owner-bound saved report/approval/export tests on dedicated local Postgres."""
import hashlib
import os
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import ProgrammingError

from app import models as m
from app.api_schemas import DecisionCreate
from app.config import Settings
from app.main import create_app
from app.repository import digest, owner_transaction
from app.worker import run_once
from tests.test_storage_integration import engine as engine, local as local
from tests.test_workflow_storage_integration import prepared, decide

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not os.environ.get("LATHER_INTEGRATION_CONFIG"), reason="dedicated local config required")]


def ready(engine, local):
    owner, run_id = prepared(engine, local)
    run_once(engine, owner, run_id=run_id)
    decide(engine, owner, run_id, "shortlist")
    assert run_once(engine, owner, run_id=run_id)["state"] == "approval_pending"
    return owner, run_id


def test_ri01_owner_report_approval_saved_exports_and_immutability(local, engine, integration_loop):
    owner, run_id = ready(engine, local)
    settings = Settings(_env_file=None, environment="test", database_url=local["runtime_url"], supabase_url=local["supabase_url"], supabase_publishable_key=local["publishable_key"])
    async def exercise():
        app = create_app(settings)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                headers = {"Authorization": "Bearer " + local["users"][0]["token"]}
                other = {"Authorization": "Bearer " + local["users"][1]["token"]}
                url = f"/api/workspace?run_id={run_id}"
                assert (await client.get(url)).status_code == 401
                assert (await client.get(url, headers=other)).status_code == 404
                response = await client.get(url, headers=headers)
                assert response.status_code == 200
                view = response.json()
                report = view["report"]
                assert report["projection"] == "persisted" and report["approval"]["can_decide"]
                assert report["snapshot"]["coverage"]["genuine_support_coverage"] is None
                assert any(row["unit_price_100g"] is None for row in report["snapshot"]["analysis"]["normalized_prices"])
                assert all(point["y"] is None for point in report["snapshot"]["positioning"])
                download = f"/api/runs/{run_id}/export?report_id={report['id']}"
                assert (await client.get(download + "&format=html", headers=headers)).status_code == 409
                assert (await client.get(download + "&format=csv", headers=other)).status_code == 404
                body = {"request_id": report["approval"]["request_id"], "artifact_version": report["version"], "artifact_hash": report["content_hash"],
                    "expected_run_version": view["run"]["version"], "decision": "approve"}
                path = f"/api/runs/{run_id}/report-decision"
                assert (await client.post(path, headers=other | {"Idempotency-Key": str(uuid4())}, json=body)).status_code == 404
                assert (await client.post(path, headers=headers | {"Idempotency-Key": str(uuid4())}, json=body | {"artifact_hash": "a" * 64})).status_code == 409
                key = str(uuid4())
                first = await client.post(path, headers=headers | {"Idempotency-Key": key}, json=body)
                replay = await client.post(path, headers=headers | {"Idempotency-Key": key}, json=body)
                assert first.status_code == replay.status_code == 200 and first.json() == replay.json()
                assert (await client.get(download + "&format=html", headers=headers)).status_code == 409
                run_once(engine, owner, run_id=run_id)
                saved = (await client.get(url, headers=headers)).json()["report"]
                assert saved["approval"]["state"] == "saved" and saved["export_allowed"]
                for format in ("html", "csv"):
                    exported = await client.get(download + "&format=" + format, headers=headers)
                    repeated = await client.get(download + "&format=" + format, headers=headers)
                    assert exported.status_code == 200 and hashlib.sha256(exported.content).digest() == hashlib.sha256(repeated.content).digest()
                    assert report["content_hash"] in exported.text and "DEMO" in exported.text
                    assert exported.headers["cache-control"] == "no-store" and exported.headers["x-content-type-options"] == "nosniff"
                    assert "attachment;" in exported.headers["content-disposition"]
                assert (await client.get(download + "&format=pdf", headers=headers)).status_code == 422
                history = (await client.get("/api/history/view", headers=headers)).json()
                assert any(entry["id"] == str(run_id) for entry in history["entries"])
                return report
    report = integration_loop.run_until_complete(exercise())
    with owner_transaction(engine, owner) as repo:
        original = repo.get(m.reports, UUID(report["id"]))
        assert digest(original["data"]) == original["content_hash"]
    with pytest.raises(ProgrammingError):
        with owner_transaction(engine, owner) as repo:
            repo.conn.execute(update(m.reports).where(m.reports.c.id == UUID(report["id"])).values(data={"label": "DEMO forged replacement"}))
    with owner_transaction(engine, owner) as repo:
        assert repo.get(m.reports, original["id"])["data"] == original["data"]
        assert len(repo.list(m.approval_decisions, run_id)) == 2


def test_ri02_approval_requires_bound_ready_review_not_just_matching_hash(local, engine):
    owner, run_id = ready(engine, local)
    with owner_transaction(engine, owner) as repo:
        run = repo.get(m.runs, run_id)
        original = repo.report(run_id)
        forged_data = dict(original["data"]) | {"revision": 99}
        forged = repo.create(m.reports, {"run_id": run_id, "version": 99, "content_hash": digest(forged_data), "data": forged_data})
        request = repo.create(m.approval_requests, {"run_id": run_id, "gate": "report", "artifact_version": 99, "artifact_hash": forged["content_hash"], "state": "pending", "artifact": {"report_id": str(forged["id"])}})
        body = DecisionCreate(request_id=request["id"], artifact_version=99, artifact_hash=forged["content_hash"], expected_run_version=run["version"], decision="approve")
        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="independent_review_required"):
            repo.decide(run_id, "report", body, str(uuid4()))
        assert repo.conn.execute(select(m.approval_decisions.c.id).where(m.approval_decisions.c.request_id == request["id"])).first() is None


def test_ri03_explicit_report_id_cannot_cross_runs_even_for_same_owner(local, engine, integration_loop):
    owner, run_id = ready(engine, local)
    _, other_run = prepared(engine, local)
    with owner_transaction(engine, owner) as repo:
        report_id = repo.report(run_id)["id"]
        from app.reporting import history_view
        assert next(entry for entry in history_view(repo, 100, 0).entries if entry.id == other_run).label == "DEMO"
    async def exercise():
        app = create_app(Settings(_env_file=None, environment="test", database_url=local["runtime_url"], supabase_url=local["supabase_url"], supabase_publishable_key=local["publishable_key"]))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                response = await client.get(f"/api/runs/{other_run}/export?format=html&report_id={report_id}", headers={"Authorization": "Bearer " + local["users"][0]["token"]})
                assert response.status_code == 404
    integration_loop.run_until_complete(exercise())
