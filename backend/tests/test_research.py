from hashlib import sha256
import json
import socket
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.adapters.public_web import RecordedWeb, _PinnedHTTPSConnection
from app.agents.extraction import contradictions, extract, parse_html
from app.harness.contracts import Phase
from app.harness.policy import PolicyDenied
from app.harness.research_types import RetrievedSource
from app.harness.retrieval import ResearchGateway
from app.harness.search import ReplayMismatch
from app.harness.web_policy import Destination, Robots, destination, public_ip, safe_url, verify_peer
from tests.research_support import FOLDER, MemoryJournal, context, setup


@pytest.mark.parametrize("path", [p for p in sorted(FOLDER.glob("R*.json")) if "parallel" not in p.stem], ids=lambda p: p.stem)
def test_research_recordings(path):
    recording, journal, clock, gateway, ctx = setup(path.stem)
    cid = UUID(int=10)
    competitor = recording.case["competitor"]
    sources = list(gateway.retrieve(ctx, cid, competitor["url"]))
    if recording.case.get("include_news"):
        news = gateway.news(ctx, cid, competitor["name"])
        sources.extend(news)
        for hit in news:
            sources.extend(gateway.retrieve(ctx, cid, hit.canonical_url))
    pages = tuple(extract(source, competitor["name"], first_party=source.publisher.endswith("demo-a.invalid")) for source in sources if source.evidence_kind == "page_excerpt")
    products = [product for page in pages for product in page.products]
    expected = recording.case["expected"]
    assert len(products) == expected["products"]
    if "amounts" in expected:
        assert [str(p.amount) if p.amount is not None else None for p in products] == expected["amounts"]
    if "totals" in expected:
        assert [str(p.total_weight_g) if p.total_weight_g is not None else None for p in products] == expected["totals"]
    if "sku" in expected:
        assert products[0].sku is expected["sku"]
    if "conflicts" in expected:
        assert len(contradictions(pages)) == expected["conflicts"]
    if "denied" in expected:
        assert any(source.access_status == "denied" for source in sources)
        assert all(source.body is None and source.excerpt is None for source in sources if source.access_status == "denied")
    if "page_requests" in expected:
        assert recording.requests.count("GET " + competitor["url"]) == expected["page_requests"]
    if "launches" in expected:
        assert sum(o.field == "reported_launch" and o.value is not None for page in pages for o in page.observations) == expected["launches"]
    if "retry_delays" in expected:
        assert clock.delays == expected["retry_delays"]
    for page in pages:
        for observation in [*page.observations, *(o for p in page.products for o in p.observations)]:
            for evidence in observation.evidence:
                source = next(s for s in sources if s.source_id == evidence.source_id)
                assert evidence.quote in source.excerpt and sha256(evidence.quote.encode()).hexdigest() == evidence.quote_hash
    assert all(row["outcome"] is not None for row in journal.rows.values())


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.1", "172.16.0.1", "192.168.1.1", "169.254.169.254", "100.64.0.1", "0.0.0.0", "224.0.0.1", "::1", "fe80::1", "fc00::1", "::ffff:8.8.8.8", "2002:0808:0808::1"])
def test_nonpublic_or_tunneled_ips_denied(ip):
    with pytest.raises(PolicyDenied):
        public_ip(ip)


@pytest.mark.parametrize("url", ["file:///etc/passwd", "gopher://example.com/", "https://user:password@example.com/", "http://2130706433/", "http://0x7f000001/", "http://[::1]/", "https://example.com:444/", "https://example.com/%0d%0a", "https://example.com/%256cogin", "https://example.com/account", "https://example.com/?token=DEMO", "https://example.com\\@localhost/", "https://example.com/a/%252e%252e/private", "https://example.com/%2Fprivate"])
def test_unsafe_urls_fail_before_transport(url):
    with pytest.raises(PolicyDenied):
        safe_url(url)


def test_dns_answer_set_and_peer_pin():
    with pytest.raises(PolicyDenied):
        destination("https://example.com/", ("8.8.8.8", "127.0.0.1"))
    target = destination("https://example.com/", ("8.8.8.8",))
    with pytest.raises(PolicyDenied):
        verify_peer(target, "1.1.1.1")
    verify_peer(target, "8.8.8.8")


def test_native_tls_connects_only_to_pinned_ip_and_keeps_original_sni(monkeypatch):
    connected, sni = [], []
    class Socket:
        def getpeername(self): return ("8.8.8.8", 443)
        def close(self): pass
    sock = Socket()
    def connect(address, timeout):
        connected.append(address)
        return sock
    class TLS:
        def wrap_socket(self, raw, server_hostname):
            sni.append(server_hostname)
            return raw
    monkeypatch.setattr(socket, "create_connection", connect)
    target = Destination("https://example.com/", "example.com", 443, "8.8.8.8")
    connection = _PinnedHTTPSConnection(target, 1)
    connection.tls_context = TLS()
    connection.connect()
    assert connected == [("8.8.8.8", 443)] and sni == ["example.com"]


def test_robots_longest_match_allow_tie_wildcards_and_merged_agents():
    policy = Robots("User-agent: *\nDisallow: /\nUser-agent: LatherLensBot\nDisallow: /private*\nAllow: /private/public$\nUser-agent: latherlensbot\nDisallow: /other\n")
    assert policy.allows("https://example.com/")
    assert not policy.allows("https://example.com/private/x")
    assert policy.allows("https://example.com/private/public")
    assert not policy.allows("https://example.com/other")
    assert Robots("User-agent: *\nDisallow: /a\nAllow: /a").allows("https://example.com/a")


def test_approval_phase_and_live_factory_fail_closed():
    recording, _, _, gateway, ctx = setup()
    for changed in ({"approvals": ()}, {"phase": Phase.DISCOVER}):
        with pytest.raises(PolicyDenied):
            gateway.retrieve(context(**changed), UUID(int=10), recording.case["competitor"]["url"])
    with pytest.raises(PolicyDenied, match="live_not_approved"):
        ResearchGateway(None, MemoryJournal(), clock=gateway.clock).retrieve(ctx, UUID(int=10), "https://example.com/")
    assert recording.requests == []


def test_completed_retrieval_replay_does_not_repeat_requests():
    recording, _, _, gateway, ctx = setup()
    first = gateway.retrieve(ctx, UUID(int=10), recording.case["competitor"]["url"])
    second = gateway.retrieve(ctx, UUID(int=10), recording.case["competitor"]["url"])
    assert first == second and len(recording.requests) == 2


def test_source_hash_and_forged_body_rejected():
    recording, _, _, gateway, ctx = setup()
    source = gateway.retrieve(ctx, UUID(int=10), recording.case["competitor"]["url"])[-1]
    with pytest.raises(ValidationError, match="source_hash_mismatch"):
        RetrievedSource.model_validate(source.model_dump() | {"body": "DEMO forged content"})


def test_recording_modification_never_falls_back_to_network(tmp_path):
    case = FOLDER / "R01-complete.json"
    (tmp_path / "manifest.json").write_bytes((FOLDER / "manifest.json").read_bytes())
    (tmp_path / case.name).write_text("{}")
    with pytest.raises(ReplayMismatch):
        RecordedWeb(tmp_path / case.name)


def test_empty_sku_and_ingredients_stay_null_while_explicit_zero_price_is_preserved():
    recording, _, _, gateway, ctx = setup()
    source = gateway.retrieve(ctx, UUID(int=10), recording.case["competitor"]["url"])[-1]
    node = {"@type": "Product", "name": "DEMO empty fields", "sku": "", "additionalProperty": {"name": "Ingredients", "value": ""},
        "offers": {"price": "0", "priceCurrency": "INR"}}
    body = '<script type="application/ld+json">' + json.dumps(node) + '</script>'
    title, excerpt, structured, links, _ = parse_html(body, source.canonical_url)
    changed = RetrievedSource.model_validate(source.model_dump() | {"body": body, "excerpt": excerpt, "title": title, "structured": structured, "links": links,
        "content_hash": sha256(body.encode()).hexdigest(), "text_hash": sha256(excerpt.encode()).hexdigest()})
    result = extract(changed, "DEMO Maker A", first_party=True)
    product = result.products[0]
    assert product.sku is None and product.ingredients is None and product.amount == 0
    assert next(o for o in product.observations if o.field == "sku").value is None
