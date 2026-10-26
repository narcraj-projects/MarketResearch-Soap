"""LP01+: mocked live-boundary negatives. No provider/network calls in CI."""
from datetime import datetime, timedelta, timezone
import json
from uuid import UUID, uuid4, uuid5

import httpx
import pytest
from pydantic import ValidationError

from app.harness.live_policy import LivePermit, enforce_credit_cap, CREDIT_USD, MODEL_RESERVATION
from app.harness.policy import PolicyDenied
from app.harness.contracts import RunContext
from app.adapters.live_web import LivePublicWeb, model_json
from app.harness.web_policy import Destination
from app.harness.live_models import JsonChatAdapter
from app.live_workflow import LiveTavilyAdapter, LiveScout
from app.harness.search import SearchSource
from app.api_schemas import BriefCreate
from hashlib import sha256


def permit(**changes):
    return LivePermit.model_validate(dict(run_id=UUID(int=1), owner_id=UUID(int=2), max_tavily_credits=10, max_model_usd="5",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10)) | changes)


def test_lp01_permit_scope_expiry_and_profile():
    grant = permit()
    grant.check(UUID(int=1), UUID(int=2))
    for run, owner in [(uuid4(), UUID(int=2)), (UUID(int=1), uuid4())]:
        with pytest.raises(PolicyDenied):
            grant.check(run, owner)
    with pytest.raises(PolicyDenied):
        grant.model_copy(update={"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)}).check(grant.run_id, grant.owner_id)
    with pytest.raises(PolicyDenied):
        grant.model_copy(update={"endpoint": "http://169.254.169.254/"}).check(grant.run_id, grant.owner_id)
    with pytest.raises(ValidationError):
        permit(max_tavily_credits=21)


def test_lp02_separate_credit_and_model_caps():
    grant = permit()
    credits = [{"cost_upper_bound_usd": CREDIT_USD} for _ in range(10)]
    with pytest.raises(PolicyDenied, match="tavily_credit_cap"):
        enforce_credit_cap(credits, grant, CREDIT_USD)
    enforce_credit_cap(credits, grant, MODEL_RESERVATION)
    model = [{"cost_upper_bound_usd": MODEL_RESERVATION} for _ in range(10)]
    with pytest.raises(PolicyDenied, match="model_spend_cap"):
        enforce_credit_cap(model, grant, MODEL_RESERVATION)
    enforce_credit_cap(model, grant, CREDIT_USD)


def test_lp03_replay_adapter_refuses_live_even_with_key(monkeypatch):
    monkeypatch.setenv("LATHER_TAVILY_API_KEY", "DEMO-key")
    adapter = LiveTavilyAdapter(permit(), transport=httpx.MockTransport(lambda _: pytest.fail("unexpected_dispatch")))
    with pytest.raises(PolicyDenied, match="live_adapter_requires_live_gateway"):
        adapter.ensure_offline()


def test_lp04_basic_news_fixed_endpoint_and_no_error_body(monkeypatch):
    monkeypatch.setenv("LATHER_TAVILY_API_KEY", "DEMO-key")
    seen = []
    def handle(request):
        seen.append(json.loads(request.content))
        return httpx.Response(429, json={"detail": "DEMO-PRIVATE-CANARY"})
    web = LivePublicWeb(permit(), transport=httpx.MockTransport(handle))
    target = Destination("https://api.tavily.com/search", "api.tavily.com", 443, "8.8.8.8")
    reply = web.exchange(target, method="POST", query={"query": "DEMO soap", "topic": "news", "search_depth": "basic", "auto_parameters": False}, timeout=1)
    assert reply.status == 429 and reply.body is None and len(seen) == 1
    with pytest.raises(PolicyDenied):
        web.exchange(Destination("https://evil.invalid/", "evil.invalid", 443, "8.8.8.8"), method="POST", query={}, timeout=1)
    with pytest.raises(PolicyDenied):
        web.exchange(Destination("http://example.com/", "example.com", 80, "8.8.8.8"), method="GET", query=None, timeout=1)


def test_lp05_model_adapter_bounded_json_and_credential_redaction(monkeypatch):
    monkeypatch.setenv("LATHER_LLM_API_KEY", "DEMO-model-key")
    def handle(request):
        body = json.loads(request.content)
        assert body["stream"] is False and body["max_tokens"] == 8192
        assert body["service_tier"] == "default"
        assert body["model"] == permit().model
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok":true}'}}], "usage": {"prompt_tokens": 10, "completion_tokens": 4}})
    adapter = JsonChatAdapter(permit(), transport=httpx.MockTransport(handle))
    assert model_json(adapter.generate([{"role": "user", "content": "DEMO"}], {"type": "object"})) == {"ok": True}
    with pytest.raises(PolicyDenied, match="model_input_limit"):
        adapter.generate([{"role": "user", "content": "x" * 100001}], {})
    for raw in ({}, {"choices": [{"message": {"content": "not JSON"}}]}):
        with pytest.raises(PolicyDenied, match="model_json_invalid"):
            model_json(raw)


def test_lp06_invented_competitor_and_quote_fail_closed():
    text = "DEMO Maker makes handmade soap in India."
    source = SearchSource(source_id=uuid4(), canonical_url="https://maker.invalid/", domain="maker.invalid", title="DEMO Maker", publisher="maker.invalid",
        excerpt=text, content_hash=sha256(text.encode()).hexdigest(), retrieved_at=datetime.now(timezone.utc))
    class Model:
        def invoke(self, *args):
            return {"candidates": [{"name": "DEMO Invented", "source_ids": [str(source.source_id)], "product_quote": "handmade soap", "geography_quote": "India", "rationale": "DEMO"}], "insufficiency_reason": "DEMO one"}
    ranker = LiveScout(Model())
    brief = BriefCreate(category="soap", geography="India", customer="soap buyers", objective="DEMO")
    with pytest.raises(PolicyDenied, match="unsubstantiated_live_identity"):
        ranker(brief, UUID(int=1), (source,))


def test_lp07_bare_live_mode_still_rejected():
    from tests.scout_support import context
    ctx = context()
    with pytest.raises(ValidationError):
        RunContext.model_validate(ctx.model_dump() | {"mode": "live"})
    approved = RunContext.model_validate(ctx.model_dump() | {"mode": "live", "live_authorization_id": uuid5(ctx.run_id, "live-permit-1.0")})
    assert approved.mode == "live"
