import httpx
import pytest
from fastapi import HTTPException
from pydantic import SecretStr, ValidationError

from app.auth import SupabaseAuth
from app.config import Settings
from app.main import create_app


def test_protected_routes_reject_missing_bearer_and_expose_openapi(integration_loop):
    async def exercise():
        app = create_app(Settings(_env_file=None, environment="test"))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            for path in ("/api/auth/me", "/api/history", "/api/runs/00000000-0000-0000-0000-000000000001"):
                assert (await client.get(path)).status_code == 401
            schema = (await client.get("/openapi.json")).json()
            assert schema["paths"]["/api/runs"]["post"]["security"] == [{"HTTPBearer": []}]
            assert "RunCreate" in schema["components"]["schemas"]
    integration_loop.run_until_complete(exercise())


@pytest.mark.parametrize("key", ["sb_secret_DEMO", "not-a-publishable-key"])
def test_config_rejects_privileged_or_invalid_api_key(key):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, supabase_publishable_key=key)


def test_invalid_token_response_is_401_without_echo(monkeypatch):
    monkeypatch.setattr(httpx.Client, "get", lambda *args, **kwargs: httpx.Response(401))
    with pytest.raises(HTTPException) as exc:
        SupabaseAuth("http://127.0.0.1:57421", SecretStr("sb_publishable_DEMO")).verify("DEMO-invalid-token")
    assert exc.value.status_code == 401
    assert exc.value.detail == "invalid_access_token"


def test_frontend_contains_no_service_role_configuration():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    for file in (root / "frontend/src").rglob("*"):
        if file.is_file():
            value = file.read_text(encoding="utf-8")
            assert "SUPABASE_SERVICE_ROLE" not in value
            assert "sb_secret_" not in value
    assert "NEXT_PUBLIC_SUPABASE_SERVICE" not in (root / ".env.example").read_text(encoding="utf-8")
