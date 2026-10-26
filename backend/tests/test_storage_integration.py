"""Real local Supabase Auth/Postgres tests; never SQLite or hosted projects."""
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID, uuid4
from datetime import datetime, timezone
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor

from alembic import command
from alembic.config import Config
import httpx
import psycopg
import pytest
from sqlalchemy import create_engine, insert, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, ProgrammingError

from app import models as m
from app.api_schemas import DecisionCreate, RunCreate
from app.config import Settings
from app.main import create_app
from app.repository import owner_transaction

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not os.environ.get("LATHER_INTEGRATION_CONFIG"), reason="explicit dedicated local Supabase config required")]
HASH = "a" * 64


class LocalConfig(dict):
    def __repr__(self):
        return "<local Supabase configuration: credentials redacted>"


@pytest.fixture(scope="module")
def local():
    data = json.loads(Path(os.environ["LATHER_INTEGRATION_CONFIG"]).read_text(encoding="utf-8"))
    for field in ("runtime_url", "admin_url"):
        url = make_url(data[field])
        if url.host != "127.0.0.1" or url.port != 57422:
            raise RuntimeError("dedicated_local_database_required")
    url = urlparse(data["supabase_url"])
    if url.hostname != "127.0.0.1" or url.port != 57421:
        raise RuntimeError("dedicated_local_auth_required")
    with psycopg.connect(data["admin_url"].replace("postgresql+psycopg://", "postgresql://")) as admin:
        if admin.execute("SELECT instance FROM lather_test_control.identity WHERE id=1").fetchone()[0] != data["test_instance"]:
            raise RuntimeError("dedicated_test_database_identity_mismatch")
    return LocalConfig(data)


@pytest.fixture
def engine(local):
    engine = create_engine(local["runtime_url"], hide_parameters=True, pool_size=1, max_overflow=5)
    yield engine
    engine.dispose()


def seed(engine, owner):
    with owner_transaction(engine, owner) as repo:
        brief = repo.create(m.briefs, {"category": "DEMO soap", "geography": "DEMO India", "customer": "DEMO founder", "objective": "DEMO comparison", "known_competitors": [], "version": 1})
        body = RunCreate(brief_id=brief["id"], budget={"max_calls": 3, "max_tokens": 1000, "max_cost_usd": "0"})
        run = repo.start(body, str(uuid4()))
    return brief, run


def test_real_supabase_auth_and_cross_user_api(local, integration_loop, engine):
    a, b = local["users"]
    brief, run = seed(engine, UUID(a["id"]))
    populate_all(engine, UUID(a["id"]), UUID(run["id"]))
    settings = Settings(_env_file=None, environment="test", database_url=local["runtime_url"], supabase_url=local["supabase_url"], supabase_publishable_key=local["publishable_key"])
    async def exercise():
        app = create_app(settings)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                headers_a = {"Authorization": "Bearer " + a["token"]}
                headers_b = {"Authorization": "Bearer " + b["token"]}
                assert (await client.get("/api/auth/me", headers=headers_a)).json() == {"user_id": a["id"]}
                for path in (f"/api/briefs/{brief['id']}", f"/api/runs/{run['id']}", f"/api/runs/{run['id']}/events"):
                    assert (await client.get(path, headers=headers_a)).status_code == 200
                    assert (await client.get(path, headers=headers_b)).status_code == 404
                for resource in ("competitors", "sources", "claims", "products", "prices", "reports", "approvals", "evals", "usage"):
                    assert (await client.get(f"/api/runs/{run['id']}/{resource}", headers=headers_a)).status_code == 200
                    assert (await client.get(f"/api/runs/{run['id']}/{resource}", headers=headers_b)).status_code == 404
                assert (await client.get("/api/auth/me", headers={"Authorization": "Bearer DEMO.invalid.token"})).status_code == 401
                response = await client.post("/api/briefs", headers=headers_a, json={"category": "DEMO soap", "geography": "DEMO India", "customer": "DEMO founder", "objective": "DEMO research", "owner_id": b["id"]})
                assert response.status_code == 422
                headers_a["Idempotency-Key"] = str(uuid4())
                body = {"brief_id": str(brief["id"]), "budget": {"max_calls": 3, "max_tokens": 1000, "max_cost_usd": "0"}}
                assert (await client.post("/api/runs", headers=headers_b | {"Idempotency-Key": str(uuid4())}, json=body)).status_code == 404
                first = await client.post("/api/runs", headers=headers_a, json=body)
                second = await client.post("/api/runs", headers=headers_a, json=body)
                assert first.status_code == second.status_code == 201
                assert first.json() == second.json()
                body["budget"]["max_calls"] = 4
                assert (await client.post("/api/runs", headers=headers_a, json=body)).status_code == 409
    integration_loop.run_until_complete(exercise())


def test_rls_all_tables_and_pool_identity_reset(local, engine):
    a, b = [UUID(user["id"]) for user in local["users"]]
    brief, run = seed(engine, a)
    populate_all(engine, a, UUID(run["id"]))
    _, other_run = seed(engine, b)
    populate_all(engine, b, UUID(other_run["id"]))
    with owner_transaction(engine, a) as repo:
        assert repo.conn.execute(text("SELECT current_user")).scalar_one() == "lather_api"
        for table in m.TABLES.values():
            rows = repo.conn.execute(select(table)).mappings().all()
            assert rows and all(row["owner_id"] == a for row in rows)
    for owner in (b, a, b):
        with owner_transaction(engine, owner) as repo:
            for table in m.TABLES.values():
                rows = repo.conn.execute(select(table)).mappings().all()
                assert rows and all(row["owner_id"] == owner for row in rows)
            visible = repo.conn.execute(select(m.briefs).where(m.briefs.c.id == brief["id"])).first()
            assert (visible is not None) == (owner == a)
    with pytest.raises(ProgrammingError):
        with owner_transaction(engine, b) as repo:
            repo.conn.execute(insert(m.briefs).values(id=uuid4(), owner_id=a, category="DEMO", geography="DEMO", customer="DEMO", objective="DEMO", known_competitors=[], version=1))
    with psycopg.connect(local["admin_url"].replace("postgresql+psycopg://", "postgresql://")) as admin:
        enabled = admin.execute("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname = ANY(%s) AND c.relrowsecurity AND c.relforcerowsecurity", (list(m.TABLES),)).fetchone()[0]
        assert enabled == len(m.TABLES)


def populate_all(engine, owner, run_id):
    with owner_transaction(engine, owner) as repo:
        competitor = repo.create(m.competitors, {"run_id": run_id, "name": "DEMO", "canonical_url": "https://example.invalid"})
        source = repo.create(m.sources, {"run_id": run_id, "canonical_url": "https://example.invalid", "title": "DEMO", "publisher": "DEMO", "retrieved_at": datetime.now(timezone.utc), "content_hash": HASH, "access_status": "ok"})
        claim = repo.create(m.claims, {"run_id": run_id, "text": "DEMO", "kind": "fact", "material": True, "review_status": "unreviewed"})
        repo.create(m.claim_sources, {"run_id": run_id, "claim_id": claim["id"], "source_id": source["id"], "quote": "DEMO", "excerpt_hash": HASH})
        product = repo.create(m.products, {"run_id": run_id, "competitor_id": competitor["id"], "sku": "DEMO", "name": "DEMO", "attributes": {"label": "DEMO"}})
        repo.create(m.prices, {"run_id": run_id, "product_id": product["id"], "source_id": source["id"], "amount": Decimal("100"), "currency": "INR", "total_weight_g": None, "pack_qty": 1, "observed_at": datetime.now(timezone.utc)})
        report = repo.create(m.reports, {"run_id": run_id, "version": 1, "content_hash": HASH, "data": {"label": "DEMO"}})
        pending = repo.create(m.approval_requests, {"run_id": run_id, "gate": "report", "artifact_version": 1, "artifact_hash": HASH, "state": "pending", "artifact": {"report_id": str(report["id"])}})
        repo.create(m.approval_decisions, {"run_id": run_id, "request_id": pending["id"], "decision": "reject", "artifact_version": 1, "artifact_hash": HASH})
        case = repo.create(m.evaluation_cases, {"case_id": "DEMO-case", "dataset_version": "DEMO-v1", "data": {"label": "DEMO"}})
        repo.create(m.evaluation_results, {"run_id": run_id, "case_id": case["id"], "outcome": "DEMO", "data": {"label": "DEMO"}})
        repo.create(m.usage, {"run_id": run_id, "operation_id": uuid4(), "attempt": 1, "calls": 0, "tokens": 0, "cost_usd": Decimal("0")})
        repo.create(m.tool_attempts, {"run_id": run_id, "operation_id": uuid4(), "attempt": 1, "request_hash": HASH,
            "cost_upper_bound_usd": Decimal("0"), "state": "reserved", "outcome": None})
        repo.create(m.source_documents, {"run_id": run_id, "source_id": source["id"], "body": "DEMO", "excerpt": "DEMO", "text_hash": HASH,
            "structured": [], "links": [], "reason": None})
        repo.create(m.research_tasks, {"run_id": run_id, "competitor_id": competitor["id"], "state": "partial", "data": {"label": "DEMO"}})
        repo.create(m.graph_checkpoints, {"run_id": run_id, "namespace": "", "checkpoint_id": "DEMO-rls", "parent_id": None,
            "encoding": "msgpack", "payload": b"DEMO", "metadata": {"label": "DEMO"}, "graph_version": "DEMO"})
        repo.create(m.graph_writes, {"run_id": run_id, "namespace": "", "checkpoint_id": "DEMO-rls", "task_id": "DEMO", "write_index": 0,
            "channel": "DEMO", "encoding": "msgpack", "payload": b"DEMO", "task_path": "DEMO"})


def test_every_table_rejects_spoofed_owner(local, engine):
    a, b = [UUID(user["id"]) for user in local["users"]]
    _, run = seed(engine, a)
    populate_all(engine, a, UUID(run["id"]))
    for table in m.TABLES.values():
        with owner_transaction(engine, a) as repo:
            row = dict(repo.conn.execute(select(table).limit(1)).mappings().one())
        row["id"] = uuid4()
        row["owner_id"] = b
        row.pop("unit_price_100g", None)
        with pytest.raises(ProgrammingError) as error:
            with owner_transaction(engine, a) as repo:
                repo.conn.execute(insert(table).values(**row))
        assert error.value.orig.sqlstate == "42501"


def test_cross_owner_and_cross_run_foreign_keys(local, engine):
    a, b = [UUID(user["id"]) for user in local["users"]]
    brief_a, run_a = seed(engine, a)
    _, run_b = seed(engine, b)
    with pytest.raises(IntegrityError):
        with owner_transaction(engine, b) as repo:
            repo.create(m.runs, {"brief_id": brief_a["id"], "status": "queued", "version": 1, "budget": {}})
    with owner_transaction(engine, a) as repo:
        source = repo.create(m.sources, {"run_id": run_a["id"], "canonical_url": "https://example.invalid/demo", "title": "DEMO source", "publisher": "DEMO", "retrieved_at": datetime.now(timezone.utc), "content_hash": HASH, "access_status": "ok"})
    with pytest.raises(IntegrityError):
        with owner_transaction(engine, b) as repo:
            claim = repo.create(m.claims, {"run_id": run_b["id"], "text": "DEMO claim", "kind": "fact", "material": True, "review_status": "unreviewed"})
            repo.create(m.claim_sources, {"run_id": run_b["id"], "claim_id": claim["id"], "source_id": source["id"], "quote": "DEMO", "excerpt_hash": HASH})
    _, second_a_run = seed(engine, a)
    with pytest.raises(IntegrityError):
        with owner_transaction(engine, a) as repo:
            claim = repo.create(m.claims, {"run_id": second_a_run["id"], "text": "DEMO other-run claim", "kind": "fact", "material": True, "review_status": "unreviewed"})
            repo.create(m.claim_sources, {"run_id": second_a_run["id"], "claim_id": claim["id"], "source_id": source["id"], "quote": "DEMO", "excerpt_hash": HASH})


def test_concurrent_start_has_one_job_and_one_event(local, engine):
    owner = UUID(local["users"][0]["id"])
    brief, _ = seed(engine, owner)
    body = RunCreate(brief_id=brief["id"], budget={"max_calls": 3, "max_tokens": 1000, "max_cost_usd": "0"})
    key = str(uuid4())
    def start():
        with owner_transaction(engine, owner) as repo:
            return repo.start(body, key)
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(lambda _: start(), range(4)))
    assert len({record["id"] for record in records}) == 1
    run_id = UUID(records[0]["id"])
    with owner_transaction(engine, owner) as repo:
        assert len(repo.list(m.jobs, run_id)) == 1
        assert len(repo.list(m.events, run_id)) == 1


def test_approval_idempotency_stale_version_and_immutability(local, engine, integration_loop):
    a, b = local["users"]
    owner = UUID(a["id"])
    _, run = seed(engine, owner)
    run_id = UUID(run["id"])
    with owner_transaction(engine, owner) as repo:
        repo.conn.execute(m.runs.update().where(m.runs.c.id == run_id).values(status="report_review", version=2))
        report = repo.create(m.reports, {"run_id": run_id, "version": 1, "content_hash": HASH, "data": {"label": "DEMO", "limitations": ["DEMO report for authorization testing only"]}})
        pending = repo.create(m.approval_requests, {"run_id": run_id, "gate": "report", "artifact_version": 1, "artifact_hash": HASH, "state": "pending", "artifact": {"report_id": str(report["id"])}})
    async def exercise():
        app = create_app(Settings(_env_file=None, environment="test", database_url=local["runtime_url"], supabase_url=local["supabase_url"], supabase_publishable_key=local["publishable_key"]))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                path = f"/api/runs/{run_id}/report-decision"
                body = {"request_id": str(pending["id"]), "artifact_version": 1, "artifact_hash": HASH, "expected_run_version": 2, "decision": "approve"}
                headers = {"Authorization": "Bearer " + a["token"], "Idempotency-Key": str(uuid4())}
                wrong = headers | {"Authorization": "Bearer " + b["token"]}
                assert (await client.post(path, headers=wrong, json=body)).status_code == 404
                assert (await client.post(path, headers=headers, json=body | {"artifact_hash": "b" * 64})).status_code == 409
                first = await client.post(path, headers=headers, json=body)
                second = await client.post(path, headers=headers, json=body)
                assert first.status_code == second.status_code == 200
                assert first.json() == second.json()
                assert (await client.post(path, headers=headers, json=body | {"decision": "reject"})).status_code == 409
                assert (await client.get(f"/api/runs/{run_id}/report", headers=headers)).json()["id"] == str(report["id"])
    integration_loop.run_until_complete(exercise())
    with pytest.raises(ProgrammingError):
        with owner_transaction(engine, owner) as repo:
            repo.conn.execute(m.reports.update().where(m.reports.c.id == report["id"]).values(content_hash="b" * 64))


def test_browser_role_cannot_write_approvals_or_cross_read(local):
    a, b = local["users"]
    with httpx.Client(timeout=5) as client:
        headers = {"apikey": local["publishable_key"], "Authorization": "Bearer " + b["token"]}
        response = client.get(local["supabase_url"] + "/rest/v1/briefs", headers=headers, params={"owner_id": "eq." + a["id"]})
        assert response.status_code == 200
        assert response.json() == []
        response = client.post(local["supabase_url"] + "/rest/v1/approval_decisions", headers=headers, json={"id": str(uuid4()), "owner_id": b["id"]})
        assert response.status_code in {401, 403}
        response = client.get(local["supabase_url"] + "/rest/v1/briefs", headers={"apikey": local["publishable_key"]})
        assert response.status_code in {401, 403}


def test_real_price_arithmetic_and_missing_weight(local, engine):
    owner = UUID(local["users"][0]["id"])
    _, run = seed(engine, owner)
    run_id = UUID(run["id"])
    with owner_transaction(engine, owner) as repo:
        competitor = repo.create(m.competitors, {"run_id": run_id, "name": "DEMO maker", "canonical_url": "https://example.invalid"})
        product = repo.create(m.products, {"run_id": run_id, "competitor_id": competitor["id"], "sku": "DEMO-pack", "name": "DEMO pack", "attributes": {"label": "DEMO"}})
        source = repo.create(m.sources, {"run_id": run_id, "canonical_url": "https://example.invalid/demo", "title": "DEMO", "publisher": "DEMO", "retrieved_at": datetime.now(timezone.utc), "content_hash": HASH, "access_status": "ok"})
        values = {"run_id": run_id, "product_id": product["id"], "source_id": source["id"], "amount": Decimal("240"), "currency": "INR", "pack_qty": 2, "observed_at": datetime.now(timezone.utc)}
        known = repo.create(m.prices, values | {"total_weight_g": Decimal("200"), "normalization_data": {"schema_version": "normalization-1.0", "eligible": True}})
        missing = repo.create(m.prices, values | {"total_weight_g": None})
        assert known["unit_price_100g"] == Decimal("120")
        assert missing["unit_price_100g"] is None
        unverified = repo.create(m.prices, values | {"total_weight_g": Decimal("200")})
        assert unverified["unit_price_100g"] is None


def test_concurrent_shortlist_approval_and_stale_replay(local, engine):
    owner = UUID(local["users"][0]["id"])
    _, run = seed(engine, owner)
    run_id = UUID(run["id"])
    with owner_transaction(engine, owner) as repo:
        competitor = repo.create(m.competitors, {"run_id": run_id, "name": "DEMO supported candidate", "canonical_url": "https://example.invalid"})
        repo.conn.execute(m.runs.update().where(m.runs.c.id == run_id).values(status="shortlist_review", version=2))
        pending = repo.create(m.approval_requests, {"run_id": run_id, "gate": "shortlist", "artifact_version": 1, "artifact_hash": HASH, "state": "pending",
            "artifact": {"competitor_ids": [str(competitor["id"])], "insufficiency_reason": "DEMO only one candidate supported"}})
    body = DecisionCreate(request_id=pending["id"], artifact_version=1, artifact_hash=HASH, expected_run_version=2, decision="approve")
    key = str(uuid4())
    def decide():
        with owner_transaction(engine, owner) as repo:
            return repo.decide(run_id, "shortlist", body, key)
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(lambda _: decide(), range(4)))
    assert len({record["id"] for record in records}) == 1
    with owner_transaction(engine, owner) as repo:
        assert len(repo.list(m.approval_decisions, run_id)) == 1
        assert repo.get(m.runs, run_id)["version"] == 3
        assert len(repo.list(m.events, run_id)) == 2  # queued plus one decision


def test_z_migration_rollback_and_reapply_preserves_auth(local):
    root = Path(__file__).resolve().parents[2]
    previous = os.environ.get("LATHER_DATABASE_URL")
    os.environ["LATHER_DATABASE_URL"] = local["admin_url"]
    cfg = Config(str(root / "backend/alembic.ini"))
    try:
        with psycopg.connect(local["admin_url"].replace("postgresql+psycopg://", "postgresql://")) as admin:
            assert admin.execute("SELECT instance FROM lather_test_control.identity WHERE id=1").fetchone()[0] == local["test_instance"]
            # Explicit disposable-fixture cleanup before the whole-schema destruction test.
            # Production downgrade refuses unknown SKUs/robots evidence instead of silently deleting or inventing values.
            # The retained dedicated stack can contain earlier DEMO test cohorts.
            # Scope destructive rollback cleanup to the exact signup pattern from prepare_local_auth.py.
            owners = [row[0] for row in admin.execute("SELECT id FROM auth.users WHERE email ~ '^demo-[ab]-[0-9a-f]{32}@example[.]invalid$'").fetchall()]
            admin.execute("DELETE FROM price_observations WHERE owner_id=ANY(%s) AND normalization_data IS NULL AND total_weight_g IS NOT NULL AND product_id IN (SELECT id FROM products WHERE attributes->>'label'='DEMO')", (owners,))
            admin.execute("DELETE FROM price_observations WHERE product_id IN (SELECT id FROM products WHERE sku IS NULL AND attributes->>'label'='DEMO' AND owner_id=ANY(%s))", (owners,))
            admin.execute("DELETE FROM products WHERE sku IS NULL AND attributes->>'label'='DEMO' AND owner_id=ANY(%s)", (owners,))
            admin.execute("DELETE FROM source_documents WHERE source_id IN (SELECT id FROM sources WHERE evidence_kind='robots_policy' AND canonical_url LIKE 'https://%%.invalid/%%' AND owner_id=ANY(%s))", (owners,))
            admin.execute("DELETE FROM sources WHERE evidence_kind='robots_policy' AND canonical_url LIKE 'https://%%.invalid/%%' AND owner_id=ANY(%s)", (owners,))
        command.downgrade(cfg, "base")
        with psycopg.connect(local["admin_url"].replace("postgresql+psycopg://", "postgresql://")) as admin:
            assert admin.execute("SELECT to_regclass('public.briefs')").fetchone()[0] is None
            assert admin.execute("SELECT count(*) FROM auth.users WHERE id = ANY(%s)", ([UUID(user["id"]) for user in local["users"]],)).fetchone()[0] == 2
        command.upgrade(cfg, "head")
        with psycopg.connect(local["admin_url"].replace("postgresql+psycopg://", "postgresql://")) as admin:
            admin.execute("GRANT lather_api TO lather_runtime")
            assert admin.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tablename = ANY(%s)", (list(m.TABLES),)).fetchone()[0] == len(m.TABLES)
    finally:
        if previous is None:
            os.environ.pop("LATHER_DATABASE_URL", None)
        else:
            os.environ["LATHER_DATABASE_URL"] = previous
