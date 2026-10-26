"""Explicit one-run authorization. Keys are local configuration, never job data."""
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.security import configure_private_logging
from .policy import PolicyDenied

ROOT = Path(__file__).resolve().parents[3]
CREDIT_USD = Decimal("0.008")  # Public Tavily pay-as-you-go upper bound, verified 2026-10-26.
MODEL_RESERVATION = Decimal("0.50")


class LiveSecrets(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore", hide_input_in_errors=True)
    lather_tavily_api_key: SecretStr | None = None
    lather_llm_api_key: SecretStr | None = None


class LivePermit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    schema_version: str = "live-permit-1.0"
    run_id: UUID
    owner_id: UUID
    max_tavily_credits: int = Field(ge=1, le=20)
    max_model_usd: Decimal = Field(ge=0, le=5)
    expires_at: datetime
    provider: str = "fireworks"
    model: str = "accounts/fireworks/models/kimi-k3"
    endpoint: str = "https://api.fireworks.ai/inference/v1/chat/completions"
    input_usd_per_million: Decimal = Decimal("3")
    output_usd_per_million: Decimal = Decimal("15")
    approval_note: str = "User approved one run, <=10 Tavily credits and <=USD5 LLM usage, 2026-10-26. No deployment."
    supplementary_query: str | None = Field(default=None, max_length=2000)
    discovery_revision: int = Field(default=0, ge=0, le=1)
    continuation_query: str | None = Field(default=None, max_length=2000)

    def check(self, run_id: UUID, owner_id: UUID):
        if (self.schema_version != "live-permit-1.0" or self.run_id != run_id or self.owner_id != owner_id
            or not 1 <= self.max_tavily_credits <= 20 or not Decimal(0) <= self.max_model_usd <= 5
            or self.expires_at.utcoffset() is None or datetime.now(timezone.utc) >= self.expires_at
            or self.endpoint != "https://api.fireworks.ai/inference/v1/chat/completions"
            or self.model != "accounts/fireworks/models/kimi-k3"
            or self.input_usd_per_million != 3 or self.output_usd_per_million != 15):
            raise PolicyDenied("live_run_not_authorized")


def load_permit(run_id: UUID, owner_id: UUID) -> LivePermit:
    try:
        value = LivePermit.model_validate(json.loads((ROOT / ".cache/live-authorization.json").read_text()))
        value.check(run_id, owner_id)
        configure_private_logging()
        return value
    except (OSError, ValueError, TypeError):
        raise PolicyDenied("live_run_not_authorized") from None


def enforce_credit_cap(rows, permit: LivePermit, cost: Decimal):
    if cost == CREDIT_USD and sum(row["cost_upper_bound_usd"] == CREDIT_USD and not (row.get("outcome") or {}).get("schema_version") == "model-live-1.0" for row in rows) >= permit.max_tavily_credits:
        raise PolicyDenied("tavily_credit_cap")
    if cost == MODEL_RESERVATION and sum((row["cost_upper_bound_usd"] for row in rows if row["cost_upper_bound_usd"] == MODEL_RESERVATION or (row.get("outcome") or {}).get("schema_version") == "model-live-1.0"), Decimal(0)) + cost > permit.max_model_usd:
        raise PolicyDenied("model_spend_cap")
