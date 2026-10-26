from datetime import timedelta
from email.utils import format_datetime
from decimal import Decimal
import json
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import ValidationError
import pytest
import httpx

from app.adapters.tavily import TavilyAdapter
from app.agents.scout import Discovery, rank
from app.api_schemas import BriefCreate
from app.harness.contracts import Budget, Role, SearchCall
from app.harness.gateway import SearchGateway
from app.harness.policy import PolicyDenied
from app.harness.recordings import RecordedTavily
from app.harness.search import ReplayMismatch, SearchCost
from app.harness.urls import normalize_url
from app.services.discovery import search
from tests.scout_support import Clock, MemoryLedger, NOW, context

FOLDER = Path(__file__).resolve().parents[1] / "evaluations/fixtures/scout-v1"


def setup(name="SC01-clean", **changes):
    recording = RecordedTavily(FOLDER / (name + ".json"))
    clock, ledger = Clock(), MemoryLedger()
    cost = SearchCost(per_attempt_upper_bound_usd=Decimal("0.1"), pricing_version="DEMO-accounting-only")
    gateway = SearchGateway(TavilyAdapter(recording.transport), ledger, cost, clock.now, clock.sleep, lambda: 0)
    return recording, clock, ledger, gateway, context(**changes), BriefCreate.model_validate(recording.case["brief"])


@pytest.mark.parametrize("case_path", sorted(FOLDER.glob("SC*.json")), ids=lambda p: p.stem)
def test_recorded_scout_cases(case_path):
    recording, clock, ledger, gateway, ctx, brief = setup(case_path.stem)
    sources, stop = search(ctx, brief, gateway)
    output = rank(brief, ctx.run_id, sources)
    expected = recording.case["expected"]
    assert len(output.candidates) == expected["candidates"]
    assert stop == expected["stop_reason"]
    assert recording.ordinal == expected["dispatches"] == len(ledger.rows)
    recording.assert_finished()
    assert len({c.domain for c in output.candidates}) == len(output.candidates)
    assert all(c.name in next(s.excerpt for s in sources if s.source_id in c.source_ids) for c in output.candidates)
    assert all(c.name != "DEMO Ghost" for c in output.candidates)
    if len(output.candidates) < 3:
        assert output.insufficiency_reason
    if case_path.stem == "SC06-rate-limit":
        assert clock.delays == [2]
    if case_path.stem == "SC07-timeout":
        assert clock.delays == [0.5, 1]
    if case_path.stem == "SC11-unknown-fit":
        assert output.candidates[0].score == 2
        assert output.candidates[0].known_dimensions == 2
        assert sum(f.status == "unknown" for f in output.candidates[0].fits) == 3
    if case_path.stem == "SC10-unsafe-urls":
        assert len(sources) == 2


def test_no_egress_even_with_key_present(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "DEMO-not-a-real-key")
    with pytest.raises(PolicyDenied, match="live_not_approved"):
        SearchGateway(TavilyAdapter(), MemoryLedger(), SearchCost(per_attempt_upper_bound_usd=0, pricing_version="DEMO")).execute(
            context(), SearchCall(operation_id=uuid4(), agent=Role.SCOUT, tool="public.search", query="DEMO"))


@pytest.mark.parametrize("changes", [{"agent": "analyst"}, {"agent": "researcher"}, {"attempt": 2}])
def test_gateway_denies_wrong_agent_or_caller_retry(changes):
    recording, _, ledger, gateway, ctx, _ = setup()
    call = SearchCall.model_validate(dict(operation_id=uuid4(), agent="scout", tool="public.search", query="DEMO") | changes)
    with pytest.raises(PolicyDenied):
        gateway.execute(ctx, call)
    assert recording.ordinal == len(ledger.rows) == 0


def test_tavily_cannot_be_called_outside_gateway():
    recording, _, _, _, ctx, _ = setup()
    with pytest.raises(PolicyDenied, match="gateway_required"):
        TavilyAdapter(recording.transport)._dispatch(ctx, SearchCall(operation_id=uuid4(), agent=Role.SCOUT, tool="public.search", query="DEMO"), 1, NOW, permit=object())
    assert recording.ordinal == 0


@pytest.mark.parametrize("limits", [{"max_calls": 1, "max_cost": "1"}, {"max_calls": 6, "max_cost": "0.1"}])
def test_retry_cannot_overrun_call_or_cost_budget(limits):
    recording, _, ledger, gateway, ctx, brief = setup("SC06-rate-limit", budget=Budget(max_tokens=0, **limits))
    sources, stop = search(ctx, brief, gateway)
    assert sources == () and stop == "budget"
    assert recording.ordinal == len(ledger.rows) == 1


def test_unknown_cost_and_deadline_prevent_dispatch():
    recording, clock, ledger, gateway, ctx, brief = setup(deadline=NOW)
    assert search(ctx, brief, gateway) == ((), "deadline")
    gateway.cost = SearchCost(pricing_version="DEMO-unknown")
    assert search(context(), brief, gateway) == ((), "unknown_cost")
    assert recording.ordinal == len(ledger.rows) == 0


def test_cache_reuses_completed_attempt_without_dispatch_and_rejects_changed_args():
    recording, _, ledger, gateway, ctx, brief = setup()
    first, _ = search(ctx, brief, gateway)
    second, _ = search(ctx, brief, gateway)
    assert first == second and recording.ordinal == len(ledger.rows) == 1
    changed = BriefCreate.model_validate(brief.model_dump() | {"geography": "DEMO different geography"})
    with pytest.raises(PolicyDenied, match="operation_payload_conflict"):
        search(ctx, changed, gateway)


def test_unfinished_attempt_is_not_silently_retried():
    recording, _, ledger, gateway, ctx, brief = setup()
    search(ctx, brief, gateway)
    next(iter(ledger.rows.values()))["outcome"] = None
    with pytest.raises(PolicyDenied, match="uncertain_attempt"):
        search(ctx, brief, gateway)
    assert recording.ordinal == 1


def test_exact_replay_rejects_wrong_query_and_missing_records():
    recording, _, _, gateway, ctx, _ = setup()
    with pytest.raises(ReplayMismatch, match="request_mismatch"):
        gateway.execute(ctx, SearchCall(operation_id=uuid4(), agent=Role.SCOUT, tool="public.search", query="DEMO wrong query"))
    with pytest.raises(ReplayMismatch, match="missing_operation"):
        recording.assert_finished()


def test_invented_competitor_cannot_enter_selected_handoff():
    _, _, _, gateway, ctx, brief = setup()
    sources, _ = search(ctx, brief, gateway)
    result = rank(brief, ctx.run_id, sources)
    data = result.model_dump(mode="json")
    data["candidates"][0]["candidate_id"] = str(UUID(int=999))
    data["candidates"][0]["name"] = "DEMO Ghost"
    with pytest.raises(ValidationError, match="invented_candidate"):
        Discovery.model_validate(data)


@pytest.mark.parametrize("raw", ["file:///etc/passwd", "http://127.0.0.1/", "http://169.254.169.254/", "http://[::1]/", "https://user:password@example.com/", "http://localhost/", "https://2130706433/", "https://example.com:444/", "https://example.com/%0d%0afoo", "https://example.com\\@localhost/", "https://example.invalid/"])
def test_unsafe_source_urls_rejected(raw):
    with pytest.raises(ValueError, match="unsafe_source_url"):
        normalize_url(raw)


def test_url_canonicalization_and_offline_public_suffixes():
    assert normalize_url("https://WWW.Example.CO.IN:443/Soap?utm_source=x&sku=1#part") == ("https://www.example.co.in/Soap?sku=1", "example.co.in")
    assert normalize_url("https://a.blogspot.com/")[1] != normalize_url("https://b.blogspot.com/")[1]
    assert normalize_url("https://shop.demo-a.invalid/", demo=True)[1] == "demo-a.invalid"


def test_search_arguments_are_bounded_and_forbid_extra_fields():
    for changes in ({"limit": 100}, {"timeout_seconds": 0}, {"query": ""}, {"include_answer": True}):
        with pytest.raises(ValidationError):
            SearchCall.model_validate(dict(operation_id=uuid4(), agent="scout", tool="public.search", query="DEMO") | changes)


def test_recording_digest_detects_mutations(tmp_path):
    case = FOLDER / "SC01-clean.json"
    (tmp_path / "manifest.json").write_bytes((FOLDER / "manifest.json").read_bytes())
    altered = json.loads(case.read_text())
    altered["steps"] = []
    (tmp_path / case.name).write_text(json.dumps(altered))
    with pytest.raises(ReplayMismatch, match="recording_hash_mismatch"):
        RecordedTavily(tmp_path / case.name)


def test_http_date_retry_after_and_timeout_bounded_by_remaining_deadline():
    clock, ledger, timeouts = Clock(), MemoryLedger(), []
    def handler(request):
        timeouts.append(request.extensions["timeout"])
        if len(timeouts) == 1:
            return httpx.Response(429, headers={"Retry-After": format_datetime(NOW + timedelta(seconds=2), usegmt=True)})
        return httpx.Response(200, json={"query": "DEMO", "results": []})
    gateway = SearchGateway(TavilyAdapter(httpx.MockTransport(handler)), ledger,
        SearchCost(per_attempt_upper_bound_usd=0, pricing_version="DEMO"), clock.now, clock.sleep, lambda: 0)
    ctx = context(deadline=NOW + timedelta(seconds=4))
    output = gateway.execute(ctx, SearchCall(operation_id=uuid4(), agent=Role.SCOUT, tool="public.search", query="DEMO", timeout_seconds=30))
    assert output.result.status == "ok" and output.result.usage.calls == 2
    assert clock.delays == [2]
    assert all(value == 4 for value in timeouts[0].values())
    assert all(value == 2 for value in timeouts[1].values())


def test_oversized_provider_body_is_invalid_and_does_not_retry():
    transport = httpx.MockTransport(lambda _: httpx.Response(200, content=b"x" * 256001))
    ledger, clock = MemoryLedger(), Clock()
    output = SearchGateway(TavilyAdapter(transport), ledger, SearchCost(per_attempt_upper_bound_usd=0, pricing_version="DEMO"), clock.now, clock.sleep).execute(
        context(), SearchCall(operation_id=uuid4(), agent=Role.SCOUT, tool="public.search", query="DEMO"))
    assert output.result.status == "invalid" and len(ledger.rows) == 1
    assert output.payload is None


def test_unknown_tool_version_fails_before_reservation_or_dispatch():
    recording, _, ledger, gateway, ctx, brief = setup()
    pinned = ctx.versions.model_dump() | {"tools": "DEMO-unreviewed-tool-version"}
    with pytest.raises(PolicyDenied, match="tool_version_mismatch"):
        search(context(versions=pinned), brief, gateway)
    assert recording.ordinal == len(ledger.rows) == 0
