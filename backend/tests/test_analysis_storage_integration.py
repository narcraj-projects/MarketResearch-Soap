"""Real Postgres Analyst/Reviewer trajectories; all research transport is recorded DEMO."""
from decimal import Decimal
import os

from alembic import command
from alembic.config import Config
import httpx
import pytest
from sqlalchemy import select

from app import models as m
from app.config import Settings
from app.harness.analysis_types import AnalysisDraft
from app.main import create_app
from app.repository import owner_transaction
from app.worker import run_once
from app.workflow import Workflow
from tests.test_workflow_storage_integration import prepared, decide, read
from tests.test_storage_integration import engine as engine, local as local

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not os.environ.get("LATHER_INTEGRATION_CONFIG"), reason="dedicated local config required")]


@pytest.mark.parametrize("always_corrupt", [False, True])
def test_ai01_real_graph_targeted_revision_or_visible_unresolved(local, engine, always_corrupt, integration_loop):
    class CorruptDraft(Workflow):
        def draft(self, state):
            data = super().draft(state)
            if state.revision == 0 or always_corrupt:
                draft = AnalysisDraft.model_validate(data["analysis"])
                row = next(p for p in draft.normalized_prices if p.unit_price_100g is not None)
                draft = draft.model_copy(update={"normalized_prices": tuple(p.model_copy(update={"unit_price_100g": Decimal(999)}) if p == row else p for p in draft.normalized_prices)})
                data["analysis"] = draft.model_dump(mode="json")
            return data
    owner, run_id = prepared(engine, local)
    assert run_once(engine, owner, run_id=run_id)["state"] == "approval_pending"
    decide(engine, owner, run_id, "shortlist")
    result = run_once(engine, owner, run_id=run_id, workflow_factory=CorruptDraft)
    assert result["recorded_web_dispatches"] == 9 and result["recorded_search_dispatches"] == 0
    assert read(engine, owner, run_id)["status"] == ("partial" if always_corrupt else "report_review")
    with owner_transaction(engine, owner) as repo:
        reports = sorted(repo.list(m.reports, run_id), key=lambda row: row["version"])
        receipts = repo.list(m.evaluation_results, run_id)
        assert len(reports) == len(receipts) == 2
        by_report = {row["data"]["report_id"]: row["data"]["assessment"] for row in receipts}
        assert by_report[str(reports[0]["id"])]["decision"] == "revise"
        assert by_report[str(reports[1]["id"])]["decision"] == ("unresolved" if always_corrupt else "ready_for_human")
        assert any(p["unit_price_100g"] == "999" for p in reports[0]["data"]["analysis"]["normalized_prices"])
        for section in ("findings", "opportunities", "comparisons", "conflicts"):
            assert reports[0]["data"]["analysis"][section] == reports[1]["data"]["analysis"][section]
        assert reports[0]["data"]["analysis"]["input_hash"] == reports[1]["data"]["analysis"]["input_hash"]
        assert len(reports[1]["data"]["methodology"]["correction_targets"]) == 1
        assert len(repo.list(m.tool_attempts, run_id)) == 10
        assert all(row["data"]["assessment"]["genuine_support_coverage"] is None for row in receipts)
        approval = [row for row in repo.list(m.approval_requests, run_id) if row["gate"] == "report"]
        assert len(approval) == (0 if always_corrupt else 1)
        if approval:
            assert approval[0]["artifact_version"] == 2 and approval[0]["artifact_hash"] == reports[1]["content_hash"]
    settings = Settings(_env_file=None, environment="test", database_url=local["runtime_url"], supabase_url=local["supabase_url"], supabase_publishable_key=local["publishable_key"])
    async def exercise():
        app = create_app(settings)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                headers = {"Authorization": "Bearer " + local["users"][0]["token"]}
                report = await client.get(f"/api/runs/{run_id}/report", headers=headers)
                assert report.status_code == 200
                assert report.json()["review"]["decision"] == ("unresolved" if always_corrupt else "ready_for_human")
                assert report.json()["review"]["genuine_support_coverage"] is None
                other = {"Authorization": "Bearer " + local["users"][1]["token"]}
                assert (await client.get(f"/api/runs/{run_id}/report", headers=other)).status_code == 404
    integration_loop.run_until_complete(exercise())
    if not always_corrupt:
        decide(engine, owner, run_id, "report")
        saved = run_once(engine, owner, run_id=run_id)
        assert saved["recorded_web_dispatches"] == 0 and read(engine, owner, run_id)["status"] == "complete"


def test_ai02_unverified_raw_weight_is_null_and_blocks_unsafe_rollback(local, engine, monkeypatch):
    owner, run_id = prepared(engine, local)
    with owner_transaction(engine, owner) as repo:
        competitor = repo.create(m.competitors, {"run_id": run_id, "name": "DEMO normalization-only", "canonical_url": "https://example.invalid/demo"})
        source = repo.create(m.sources, {"run_id": run_id, "canonical_url": "https://example.invalid/demo", "title": "DEMO", "publisher": "DEMO",
            "retrieved_at": repo.get(m.runs, run_id)["created_at"], "content_hash": "a" * 64, "access_status": "ok"})
        product = repo.create(m.products, {"run_id": run_id, "competitor_id": competitor["id"], "sku": "DEMO-only", "name": "DEMO", "attributes": {"label": "DEMO"}})
        price = repo.create(m.prices, {"run_id": run_id, "product_id": product["id"], "source_id": source["id"], "amount": Decimal(120), "currency": "INR",
            "total_weight_g": Decimal(100), "pack_qty": 1, "observed_at": repo.get(m.runs, run_id)["created_at"]})
        assert price["unit_price_100g"] is None and price["normalization_data"] is None
    monkeypatch.setenv("LATHER_DATABASE_URL", local["admin_url"])
    with pytest.raises(RuntimeError, match="unverified_weight_prevents_safe_downgrade"):
        command.downgrade(Config("alembic.ini"), "0005")
    with owner_transaction(engine, owner) as repo:
        assert repo.get(m.prices, price["id"])["total_weight_g"] == Decimal(100)
        assert repo.conn.execute(select(m.prices.c.unit_price_100g).where(m.prices.c.id == price["id"])).scalar_one() is None


def test_ai03_durable_review_receipt_is_idempotent(local, engine):
    owner, run_id = prepared(engine, local)
    run_once(engine, owner, run_id=run_id)
    decide(engine, owner, run_id, "shortlist")
    assert run_once(engine, owner, run_id=run_id)["state"] == "approval_pending"
    with owner_transaction(engine, owner) as repo:
        report = repo.report(run_id)
        receipts = repo.list(m.evaluation_results, run_id)
        assert len(receipts) == 1 and report["review"]["decision"] == "ready_for_human"
    assert run_once(engine, owner, run_id=run_id)["state"] == "idle"
    with owner_transaction(engine, owner) as repo:
        assert repo.list(m.evaluation_results, run_id) == receipts


def test_ai04_malformed_draft_is_flagged_unresolved_without_unsafe_repair(local, engine):
    class MalformedDraft(Workflow):
        def draft(self, state):
            data = super().draft(state)
            data["analysis"]["opportunities"] = "DEMO malformed output, not a list"
            return data
    owner, run_id = prepared(engine, local)
    run_once(engine, owner, run_id=run_id)
    decide(engine, owner, run_id, "shortlist")
    result = run_once(engine, owner, run_id=run_id, workflow_factory=MalformedDraft)
    assert result["state"] == "finished" and read(engine, owner, run_id)["status"] == "partial"
    with owner_transaction(engine, owner) as repo:
        assert len(repo.list(m.reports, run_id)) == 1
        assert repo.report(run_id)["review"]["decision"] == "unresolved"
        assert repo.report(run_id)["review"]["issues"][0]["code"] == "schema_invalid"
        assert not any(r["gate"] == "report" for r in repo.list(m.approval_requests, run_id))
