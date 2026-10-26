"""Pinned public HTTPS, with existing robots/redirect gateway policy above it."""
import http.client
import json
import socket
import ssl
from threading import Lock
from urllib.parse import urlsplit

import httpx

from app.adapters.public_web import _PinnedHTTPSConnection
from app.harness.live_policy import LivePermit, LiveSecrets, ROOT
from app.harness.policy import PolicyDenied
from app.harness.research_types import WireReply
from app.harness.web_policy import Destination, USER_AGENT, public_ip, verify_peer, destination


class PinnedTavilyTransport(httpx.BaseTransport):
    """Fixed API host, all-address DNS validation, pinned socket and original TLS SNI."""
    def __init__(self, target=None):
        self.target = target

    def handle_request(self, request):
        if str(request.url) != "https://api.tavily.com/search" or request.method != "POST":
            raise PolicyDenied("tavily_endpoint_denied")
        body = request.read()
        data = json.loads(body)
        if len(body) > 16000 or data.get("search_depth") != "basic" or data.get("auto_parameters") is not False:
            raise PolicyDenied("tavily_basic_only")
        addresses = tuple(sorted({str(item[4][0]) for item in socket.getaddrinfo("api.tavily.com", 443, type=socket.SOCK_STREAM)})) if self.target is None else (self.target.ip,)
        target = self.target or destination(str(request.url), addresses)
        timeout = request.extensions.get("timeout", {}).get("read") or 15
        conn = _PinnedHTTPSConnection(target, timeout)
        try:
            conn.request("POST", "/search", body=body, headers={"Authorization": request.headers["authorization"], "Content-Type": "application/json", "Accept-Encoding": "identity"})
            verify_peer(target, conn.sock.getpeername()[0] if conn.sock else None)
            response = conn.getresponse()
            raw = response.read(256001)
            if len(raw) > 256000:
                raise PolicyDenied("tavily_response_limit")
            if response.status == 200:
                # Public provider payload only; never persist Authorization headers.
                from hashlib import sha256
                from uuid import uuid4
                folder = ROOT / ".cache/live-public-responses"
                folder.mkdir(parents=True, exist_ok=True)
                (folder / (sha256(body).hexdigest()[:16] + "-" + uuid4().hex + ".json")).write_bytes(raw)
            return httpx.Response(response.status, content=raw, headers={"Content-Type": "application/json", "Retry-After": response.getheader("Retry-After", "0")})
        except (TimeoutError, socket.timeout):
            raise httpx.ReadTimeout("live_tool_timeout") from None
        except (OSError, ssl.SSLError, http.client.HTTPException):
            raise httpx.ConnectError("live_tool_network_error") from None
        finally:
            conn.close()


class LivePublicWeb:
    approved_live_transport = True

    def __init__(self, permit: LivePermit, *, transport: httpx.MockTransport | None = None):
        self.permit, self.mock = permit, transport
        self.requests: list[str] = []
        self.lock = Lock()
        self.ordinal = 0

    def resolve(self, host: str, *, operation_id=None, attempt=1):
        if self.mock is not None:
            return ("8.8.8.8",)
        try:
            return tuple(sorted({public_ip(str(item[4][0])) for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}))
        except (OSError, ValueError):
            raise PolicyDenied("dns_unavailable") from None

    def observe_cached(self, *args):
        pass

    def exchange(self, target: Destination, *, method: str, query: dict | None, timeout: float, attempt=None):
        self.permit.check(self.permit.run_id, self.permit.owner_id)
        if target.port != 443 or urlsplit(target.url).scheme != "https":
            raise PolicyDenied("https_only_live_pilot")
        with self.lock:
            self.requests.append("POST tavily" if query else "GET public_page")
            self.ordinal += 1
        if query:
            if target.url != "https://api.tavily.com/search" or method != "POST" or query.get("search_depth") != "basic" or query.get("auto_parameters") is not False:
                raise PolicyDenied("live_tool_not_allowed")
            secret = LiveSecrets().lather_tavily_api_key
            if secret is None:
                raise PolicyDenied("tavily_key_missing")
            try:
                with httpx.Client(transport=self.mock or PinnedTavilyTransport(target), trust_env=False, follow_redirects=False, timeout=timeout) as client:
                    with client.stream("POST", target.url, headers={"Authorization": "Bearer " + secret.get_secret_value()}, json=query) as response:
                        body = bytearray()
                        for chunk in response.iter_bytes():
                            body.extend(chunk)
                            if len(body) > 256000:
                                return WireReply(status=0, failure="response_limit")
                        return WireReply(status=response.status_code, body=body.decode("utf8") if response.status_code == 200 else None,
                            content_type="application/json", peer_ip=target.ip)
            except httpx.TimeoutException:
                return WireReply(status=0, failure="timeout")
            except (httpx.HTTPError, UnicodeError, ValueError):
                return WireReply(status=0, failure="network")
        if method != "GET":
            raise PolicyDenied("public_read_only")
        conn = _PinnedHTTPSConnection(target, timeout)
        try:
            parsed = urlsplit(target.url)
            path = parsed.path + ("?" + parsed.query if parsed.query else "")
            conn.request("GET", path, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity", "Accept": "text/html,text/plain;q=0.9"})
            verify_peer(target, conn.sock.getpeername()[0] if conn.sock else None)
            page_response = conn.getresponse()
            raw = page_response.read(256001)
            if len(raw) > 256000:
                return WireReply(status=0, failure="response_limit")
            encoding = page_response.getheader("Content-Encoding", "identity").lower()
            content_type = page_response.getheader("Content-Type", "text/html")
            try:
                page_body = raw.decode(page_response.headers.get_content_charset() or "utf8", errors="strict")
            except (UnicodeError, LookupError):
                return WireReply(status=0, failure="response_limit")
            return WireReply(status=page_response.status, body=page_body if page_response.status == 200 else None, content_type=content_type,
                location=page_response.getheader("Location"), robots_tag=page_response.getheader("X-Robots-Tag"),
                encoding="identity" if encoding == "identity" else "unsupported", peer_ip=target.ip)
        except (TimeoutError, socket.timeout):
            return WireReply(status=0, failure="timeout")
        except (OSError, ssl.SSLError, http.client.HTTPException, ValueError):
            return WireReply(status=0, failure="network")
        finally:
            conn.close()


def model_json(response: dict) -> dict:
    try:
        message = response["choices"][0]["message"]["content"]
        value = json.loads(message)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, KeyError, IndexError, TypeError):
        raise PolicyDenied("model_json_invalid") from None
