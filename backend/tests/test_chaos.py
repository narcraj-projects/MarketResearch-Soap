"""CP: deterministic replay and production-denial tests. All responses are DEMO."""
from hashlib import sha256
from types import SimpleNamespace
from uuid import UUID, uuid5

import httpx
import pytest
from pydantic import ValidationError

from app.adapters.tavily import TavilyAdapter
from app.auth import Identity, current_user
from app.config import Settings
from app.harness.chaos import ChaosCreate, FOLDER, plan, read_fixture, require_isolated_engine, require_test_mode, scenario_files
from app.harness.contracts import SearchCall, Role
from app.harness.gateway import SearchGateway
from app.harness.model_replay import ModelReplayGateway
from app.harness.policy import PolicyDenied
from app.harness.recordings import RecordedTavily
from app.harness.replay import ReplayRequest, ReplayStep, ReplayTape
from app.harness.search import ReplayMismatch, SearchCost
from app.main import create_app
from tests.scout_support import Clock, MemoryLedger, context, versions
from tests.test_health import asgi_loop as asgi_loop


@pytest.mark.parametrize("kind", ["search", "model", "tool"])
def test_cp01_exact_replay_all_response_kinds_and_hashes(kind):
    request = ReplayRequest(kind=kind, operation="DEMO-lane", attempt=1, versions=versions(), arguments={"input_hash": "a" * 64})
    raw = '{"label":"DEMO","result":null}'
    step = ReplayStep(request=request, raw_response=raw, response_hash=sha256(raw.encode()).hexdigest())
    tape = ReplayTape((step,))
    assert tape.consume(request) == tape.consume(request) == raw
    tape.assert_finished()
    with pytest.raises(ReplayMismatch):
        tape.consume(request.model_copy(update={"arguments": {"input_hash": "b" * 64}}))
    with pytest.raises(ReplayMismatch):
        tape.consume(request.model_copy(update={"versions": versions().model_copy(update={"model": "DEMO-different"})}))
    with pytest.raises(ValidationError):
        ReplayStep(request=request, raw_response=raw, response_hash="0" * 64)
    with pytest.raises(ValidationError):
        ReplayTape((step.model_copy(update={"raw_response": "DEMO-tampered"}),))
    request.arguments["input_hash"] = "c" * 64
    with pytest.raises(ReplayMismatch):
        tape.consume(request)  # caller mutation cannot rewrite the snapshotted expected request


def test_cp02_attempt_order_missing_extra_and_independent_lanes():
    def step(lane, attempt):
        request = ReplayRequest(kind="model", operation=lane, attempt=attempt, versions=versions(), arguments={})
        return ReplayStep(request=request, raw_response="DEMO", response_hash=sha256(b"DEMO").hexdigest())
    a, b, c = step("A", 1), step("A", 2), step("B", 1)
    tape = ReplayTape((a, b, c))
    with pytest.raises(ReplayMismatch, match="order"):
        tape.consume(b.request)
    tape.consume(c.request)
    tape.consume(a.request)
    with pytest.raises(ReplayMismatch, match="missing"):
        tape.assert_finished()
    tape.consume(b.request)
    tape.assert_finished()
    with pytest.raises(ReplayMismatch):
        ReplayTape((a, a))


@pytest.mark.parametrize("environment", ["local", "production"])
def test_cp03_production_and_default_local_cannot_enable_faults(environment):
    with pytest.raises(ValidationError, match="chaos_requires_test_environment"):
        Settings(_env_file=None, environment=environment, chaos_enabled=True)
    with pytest.raises(PolicyDenied):
        require_test_mode(Settings(_env_file=None, environment=environment))
    with pytest.raises(PolicyDenied):
        require_isolated_engine(SimpleNamespace(url=SimpleNamespace(host="example.invalid", port=5432)))


def test_cp04_fixed_allowlist_and_pinned_fixture_versions():
    settings = Settings(_env_file=None, environment="test", chaos_enabled=True)
    registry = read_fixture("scenarios.json")
    assert len(registry["scenarios"]) == 9
    for row in registry["scenarios"]:
        configured = plan(row["scenario"])
        assert scenario_files(configured, settings) == row
        with pytest.raises(PolicyDenied):
            scenario_files(configured.model_copy(update={"manifest_hash": "0" * 64}), settings)
    with pytest.raises(ValidationError):
        ChaosCreate(scenario="timeout", authorized=True, target_url="https://example.invalid")
    with pytest.raises(ValidationError):
        ChaosCreate(scenario="publish")
    with pytest.raises(ReplayMismatch):
        read_fixture("../scout-v1/SC01-clean.json")


@pytest.mark.parametrize("scenario", ["timeout", "rate_limit"])
def test_cp05_cached_failed_attempt_resume_uses_correct_recorded_response(scenario):
    recording = RecordedTavily(FOLDER / f"search-{scenario}.json")
    ledger, clock = MemoryLedger(), Clock()
    class Lost(BaseException):
        pass
    def lost(_):
        raise Lost()
    call = SearchCall(operation_id=UUID(int=9), agent=Role.SCOUT, tool="public.search", query=recording.case["steps"][0]["request"]["query"], limit=recording.case["steps"][0]["request"]["max_results"])
    gateway = SearchGateway(TavilyAdapter(recording.transport), ledger, SearchCost(per_attempt_upper_bound_usd=0, pricing_version="DEMO"), clock=clock.now, sleep=lost)
    with pytest.raises(Lost):
        gateway.execute(context(), call)
    assert recording.ordinal == 1 and len(ledger.rows) == 1
    fresh = RecordedTavily(FOLDER / f"search-{scenario}.json")
    resumed = SearchGateway(TavilyAdapter(fresh.transport), ledger, SearchCost(per_attempt_upper_bound_usd=0, pricing_version="DEMO"), clock=clock.now, sleep=clock.sleep)
    result = resumed.execute(context(), call)
    assert result.result.status == "ok" and result.result.attempt == 2
    assert fresh.ordinal == 1 and len(ledger.rows) == 2  # failed attempt was not dispatched or charged again


def test_cp06_production_api_denies_injection_without_db_or_external_auth(asgi_loop):
    async def exercise():
        app = create_app(Settings(_env_file=None, environment="production"))
        app.dependency_overrides[current_user] = lambda: Identity(UUID(int=1))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            capabilities = await client.get("/api/chaos/capabilities")
            assert capabilities.json() == {"enabled": False, "label": "DEMO", "scenarios": []}
            for body in ({"scenario": "timeout"}, {"scenario": "interrupted_worker", "environment": "test", "enabled": True}):
                response = await client.post("/api/chaos/runs?environment=test", json=body, headers={"Idempotency-Key": "DEMO-production-test", "X-Chaos-Enabled": "true"})
                assert response.status_code == 403 and response.json()["detail"] == "chaos_disabled"
    asgi_loop.run_until_complete(exercise())


def test_cp07_model_gateway_itself_rejects_production_before_context_or_db_access():
    with pytest.raises(PolicyDenied, match="chaos_disabled"):
        ModelReplayGateway(None, None, None, "malformed_json", Settings(_env_file=None, environment="production"))


def test_cp08_public_tool_resume_after_rate_limit_consumes_cached_slot_then_timeout_then_success():
    from app.adapters.public_web import RecordedWeb
    from app.harness.retrieval import ResearchGateway
    from tests.research_support import FOLDER, setup
    recording, journal, clock, gateway, ctx = setup("R14-retry")
    class Lost(BaseException):
        pass
    def lose(_):
        raise Lost()
    gateway.sleep = lose
    with pytest.raises(Lost):
        gateway.retrieve(ctx, UUID(int=10), recording.case["competitor"]["url"])
    assert len(journal.rows) == len(recording.requests) == 2  # robots + first 429
    fresh = RecordedWeb(FOLDER / "R14-retry.json")
    result = ResearchGateway(fresh, journal, clock=clock.now, sleep=clock.sleep).retrieve(ctx, UUID(int=10), recording.case["competitor"]["url"])
    assert result[-1].access_status == "ok" and len(fresh.requests) == 2  # attempts 2 (timeout) and 3 (200)
    assert len(journal.rows) == 4 and fresh.dns_cursors["demo-a.invalid"] == 4


def test_cp09_cached_robots_does_not_reset_rebinding_dns_observation_on_restart():
    from app.adapters.public_web import RecordedWeb
    from app.harness.research_types import ResearchCall
    from app.harness.retrieval import ResearchGateway
    from tests.research_support import FOLDER, setup
    recording, journal, clock, gateway, ctx = setup("R22-dns-rebinding")
    cid, url = UUID(int=10), "https://demo-a.invalid/robots.txt"
    gateway._wire(ctx, ResearchCall(operation_id=uuid5(cid, "robots:" + url), competitor_id=cid, tool="public.retrieve", kind="robots", url=url))
    fresh = RecordedWeb(FOLDER / "R22-dns-rebinding.json")
    result = ResearchGateway(fresh, journal, clock=clock.now, sleep=clock.sleep).retrieve(ctx, cid, recording.case["competitor"]["url"])
    assert fresh.requests == [] and fresh.dns_cursors["demo-a.invalid"] == 2
    assert result[-1].access_status != "ok" and result[-1].body is None
