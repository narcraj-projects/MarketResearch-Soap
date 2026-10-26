"""Real local Auth/RLS historical versions and diff; all evidence is generated DEMO."""
import os
from uuid import UUID

import httpx
import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.exc import ProgrammingError

from app import models as m
from app.config import Settings
from app.main import create_app
from app.repository import digest, owner_transaction
from tests.history_storage_support import seed_history
from tests.test_storage_integration import engine as engine, local as local

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not os.environ.get("LATHER_INTEGRATION_CONFIG"), reason="dedicated local config required")]


def test_hi01_multiple_versions_price_change_owner_isolation_and_immutability(local, engine, integration_loop):
    owner = UUID(local["users"][0]["id"])
    earlier, reports = seed_history(engine, owner, revisions=True)
    later, recent = seed_history(engine, owner, "price", later=True)
    async def exercise():
        app = create_app(Settings(_env_file=None, environment="test", database_url=local["runtime_url"], supabase_url=local["supabase_url"], supabase_publishable_key=local["publishable_key"]))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                headers = {"Authorization": "Bearer " + local["users"][0]["token"]}
                other = {"Authorization": "Bearer " + local["users"][1]["token"]}
                path = f"/api/history/diff?before_run={earlier}&after_run={later}&before_version=2&after_version=1"
                for route in (path, f"/api/runs/{earlier}/versions", f"/api/workspace?run_id={earlier}&report_version=1"):
                    assert (await client.get(route)).status_code == 401
                    assert (await client.get(route, headers=other)).status_code == 404
                versions = await client.get(f"/api/runs/{earlier}/versions", headers=headers)
                assert versions.status_code == 200 and versions.json()["total"] == 2
                assert [v["comparable"] for v in versions.json()["entries"]] == [True, False]
                assert [v["version"] for v in versions.json()["entries"]] == [2, 1]
                first = await client.get(f"/api/workspace?run_id={earlier}&report_version=1", headers=headers)
                assert first.status_code == 200 and first.json()["report"]["content_hash"] == reports[0]["content_hash"]
                assert not first.json()["report"]["export_allowed"]
                assert (await client.get(f"/api/workspace?run_id={earlier}&report_version=99", headers=headers)).status_code == 404
                assert (await client.get("/api/workspace?report_version=1", headers=headers)).status_code == 422
                result = await client.get(path, headers=headers)
                assert result.status_code == 200 and result.headers["cache-control"] == "no-store"
                assert result.json() == (await client.get(path, headers=headers)).json()
                assert result.json()["counts"]["changed"] == 1 and result.json()["counts"]["gone"] == 0
                price = next(row for row in result.json()["changes"] if row["status"] == "changed")
                assert price["field"] == "price" and price["before"]["values"][0]["amount"] == "120" and price["after"]["values"][0]["amount"] == "140"
                assert price["before"]["evidence"] and price["after"]["evidence"]
                assert (await client.get(path.replace("before_version=2", "before_version=1"), headers=headers)).status_code == 409
                other_run, _ = seed_history(engine, UUID(local["users"][1]["id"]), later=True)
                assert (await client.get(path.replace(str(later), str(other_run)), headers=headers)).status_code == 404
                history = (await client.get("/api/history/view", headers=headers)).json()
                assert next(row for row in history["entries"] if row["id"] == str(earlier))["saved_report_version"] == 2
                assert next(row for row in history["entries"] if row["id"] == str(earlier))["saved_as_of"].startswith("2026-10-11T12:00:00")
                return first.json()["report"]["snapshot"]
    original = integration_loop.run_until_complete(exercise())
    for statement in (update(m.reports).values(data={"label": "DEMO tamper"}), delete(m.reports)):
        with pytest.raises(ProgrammingError):
            with owner_transaction(engine, owner) as repo:
                repo.conn.execute(statement.where(m.reports.c.id == reports[0]["id"]))
    with owner_transaction(engine, owner) as repo:
        stored = repo.get(m.reports, reports[0]["id"])
        assert stored["data"]["presentation"] == original and digest(stored["data"]) == reports[0]["content_hash"]
        assert repo.get(m.reports, recent[0]["id"])["content_hash"] == recent[0]["content_hash"]


def test_hi02_unavailable_website_retains_dated_before_values_without_gone(local, engine):
    from app.history import diff
    owner = UUID(local["users"][0]["id"])
    earlier, _ = seed_history(engine, owner)
    later, _ = seed_history(engine, owner, "unavailable", later=True)
    with owner_transaction(engine, owner) as repo:
        result = diff(repo, earlier, later, 1, 1)
        assert result.counts["gone"] == 0 and result.counts["unknown"] > 0
        row = next(row for row in result.changes if row.brand == "DEMO Maker A" and row.field == "price")
        assert row.status == "unknown" and row.before.values[0]["amount"] == "120"
        assert not row.after.values and row.after.evidence[0].source.access_status == "unavailable"
        assert "not_discontinued" in row.reason


def test_hi03_explicit_discontinued_is_narrow_attribution_and_diff_reads_write_nothing(local, engine):
    from app.history import diff
    owner = UUID(local["users"][0]["id"])
    earlier, _ = seed_history(engine, owner)
    later, _ = seed_history(engine, owner, "gone", later=True)
    with owner_transaction(engine, owner) as repo:
        before = [dict(row) for row in repo.conn.execute(select(m.reports).where(m.reports.c.run_id.in_([earlier, later]))).mappings()]
        result = diff(repo, earlier, later, 1, 1)
        assert result.counts["gone"] == 1
        gone = next(row for row in result.changes if row.status == "gone")
        assert gone.field == "availability" and "source_reports_discontinued" in gone.reason
        assert "Discontinued" in gone.after.evidence[0].quote
        assert before == [dict(row) for row in repo.conn.execute(select(m.reports).where(m.reports.c.run_id.in_([earlier, later]))).mappings()]


def test_hi04_invalid_legacy_sibling_and_mismatched_presentation_do_not_hide_valid_history(local, engine):
    from copy import deepcopy
    from app.history import versions
    from app.reporting import report_view
    owner = UUID(local["users"][0]["id"])
    run_id, reports = seed_history(engine, owner)
    with owner_transaction(engine, owner) as repo:
        repo.create(m.reports, {"run_id": run_id, "version": 2, "content_hash": "a" * 64, "data": {"label": "DEMO", "legacy": "invalid digest fixture"}})
        data = deepcopy(reports[0]["data"])
        data["presentation"]["analysis"]["as_of"] = "2026-01-01T00:00:00Z"
        invalid = repo.create(m.reports, {"run_id": run_id, "version": 3, "content_hash": digest(data), "data": data})
        value = report_view(repo, repo.get(m.runs, run_id), invalid)
        assert value.snapshot is None and not value.export_allowed and not value.approval.can_decide
        listed = versions(repo, run_id)
        assert [entry.comparable for entry in listed.entries] == [False, False, True]
        assert listed.entries[1].approval == "integrity_error" and listed.entries[2].version == 1
