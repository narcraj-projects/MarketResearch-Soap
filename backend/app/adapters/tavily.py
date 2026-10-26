"""Tavily wire adapter. Only an in-process recording transport is enabled now."""
from datetime import datetime
from email.utils import parsedate_to_datetime
from hashlib import sha256
import json
import time
from uuid import uuid5

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.harness.contracts import RunContext, SearchCall
from app.harness.policy import PolicyDenied
from app.harness.search import AttemptOutcome, ReplayMismatch, SearchPayload, SearchSource
from app.harness.urls import normalize_url

_GATEWAY_PERMIT = object()  # Architectural capability, not a security sandbox.
ADAPTER_VERSION = "tavily-search-1.0"


class Hit(BaseModel):
    model_config = ConfigDict(extra="ignore", hide_input_in_errors=True)
    title: str = Field(min_length=1, max_length=500, strict=True)
    url: str = Field(min_length=1, max_length=4000, strict=True)
    content: str = Field(min_length=1, max_length=10000, strict=True)
    score: float = Field(ge=0, le=1, allow_inf_nan=False)


class Response(BaseModel):
    model_config = ConfigDict(extra="ignore", hide_input_in_errors=True)
    query: str = Field(min_length=1, max_length=2000, strict=True)
    results: list[Hit] = Field(max_length=10)


class TavilyAdapter:
    def __init__(self, transport: httpx.MockTransport | None = None):
        if transport is not None and not isinstance(transport, httpx.MockTransport):
            raise PolicyDenied("live_not_approved")
        self._transport = transport

    def ensure_offline(self) -> None:
        if self._transport is None:
            raise PolicyDenied("live_not_approved")

    def _preflight(self, context: RunContext) -> None:
        self.ensure_offline()

    def _client(self, seconds: float):
        return httpx.Client(transport=self._transport, timeout=httpx.Timeout(seconds), follow_redirects=False, trust_env=False)

    def _headers(self) -> dict:
        return {"Authorization": "Bearer DEMO-not-a-key"}

    @staticmethod
    def request_body(call: SearchCall) -> dict:
        return {"query": call.query, "max_results": call.limit, "search_depth": "basic", "topic": "general",
            "include_answer": False, "include_raw_content": False, "include_images": False, "auto_parameters": False, "include_usage": True}

    def observe_cached(self, call: SearchCall):
        observer = getattr(self._transport, "_lather_replay_cached", None)
        if observer is not None:
            observer(self.request_body(call), call.attempt)

    def _dispatch(self, context: RunContext, call: SearchCall, seconds: float, now: datetime, *, permit: object) -> AttemptOutcome:
        if permit is not _GATEWAY_PERMIT:
            raise PolicyDenied("gateway_required")
        self._preflight(context)
        body = self.request_body(call)
        started = time.monotonic()
        try:
            with self._client(seconds) as client:
                # DEMO marker is not an API credential. No real transport/key factory exists.
                with client.stream("POST", "https://api.tavily.com/search", headers=self._headers(), json=body,
                    extensions={"lather_replay_attempt": call.attempt}) as response:
                    if response.status_code != 200:
                        retry_after = None
                        if response.status_code in {429, 503} and (value := response.headers.get("Retry-After")):
                            try:
                                retry_after = max(0.0, float(value))
                            except ValueError:
                                try:
                                    retry_after = max(0.0, (parsedate_to_datetime(value) - now).total_seconds())
                                except (ValueError, TypeError, OverflowError):
                                    pass
                            if retry_after is not None and (retry_after == float("inf") or retry_after != retry_after):
                                retry_after = None
                        if response.status_code == 429:
                            return AttemptOutcome(status="rate_limited", retryable=True, retry_after_seconds=retry_after)
                        if response.status_code in {500, 502, 503, 504}:
                            return AttemptOutcome(status="unavailable", retryable=True, retry_after_seconds=retry_after)
                        return AttemptOutcome(status="denied" if response.status_code in {401, 403, 432, 433} else "invalid")
                    chunks = bytearray()
                    for chunk in response.iter_bytes():
                        if time.monotonic() - started >= seconds:
                            return AttemptOutcome(status="timeout", retryable=True)
                        chunks.extend(chunk)
                        if len(chunks) > 256000:
                            return AttemptOutcome(status="invalid")
                    raw = json.loads(chunks)
                    parsed = Response.model_validate(raw)
                    if parsed.query != call.query or len(parsed.results) > call.limit:
                        return AttemptOutcome(status="invalid")
                    sources = []
                    rejected = 0
                    seen = set()
                    for hit in parsed.results:
                        try:
                            url, domain = normalize_url(hit.url, demo=True)
                        except ValueError:
                            rejected += 1
                            continue
                        content_hash = sha256(hit.content.encode()).hexdigest()
                        identity = f"{call.operation_id}:{call.attempt}:{url}:{content_hash}"
                        if url in seen:
                            continue
                        seen.add(url)
                        sources.append(SearchSource(source_id=uuid5(context.run_id, identity), canonical_url=url, domain=domain, title=hit.title,
                            publisher=urlsplit_host(url), excerpt=hit.content, content_hash=content_hash, retrieved_at=now))
                    return AttemptOutcome(status="ok", payload=SearchPayload(sources=tuple(sources), rejected_urls=rejected))
        except ReplayMismatch:
            raise
        except httpx.TimeoutException:
            return AttemptOutcome(status="timeout", retryable=True)
        except httpx.TransportError:
            return AttemptOutcome(status="unavailable", retryable=True)
        except (ValidationError, ValueError, TypeError, UnicodeError):
            return AttemptOutcome(status="invalid")


def urlsplit_host(url: str) -> str:
    from urllib.parse import urlsplit
    return urlsplit(url).hostname or "unknown"
