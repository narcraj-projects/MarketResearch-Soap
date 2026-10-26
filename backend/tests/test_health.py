import asyncio
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from app.config import Settings
from app.db import Base, build_engine
from app.main import create_app


@pytest.fixture(scope="session")
def asgi_loop():
    # Windows initializes a local asyncio control socket before function-scoped
    # network blocking. All requests below use ASGITransport, never TCP.
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def test_health_lifecycle_without_network_or_database(asgi_loop):
    async def exercise():
        app = create_app(Settings(_env_file=None, environment="test"))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            assert (await client.get("/health/live")).json()["status"] == "alive"
            assert (await client.get("/health/ready")).status_code == 503
            async with app.router.lifespan_context(app):
                response = await client.get("/health/ready")
                assert response.status_code == 200
                assert response.json() == {
                    "status": "ready", "mode": "replay", "database": "not_checked",
                    "external_calls_enabled": False,
                }
            assert (await client.get("/health/ready")).status_code == 503

    asgi_loop.run_until_complete(exercise())


@pytest.mark.parametrize("field,value", [("mode", "live"), ("external_calls_enabled", True), ("langsmith_enabled", True)])
def test_config_rejects_live_services(field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


def test_database_is_unconfigured_and_domain_metadata_exists():
    assert "briefs" in Base.metadata.tables
    with pytest.raises(RuntimeError, match="database_not_configured"):
        build_engine(Settings(_env_file=None))


def test_bad_database_url_is_not_exposed_in_validation_message():
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, database_url="DEMO-invalid-private-value")
    assert "DEMO-invalid-private-value" not in str(error.value)


def test_checked_in_env_example_is_valid_and_offline():
    example = Path(__file__).resolve().parents[2] / ".env.example"
    settings = Settings(_env_file=example)
    assert settings.mode == "replay"
    assert settings.external_calls_enabled is False
    assert settings.langsmith_enabled is False
    assert settings.database_url is None
