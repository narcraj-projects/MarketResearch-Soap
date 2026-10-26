"""Real local evidence/RLS tests. All public HTTP/DNS/news is recorded DEMO data."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
import os
import subprocess
import sys
from pathlib import Path
from threading import Barrier
from uuid import uuid4

from alembic import command
from alembic.config import Config
import httpx
import pytest
from sqlalchemy import select

from app import models as m
from app.adapters.public_web import RecordedWeb
from app.agents.extraction import canonical
from app.agents.researcher import research_parallel
from app.api_schemas import DecisionCreate
from app.config import Settings
from app.harness.policy import PolicyDenied
from app.harness.research_store import ResearchStore
from app.harness.research_types import RetrievedSource
from app.harness.retrieval import ResearchGateway
from app.main import create_app
from app.repository import owner_transaction
from app.services.discovery import discover
from tests.research_support import FOLDER, versions
from tests.test_scout_storage_integration import begin as scout_begin
from tests.test_storage_integration import engine as engine, local as local

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not os.environ.get("LATHER_INTEGRATION_CONFIG"), reason="explicit dedicated local Supabase required")]


def prepared(engine, local, case="R21-parallel"):
    owner, _, scout, ctx, brief, gateway = scout_begin(engine, local, budget={"max_calls": 100, "max_tokens": 0, "max_cost_usd": "0"})
    pending = discover(ctx, brief, gateway, scout)
    with owner_transaction(engine, owner) as repo:
        repo.decide(ctx.run_id, "shortlist", DecisionCreate(request_id=pending["request_id"], artifact_version=1, artifact_hash=pending["artifact_hash"],
            expected_run_version=pending["run_version"], decision="approve"), str(uuid4()))
    store = ResearchStore(engine)
    context, competitors = store.begin(ctx.run_id, owner, datetime.now(timezone.utc) + timedelta(minutes=5), versions())
    recording = RecordedWeb(FOLDER / (case + ".json"))
    research_gateway = ResearchGateway(recording, store, sleep=lambda _: None)
    return owner, store, context, competitors, recording, research_gateway


def test_parallel_research_attribution_unknowns_and_owner_api(engine, local, integration_loop):
    owner, store, context, competitors, recording, gateway = prepared(engine, local)
    # Every lane must reach its independent initial page request before any can proceed.
    barrier = Barrier(3)
    def meet(request):
        if request.startswith("GET https://demo-") and request.endswith("/soap"):
            barrier.wait(timeout=15)
    recording.before_request = meet
    results = research_parallel(context, competitors, gateway, store)
    assert len(results) == 3 and all(len(result.pages[0].products) == 1 for result in results)
    with owner_transaction(engine, owner) as repo:
        products = repo.list(m.products, context.run_id)
        prices = repo.list(m.prices, context.run_id)
        assert len(products) == len(prices) == 3
        unknown = next(product for product in products if product["sku"] is None)
        ambiguous = next(price for price in prices if price["product_id"] == unknown["id"])
        assert ambiguous["pack_qty"] == 3 and ambiguous["total_weight_g"] is None and ambiguous["unit_price_100g"] is None
        known_prices = [price for price in prices if price["product_id"] != unknown["id"]]
        assert all(price["unit_price_100g"] == Decimal("120") for price in known_prices)
        tasks = repo.list(m.research_tasks, context.run_id)
        assert len(tasks) == 3 and {row["competitor_id"] for row in tasks} == {c["id"] for c in competitors}
        claims = repo.list(m.claims, context.run_id, limit=1000)
        links = repo.list(m.claim_sources, context.run_id, limit=1000)
        assert claims and len(links) >= len(claims)
        for link in links:
            source = repo.get(m.sources, link["source_id"])
            document = repo.conn.execute(select(m.source_documents).where(m.source_documents.c.source_id == source["id"])).mappings().one()
            assert link["quote"] in document["excerpt"] and link["excerpt_hash"] == sha256(link["quote"].encode()).hexdigest()
            assert source["retrieved_at"] and source["content_hash"] == sha256(document["body"].encode()).hexdigest()
            if link["locator"].startswith("json:"):
                value = document["structured"]
                for piece in link["locator"][5:].split("/")[1:]:
                    piece = piece.replace("~1", "/").replace("~0", "~")
                    value = value[int(piece)] if isinstance(value, list) else value[piece]
                assert canonical(value) == link["quote"]
        marketing = [claim for claim in claims if claim["kind"] == "competitor_marketing_claim"]
        assert marketing and all(claim["review_status"] == "flagged" for claim in marketing)
        event_count = len(repo.list(m.events, context.run_id, limit=1000))
    # Re-open store/gateway and repeat: existing lane artifacts and wire results are durable.
    fresh_store = ResearchStore(engine)
    fresh_context, fresh_competitors = fresh_store.begin(context.run_id, owner, datetime.now(timezone.utc) + timedelta(hours=1), versions())
    fresh_recording = RecordedWeb(FOLDER / "R21-parallel.json")
    again = research_parallel(fresh_context, fresh_competitors, ResearchGateway(fresh_recording, fresh_store), fresh_store)
    assert again == results and fresh_recording.requests == []
    child = subprocess.run([sys.executable, "tools/research_demo.py", "--run-id", str(context.run_id)], cwd=Path(__file__).resolve().parents[1],
        capture_output=True, text=True, timeout=30)
    if child.returncode != 0:
        pytest.fail("research_child_failed; diagnostic details suppressed")
    child_result = json.loads(child.stdout.strip().splitlines()[-1])
    assert child_result["state"] == "research_complete" and child_result["recorded_http_dispatches"] == 0 and child_result["products"] == 3
    with owner_transaction(engine, owner) as repo:
        assert len(repo.list(m.events, context.run_id, limit=1000)) == event_count
    async def check_api():
        app = create_app(Settings(_env_file=None, environment="test", database_url=local["runtime_url"], supabase_url=local["supabase_url"], supabase_publishable_key=local["publishable_key"]))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                own = {"Authorization": "Bearer " + local["users"][0]["token"]}
                other = {"Authorization": "Bearer " + local["users"][1]["token"]}
                for path in (f"/api/runs/{context.run_id}/research", f"/api/runs/{context.run_id}/claims/{claims[0]['id']}/evidence"):
                    response = await client.get(path, headers=own)
                    assert response.status_code == 200 and response.json()
                    assert (await client.get(path, headers=other)).status_code == 404
    integration_loop.run_until_complete(check_api())


def test_inaccessible_lane_does_not_erase_other_competitors(engine, local):
    owner, store, context, competitors, recording, gateway = prepared(engine, local, "R23-parallel-blocked")
    results = research_parallel(context, competitors, gateway, store)
    blocked = next(c["id"] for c in competitors if c["name"] == "DEMO Maker B")
    failed = next(result for result in results if result.competitor_id == blocked)
    assert failed.state == "partial" and all(not page.products for page in failed.pages)
    assert all(o.value is None for page in failed.pages for o in page.observations)
    assert sum(bool(page.products) for result in results for page in result.pages) == 2
    with owner_transaction(engine, owner) as repo:
        assert len(repo.list(m.products, context.run_id)) == 2
        assert len(repo.list(m.research_tasks, context.run_id)) == 3
        serialized = json.dumps([row["outcome"] for row in repo.list(m.tool_attempts, context.run_id)], default=str)
        assert "DEMO blocked response body" not in serialized
        assert repo.get(m.runs, context.run_id)["status"] == "researching"  # No Analyst/report stage started.


def test_unapproved_research_and_cross_lane_source_are_rejected(engine, local):
    owner, _, scout, context, brief, search_gateway = scout_begin(engine, local, budget={"max_calls": 100, "max_tokens": 0, "max_cost_usd": "0"})
    discover(context, brief, search_gateway, scout)
    with pytest.raises(PolicyDenied, match="shortlist_approval_required"):
        ResearchStore(engine).begin(context.run_id, owner, datetime.now(timezone.utc) + timedelta(minutes=1), versions())
    owner, store, context, competitors, recording, gateway = prepared(engine, local)
    first, second = competitors[:2]
    sources = gateway.retrieve(context, first["id"], first["canonical_url"])
    with pytest.raises(PolicyDenied, match="cross_competitor_source"):
        store.save_task(context, second["id"], sources, ())
    original = sources[-1]
    altered_body = (original.body or "") + " DEMO forged content"
    forged = RetrievedSource.model_validate(original.model_dump() | {"body": altered_body, "content_hash": sha256(altered_body.encode()).hexdigest()})
    with pytest.raises(PolicyDenied, match="source_payload_conflict"):
        store.save_task(context, first["id"], (forged,), ())
    with owner_transaction(engine, owner) as repo:
        assert repo.list(m.claims, context.run_id) == []


def test_null_sku_evidence_blocks_lossy_migration_downgrade(engine, local):
    owner, store, context, competitors, recording, gateway = prepared(engine, local)
    research_parallel(context, competitors, gateway, store)
    prior = os.environ.get("LATHER_DATABASE_URL")
    try:
        os.environ["LATHER_DATABASE_URL"] = local["admin_url"]
        cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        with pytest.raises(RuntimeError, match="unknown_sku_prevents_lossless_downgrade|unverified_weight_prevents_safe_downgrade"):
            command.downgrade(cfg, "0003")
    finally:
        if prior is None:
            os.environ.pop("LATHER_DATABASE_URL", None)
        else:
            os.environ["LATHER_DATABASE_URL"] = prior
    with owner_transaction(engine, owner) as repo:
        assert any(product["sku"] is None for product in repo.list(m.products, context.run_id))
        assert len(repo.list(m.research_tasks, context.run_id)) == 3


def test_contradictory_prices_and_news_keep_source_relationships(engine, local):
    owner, store, context, competitors, _, _ = prepared(engine, local)
    competitor = next(c for c in competitors if c["name"] == "DEMO Maker A")
    recording = RecordedWeb(FOLDER / "R05-contradiction.json")
    gateway = ResearchGateway(recording, store)
    docs = gateway.retrieve(context, competitor["id"], competitor["canonical_url"])
    result = store.save_task(context, competitor["id"], docs, ())
    assert len(result.conflicts) == 1
    with owner_transaction(engine, owner) as repo:
        prices = repo.list(m.prices, context.run_id)
        assert sorted(p["amount"] for p in prices) == [Decimal("120"), Decimal("140")]
        assert all(p["source_id"] == result.pages[0].source_id for p in prices)
    # A separate run proves news discovery plus permitted article retrieval and launch attribution.
    owner, store, context, competitors, _, _ = prepared(engine, local)
    competitor = next(c for c in competitors if c["name"] == "DEMO Maker A")
    news_recording = RecordedWeb(FOLDER / "R19-news.json")
    gateway = ResearchGateway(news_recording, store)
    sources = list(gateway.retrieve(context, competitor["id"], competitor["canonical_url"]))
    hits = gateway.news(context, competitor["id"], competitor["name"])
    sources.extend(hits)
    for hit in hits:
        sources.extend(gateway.retrieve(context, competitor["id"], hit.canonical_url))
    result = store.save_task(context, competitor["id"], tuple(sources), ())
    launches = [o for page in result.pages for o in page.observations if o.field == "reported_launch" and o.value is not None]
    assert len(launches) == 1 and launches[0].kind == "competitor_marketing_claim"
    with owner_transaction(engine, owner) as repo:
        claim = next(c for c in repo.list(m.claims, context.run_id, limit=1000) if c["text"].startswith("reported_launch:"))
        links = repo.conn.execute(select(m.claim_sources).where(m.claim_sources.c.claim_id == claim["id"])).mappings().all()
        assert len(links) == 1
        source = repo.get(m.sources, links[0]["source_id"])
        assert source["canonical_url"] == "https://news.invalid/a-launch" and source["evidence_kind"] == "page_excerpt"
