"""Supabase validates access tokens; never decode unsigned identity claims."""
from dataclasses import dataclass
from uuid import UUID

import httpx
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import SecretStr

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Identity:
    user_id: UUID


class SupabaseAuth:
    def __init__(self, url: str, publishable_key: SecretStr):
        self.url = url.rstrip("/")
        self.key = publishable_key

    def verify(self, token: str) -> Identity:
        try:
            with httpx.Client(timeout=5, follow_redirects=False, trust_env=False) as client:
                response = client.get(self.url + "/auth/v1/user", headers={
                    "apikey": self.key.get_secret_value(), "Authorization": "Bearer " + token,
                })
            if response.status_code >= 500 or response.status_code == 429:
                raise HTTPException(503, "authentication_unavailable")
            if response.status_code != 200:
                raise ValueError("invalid")
            data = response.json()
            if data.get("role") != "authenticated" or data.get("is_anonymous", False):
                raise ValueError("invalid")
            return Identity(UUID(data["id"]))
        except (httpx.RequestError, httpx.HTTPError):
            raise HTTPException(503, "authentication_unavailable") from None
        except (ValueError, KeyError, TypeError):
            raise HTTPException(401, "invalid_access_token", headers={"WWW-Authenticate": "Bearer"}) from None


def current_user(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Identity:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "authentication_required", headers={"WWW-Authenticate": "Bearer"})
    settings = request.app.state.settings
    if settings.supabase_url is None or settings.supabase_publishable_key is None:
        raise HTTPException(503, "authentication_not_configured")
    return SupabaseAuth(str(settings.supabase_url), settings.supabase_publishable_key).verify(credentials.credentials)
