"""Research gateway: approved identity, per-wire accounting, public DNS/peer and robots."""
from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
import re
from threading import Lock
import time
from urllib.parse import urljoin, urlsplit
from uuid import UUID, uuid5

from app.adapters.public_web import RecordedWeb
from app.adapters.live_web import LivePublicWeb
from app.agents.extraction import canonical, parse_html
from .contracts import Phase, RunContext
from .policy import ALLOWLIST, PolicyDenied, require_approval
from .research_types import ResearchCall, ResearchJournal, RetrievedSource, WireOutcome, WireReply
from pydantic import JsonValue
from .search import ReplayMismatch
from .web_policy import Robots, destination, safe_url, verify_peer

TOOLS_VERSION = "public-research-1.0"


class ResearchGateway:
    def attempt_cost(self, call: ResearchCall) -> Decimal:
        assert self.cost is not None
        return self.cost

    def __init__(self, transport: RecordedWeb | LivePublicWeb | None, journal: ResearchJournal, *, cost_upper_bound: Decimal | None = Decimal(0),
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc), sleep: Callable[[float], None] = time.sleep,
                 guard: Callable[[], None] = lambda: None):
        if transport is not None and not isinstance(transport, RecordedWeb) and not isinstance(transport, LivePublicWeb):
            raise PolicyDenied("live_not_approved")
        self.transport, self.journal, self.cost = transport, journal, cost_upper_bound
        self.clock, self.sleep = clock, sleep
        self.guard = guard
        self.rate_lock = Lock()
        self.next_access: dict[str, datetime] = {}
        self.last_access: dict[str, datetime] = {}
        self.origin_locks: dict[str, Lock] = {}

    def access(self, context: RunContext) -> None:
        if isinstance(self.transport, LivePublicWeb):
            if context.mode != "live":
                raise PolicyDenied("live_context_required")
            self.transport.permit.check(context.run_id, context.user_id)
        elif context.mode == "live":
            raise PolicyDenied("live_transport_required")
        if context.phase != Phase.RESEARCH or context.versions.tools != TOOLS_VERSION:
            raise PolicyDenied("research_role_phase_or_version")
        require_approval(context, "shortlist")
        if self.clock() >= context.deadline:
            raise PolicyDenied("deadline")
        if self.transport is None:
            raise PolicyDenied("live_not_approved")
        if self.cost is None or not self.cost.is_finite() or self.cost < 0 or int(self.cost.as_tuple().exponent) < -8:
            raise PolicyDenied("unknown_cost")

    def _source(self, context: RunContext, call: ResearchCall, reply: WireReply, attempt: int = 0) -> RetrievedSource:
        url = call.url
        kind = "robots_policy" if call.kind == "robots" else "page_excerpt"
        status = "unavailable"
        reason: str | None = reply.failure or "http_unavailable"
        body, text, title = None, None, "Unavailable public resource"
        structured: tuple[JsonValue, ...] = ()
        links: tuple[str, ...] = ()
        if reply.status in {401, 403, 451}:
            status, reason = "denied", "access_restricted"
        if reply.status == 200 and reply.failure is None:
            body = reply.body
            if body is None or len(body.encode()) > 256000 or reply.encoding != "identity":
                reason = "unsupported_encoding_or_size"
                body = None
            elif call.kind == "robots":
                if len(body.encode()) > 64000 or not reply.content_type.lower().startswith("text/plain"):
                    reason, body = "robots_invalid_response", None
                else:
                    text, title = body, "Robots access policy"
                    status, reason = "ok", None
            elif reply.content_type.lower().split(";", 1)[0] in {"text/html", "application/xhtml+xml"}:
                try:
                    title, text, structured, links, restricted = parse_html(body, url)
                    restricted = restricted or any(token in (reply.robots_tag or "").lower() for token in ("noarchive", "nosnippet", "none"))
                    if restricted:
                        status, reason, body, text, structured, links = "denied", "access_restricted", None, None, (), ()
                        title = "Access-restricted public resource"
                    else:
                        status, reason = "ok", None
                except (ValueError, RecursionError):
                    reason, body = "invalid_html", None
            else:
                reason, body = "unsupported_content_type", None
        return RetrievedSource.model_validate(dict(label="LIVE" if context.mode == "live" else "DEMO", source_id=uuid5(context.run_id, f"source:{call.operation_id}:{url}:{attempt}"), competitor_id=call.competitor_id,
            canonical_url=url, requested_url=url, retrieved_at=self.clock(), title=title, publisher=urlsplit(url).hostname,
            access_status=status, evidence_kind=kind, body=body, excerpt=text, structured=structured, links=links, reason=reason,
            content_hash=sha256(body.encode()).hexdigest() if body is not None else None, text_hash=sha256(text.encode()).hexdigest() if text is not None else None))

    def _wire(self, context: RunContext, call: ResearchCall, delay: float = 0) -> WireOutcome:
        call = ResearchCall.model_validate(call.model_dump())
        self.access(context)
        if call.tool not in ALLOWLIST[call.agent]:
            raise PolicyDenied("tool_or_phase_denied")
        assert self.transport is not None and self.cost is not None
        if context.mode == "live":
            assert isinstance(self.transport, LivePublicWeb)
            self.transport.permit.check(context.run_id, context.user_id)
        cost = self.attempt_cost(call)
        # Every wire URL, including robots, redirects and the fixed news API, is independently pinned.
        url = safe_url(call.url)
        query = None
        if call.tool in {"public.news", "public.search"}:
            if url != "https://api.tavily.com/search":
                raise PolicyDenied("news_endpoint_denied")
            query = {"query": call.query, "topic": "general" if call.tool == "public.search" else "news", "search_depth": "basic", "max_results": 3,
                "include_answer": False, "include_raw_content": False, "include_images": False, "auto_parameters": False, "include_usage": True}
        last = None
        for attempt in range(1, 4):
            self.access(context)
            fingerprint = sha256(canonical({"call": call.model_dump(mode="json"), "versions": context.versions.model_dump(mode="json"), "cost": str(cost)}).encode()).hexdigest()
            cached = self.journal.reserve(context, call, attempt, fingerprint, cost, self.clock())
            if cached is not None:
                outcome = cached
                self.transport.observe_cached(urlsplit(url).hostname or "", str(call.operation_id), attempt)
            else:
                try:
                    target = destination(url, self.transport.resolve(urlsplit(url).hostname or "", operation_id=str(call.operation_id), attempt=attempt))
                    with self.rate_lock:
                        origin_lock = self.origin_locks.setdefault(self.origin(url), Lock())
                    with origin_lock:
                        if delay:
                            self._rate_limit(url, delay, context)
                        seconds = min(call.timeout_seconds, (context.deadline - self.clock()).total_seconds())
                        if seconds <= 0:
                            raise PolicyDenied("deadline")
                        self.guard()
                        reply = self.transport.exchange(target, method="POST" if query else "GET", query=query, timeout=seconds, attempt=attempt)
                        with self.rate_lock:
                            self.last_access[self.origin(url)] = self.clock()
                    if reply.failure is None:
                        verify_peer(target, reply.peer_ip)
                    if reply.location:
                        try:
                            normalized = safe_url(urljoin(url, reply.location))
                            if urlsplit(url).scheme == "https" and urlsplit(normalized).scheme != "https":
                                raise PolicyDenied("https_downgrade")
                            reply = WireReply.model_validate(reply.model_dump() | {"location": normalized})
                        except PolicyDenied:
                            reply = WireReply(status=0, failure="unsafe_redirect")
                    if reply.status != 200:
                        reply = WireReply.model_validate(reply.model_dump() | {"body": None})
                    source = self._source(context, call, reply, attempt) if call.kind != "news" else None
                    if source is not None and source.access_status != "ok":
                        reply = WireReply.model_validate(reply.model_dump() | {"body": None})
                    outcome = WireOutcome(competitor_id=call.competitor_id, reply=reply, source=source)
                except ReplayMismatch:
                    raise
                except PolicyDenied as error:
                    if str(error) in {"lease_lost_or_cancelled", "lease_owner_mismatch", "worker_lease_required"}:
                        raise
                    # Stable code only; never retain unsafe URL/header or a private response body.
                    reply = WireReply(status=0, failure="peer_mismatch" if str(error) in {"peer_mismatch", "nonpublic_address"} else "network")
                    outcome = WireOutcome(competitor_id=call.competitor_id, reply=reply, source=self._source(context, call, reply, attempt) if call.kind != "news" else None)
                self.journal.complete(context, call, attempt, fingerprint, outcome, self.clock())
            last = outcome
            if outcome.reply.failure not in {"timeout", "network"} and outcome.reply.status not in {429, 500, 502, 503, 504}:
                return outcome
            # Policy failures (including unrecorded/private DNS) are not bypassed by retries.
            if outcome.reply.status == 0 and outcome.reply.failure != "timeout":
                return outcome
            if attempt < 3:
                wait = max(outcome.reply.retry_after or 0, 0.5 * 2 ** (attempt - 1))
                if self.clock().timestamp() + wait >= context.deadline.timestamp():
                    return outcome
                self.sleep(wait)
        assert last is not None
        return last

    def _rate_limit(self, url: str, delay: float, context: RunContext) -> None:
        from datetime import timedelta
        origin = self.origin(url)
        with self.rate_lock:
            now = self.clock()
            scheduled = max(now, self.next_access.get(origin, now), self.last_access.get(origin, now) + timedelta(seconds=delay))
            self.next_access[origin] = scheduled + timedelta(seconds=delay)
        wait = (scheduled - now).total_seconds()
        if scheduled >= context.deadline:
            raise PolicyDenied("deadline")
        if wait > 0:
            self.sleep(wait)

    @staticmethod
    def origin(url: str) -> str:
        parsed = urlsplit(url)
        return parsed.scheme + "://" + parsed.netloc

    def retrieve(self, context: RunContext, competitor_id: UUID, raw_url: str) -> tuple[RetrievedSource, ...]:
        self.access(context)
        url = safe_url(raw_url)
        results: list[RetrievedSource] = []
        visited = set()
        for hop in range(4):
            if url in visited:
                break
            visited.add(url)
            robots_url = self.origin(url) + "/robots.txt"
            # Scope policy recordings per competitor, so lane ownership is never conflated.
            robots_call = ResearchCall(operation_id=uuid5(competitor_id, "robots:" + robots_url), competitor_id=competitor_id,
                tool="public.retrieve", url=robots_url, kind="robots")
            policy_outcome = self._wire(context, robots_call)
            if policy_outcome.source:
                results.append(policy_outcome.source)
            try:
                if policy_outcome.reply.status == 404:
                    policy = Robots("")
                elif policy_outcome.source and policy_outcome.source.access_status == "ok":
                    policy = Robots(policy_outcome.source.body or "")
                else:
                    raise PolicyDenied("robots_unavailable")
                if not policy.allows(url):
                    raise PolicyDenied("robots_disallowed")
            except PolicyDenied as error:
                denied_call = ResearchCall(operation_id=uuid5(competitor_id, "denied:" + url), competitor_id=competitor_id, tool="public.retrieve", url=url, kind="page")
                denied = self._source(context, denied_call, WireReply(status=403))
                denied = RetrievedSource.model_validate(denied.model_dump() | {"reason": str(error)})
                # A policy refusal has no page request or page-call charge; the lane stores this source.
                results.append(denied)
                return tuple(results)
            call = ResearchCall(operation_id=uuid5(competitor_id, "page:" + url), competitor_id=competitor_id, tool="public.retrieve", url=url, kind="page")
            outcome = self._wire(context, call, policy.delay)
            if outcome.source:
                results.append(outcome.source)
            if outcome.reply.status in {301, 302, 303, 307, 308} and outcome.reply.location:
                url = outcome.reply.location
                continue
            return tuple(results)
        return tuple(results)

    def news(self, context: RunContext, competitor_id: UUID, name: str) -> tuple[RetrievedSource, ...]:
        return self.search_evidence(context, competitor_id, name, product=False)

    def search_evidence(self, context: RunContext, competitor_id: UUID, name: str, *, product: bool, query_override: str | None = None, approved_domain: str | None = None) -> tuple[RetrievedSource, ...]:
        self.access(context)
        query = query_override or name + (" soap product price INR weight ingredients official India" if product else " soap product launches announcements")
        call = ResearchCall(operation_id=uuid5(competitor_id, "news:" + query), competitor_id=competitor_id, tool="public.search" if product else "public.news", kind="news",
            url="https://api.tavily.com/search", query=query)
        result = self._wire(context, call)
        if result.reply.status != 200:
            raise PolicyDenied("news_search_timeout" if result.reply.failure == "timeout" else "news_search_rate_limited" if result.reply.status == 429 else "news_search_unavailable")
        if not result.reply.body or len(result.reply.body.encode()) > 256000:
            raise PolicyDenied("news_search_invalid")
        try:
            body = json.loads(result.reply.body)
            equivalent_query = query.replace("site:" + approved_domain + " ", "", 1) if approved_domain else query
            equivalent_unquoted = equivalent_query.replace('"', '') if approved_domain else query
            if body.get("query") not in {query, equivalent_query, equivalent_unquoted} or not isinstance(body.get("results"), list) or len(body["results"]) > 3:
                raise PolicyDenied("news_search_invalid")
            hits = []
            for hit in body["results"]:
                if not isinstance(hit, dict) or not isinstance(hit.get("content"), str) or not hit["content"] or len(hit["content"]) > 10000:
                    continue
                try:
                    url = safe_url(hit["url"])
                except (KeyError, PolicyDenied):
                    continue
                host = (urlsplit(url).hostname or "").removeprefix("www.")
                first_party_match = approved_domain is not None and host == approved_domain.removeprefix("www.")
                if approved_domain is not None and not first_party_match:
                    continue
                if not first_party_match and not re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", hit["content"], re.I):
                    continue
                content = hit["content"]
                identity = f"supplement:{competitor_id}:{query}:{url}" if query_override else f"news:{competitor_id}:{url}"
                hits.append(RetrievedSource(label="LIVE" if context.mode == "live" else "DEMO", source_id=uuid5(context.run_id, identity), competitor_id=competitor_id,
                    canonical_url=url, requested_url=url, retrieved_at=result.source.retrieved_at if result.source else self.clock(), title=str(hit.get("title") or "News search result")[:500], publisher=urlsplit(url).hostname or "unknown",
                    access_status="ok", evidence_kind="search_snippet", content_hash=sha256(content.encode()).hexdigest(), text_hash=sha256(content.encode()).hexdigest(), body=content, excerpt=content))
            return tuple(hits)
        except (ValueError, TypeError):
            raise PolicyDenied("news_search_invalid") from None
