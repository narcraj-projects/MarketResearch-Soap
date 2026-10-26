"""Validated local-only settings. No vendor SDKs or network initialization."""
from pathlib import Path
import base64
import json
from typing import Literal
from uuid import UUID

from pydantic import AnyHttpUrl, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LATHER_",
        env_file=Path(__file__).resolve().parents[2] / ".env",
        extra="ignore",
        hide_input_in_errors=True,
    )
    environment: Literal["local", "test", "production"] = "local"
    chaos_enabled: bool = False
    evaluations_enabled: bool = False
    trusted_reviewer_ids: tuple[UUID, ...] = ()
    business_owner_ids: tuple[UUID, ...] = ()
    mode: Literal["replay"] = "replay"
    external_calls_enabled: Literal[False] = False
    langsmith_enabled: Literal[False] = False
    database_url: SecretStr | None = None
    supabase_url: AnyHttpUrl | None = None
    supabase_publishable_key: SecretStr | None = None

    @model_validator(mode="after")
    def test_faults_only(self):
        if self.supabase_url is not None:
            url = self.supabase_url
            if (url.username or url.password or url.query or url.fragment or url.path not in {None, "/"}
                or (url.scheme != "https" and not (self.environment != "production" and url.host in {"127.0.0.1", "localhost", "::1"}))):
                raise ValueError("secure_supabase_origin_required")
        if self.chaos_enabled and self.environment != "test":
            raise ValueError("chaos_requires_test_environment")
        if self.evaluations_enabled and self.environment != "test":
            raise ValueError("evaluations_require_test_environment")
        return self

    @field_validator("supabase_publishable_key")
    @classmethod
    def public_key_only(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        key = value.get_secret_value()
        if key.startswith("sb_publishable_"):
            return value
        try:
            part = key.split(".")[1]
            payload = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
            if payload.get("role") == "anon":
                return value  # classification only; token verification is Auth's job
        except (ValueError, IndexError, TypeError):
            pass
        raise ValueError("publishable_or_anon_key_required")

    @field_validator("external_calls_enabled", "langsmith_enabled", mode="before")
    @classmethod
    def disabled_services(cls, value: object) -> Literal[False]:
        if value is False or value == "false":
            return False
        raise ValueError("external_services_disabled")

    @field_validator("database_url")
    @classmethod
    def postgres_only(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        try:
            url = make_url(value.get_secret_value())
            if url.drivername != "postgresql+psycopg":
                raise ValueError("driver")
        except Exception:
            raise ValueError("database_url_requires_postgresql_psycopg") from None
        return value
