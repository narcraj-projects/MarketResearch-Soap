"""SEC01+: adversarial inputs; no sockets, credentials or provider requests."""
import logging
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from pydantic import ValidationError

from app.auth import Identity, current_user
from app.config import Settings
from app.main import create_app
from app.security import IngressGuard, WindowLimiter, configure_private_logging
from app.harness.urls import normalize_url
from app.harness.policy import PolicyDenied
from app.harness.web_policy import destination, public_ip
from uuid import UUID


def test_sec01_validation_does_not_echo_input_or_attacker_field_names(integration_loop):
    async def exercise():
        app = create_app(Settings(_env_file=None))
        app.dependency_overrides[current_user] = lambda: Identity(UUID(int=1))
        # /auth/me is dependency-only; invalid route UUID triggers validation
        # after identity. Override storage so no connection can occur.
        from app.api import repository
        app.dependency_overrides[repository] = lambda: None
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.get("/api/runs/DEMO-private-secret")
            assert response.status_code == 422 and response.json() == {"detail": "invalid_request"}
            schema = (await client.get("/openapi.json")).json()
            assert schema["paths"]["/api/runs/{run_id}"]["get"]["responses"]["422"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/Error"
            response = await client.post("/api/briefs", json={"DEMO-private-field": "DEMO-password"})
            assert response.status_code == 422
            assert "DEMO" not in response.text
            assert response.headers["cache-control"] == "no-store"
            cross = await client.options("/api/briefs", headers={"Origin": "https://evil.invalid", "Access-Control-Request-Method": "POST"})
            assert "access-control-allow-origin" not in cross.headers
    integration_loop.run_until_complete(exercise())


def test_sec02_streamed_body_limit_before_auth_or_route(integration_loop):
    async def exercise():
        app = create_app(Settings(_env_file=None))
        async def chunks():
            yield b'{"value":"' + b'x' * 33000
            yield b'x' * 33000 + b'"}'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            assert (await client.post("/api/briefs", content=chunks(), headers={"Content-Type": "application/json"})).status_code == 413
            assert (await client.post("/api/briefs", content="{}", headers={"Content-Type": "application/json", "Content-Encoding": "gzip"})).status_code == 415
            assert (await client.get("/api/auth/me", headers={"Authorization": "Bearer " + "x" * 8192})).status_code == 431
            assert (await client.post("/api/briefs", content="[" * 2000, headers={"Content-Type": "application/json"})).status_code == 422
    integration_loop.run_until_complete(exercise())


def test_sec03_rate_limits_are_atomic_bounded_and_ignore_forwarded_identity(integration_loop):
    clock = [0.0]
    limiter = WindowLimiter(limit=3, capacity=1, clock=lambda: clock[0])
    with ThreadPoolExecutor(8) as pool:
        assert sum(pool.map(lambda _: limiter.allow("peer"), range(20))) == 3
    assert not limiter.allow("new-peer") and len(limiter.entries) == 1
    clock[0] = 60
    assert limiter.allow("new-peer")
    async def exercise():
        app = IngressGuard(create_app(Settings(_env_file=None)), WindowLimiter(limit=1))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            assert (await client.get("/api/auth/me")).status_code == 401
            result = await client.get("/api/auth/me", headers={"X-Forwarded-For": "8.8.8.8"})
            assert result.status_code == 429 and result.headers["retry-after"] == "60"
    integration_loop.run_until_complete(exercise())


def test_sec04_transport_logging_discards_url_token_and_exception(caplog):
    configure_private_logging()
    canary = "DEMO-secret-log-canary"
    with caplog.at_level(logging.DEBUG):
        try:
            raise ValueError(canary)
        except ValueError:
            for name in ("httpx", "httpcore.connection", "httpcore.http11", "httpcore.proxy.nested", "uvicorn.access", "uvicorn.error"):
                logging.getLogger(name).exception("GET https://example.invalid/?token=%s", canary)
    assert canary not in caplog.text and "private_transport_event" in caplog.text


@pytest.mark.parametrize("query", ["access_token", "api%5fkey", "%2574oken", "x-amz-signature", "client_secret"])
def test_sec05_sensitive_url_query_never_persisted(query):
    with pytest.raises(ValueError, match="unsafe_source_url"):
        normalize_url("https://example.com/?" + query + "=DEMO-secret")


@pytest.mark.parametrize("ip", ["192.0.0.8", "192.0.0.170", "198.18.0.1", "192.0.2.1", "2001:db8::1", "64:ff9b:1::a00:1", "64:ff9b::7f00:1", "2001::1", "ff02::1"])
def test_sec06_special_use_addresses_and_mixed_dns_denied(ip):
    with pytest.raises(PolicyDenied):
        public_ip(ip)
    with pytest.raises(PolicyDenied):
        destination("https://example.com/", ("8.8.8.8", ip))


@pytest.mark.parametrize("url", ["http://supabase.example.com", "https://user:DEMO@example.com/", "https://example.com/?token=DEMO", "https://example.com/auth"])
def test_sec07_auth_origin_config_rejects_credentials_path_query_or_insecure_remote(url):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", supabase_url=url)


