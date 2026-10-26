"""Bounded ingress and privacy controls; no raw inputs enter security logs."""
from collections import OrderedDict
from hashlib import sha256
import json
import logging
from threading import Lock
from time import monotonic

from starlette.responses import JSONResponse

BODY_LIMIT = 65536


class WindowLimiter:
    """Per-process safety valve, not a distributed abuse-prevention service."""
    def __init__(self, limit=600, window=60, capacity=4096, clock=monotonic):
        self.limit, self.window, self.capacity, self.clock = limit, window, capacity, clock
        self.entries: OrderedDict[str, tuple[float, int]] = OrderedDict()
        self.lock = Lock()

    def allow(self, key: str) -> bool:
        key = sha256(key.encode()).hexdigest()
        with self.lock:
            now = self.clock()
            # Expire old entries; never evict a live bucket to admit new identities.
            while self.entries and now - next(iter(self.entries.values()))[0] >= self.window:
                self.entries.popitem(last=False)
            if key not in self.entries and len(self.entries) >= self.capacity:
                return False
            began, count = self.entries.get(key, (now, 0))
            if count >= self.limit:
                return False
            self.entries[key] = began, count + 1
            return True


class PrivateTransportFilter(logging.Filter):
    """Suppress SDK/access-log text, URL queries and exception payloads entirely."""
    def filter(self, record):
        record.msg, record.args = "private_transport_event", ()
        record.exc_info, record.exc_text, record.stack_info = None, None, None
        return True


def configure_private_logging():
    previous = logging.getLogRecordFactory()
    if not getattr(previous, "_lather_private", False):
        def private_record(*args, **kwargs):
            record = previous(*args, **kwargs)
            if str(record.name).startswith(("httpx", "httpcore", "uvicorn.access", "uvicorn.error")):
                PrivateTransportFilter().filter(record)
            return record
        setattr(private_record, "_lather_private", True)
        logging.setLogRecordFactory(private_record)
    for name in ("httpx", "httpcore.connection", "httpcore.http11", "httpcore.http2", "uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(name)
        if not any(isinstance(item, PrivateTransportFilter) for item in logger.filters):
            logger.addFilter(PrivateTransportFilter())


class IngressGuard:
    """Pure ASGI: limit chunked bodies as well as declared lengths; preserve SSE."""
    def __init__(self, app, limiter=None):
        self.app, self.limiter = app, limiter or WindowLimiter()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            return await self.app(scope, receive, send)

        async def reject(code, status):
            await JSONResponse({"detail": code}, status_code=status, headers={
                "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                **({"Retry-After": "60"} if status == 429 else {})})(scope, receive, send)

        peer = scope.get("client") or ("unknown", 0)
        if not self.limiter.allow(str(peer[0])):
            return await reject("request_rate_limit", 429)
        headers = dict(scope.get("headers", []))
        if any(len(headers.get(name, b"")) > 8192 for name in (b"authorization", b"cookie")):
            return await reject("header_limit", 431)
        if len(scope.get("query_string", b"")) > 8192:
            return await reject("query_limit", 414)
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            return await reject("invalid_content_length", 400)
        if length < 0 or length > BODY_LIMIT:
            return await reject("request_body_limit", 413)
        if scope["method"] in {"POST", "PUT", "PATCH"}:
            if headers.get(b"content-encoding", b"identity").lower() != b"identity":
                return await reject("content_encoding_denied", 415)
            if headers.get(b"content-type", b"").split(b";")[0].strip().lower() != b"application/json":
                return await reject("json_required", 415)
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > BODY_LIMIT:
                    return await reject("request_body_limit", 413)
                if not message.get("more_body", False):
                    break
            try:
                json.loads(body)
            except (ValueError, RecursionError, UnicodeError):
                return await reject("invalid_json", 422)
            async def buffered():
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await self.app(scope, buffered, send)
        return await self.app(scope, receive, send)
