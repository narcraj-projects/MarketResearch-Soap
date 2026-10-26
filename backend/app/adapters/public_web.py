"""Recorded public HTTP boundary. No enabled external transport or DNS fallback."""
from collections.abc import Callable
import http.client
import json
from pathlib import Path
from hashlib import sha256
import socket
import ssl
from threading import Lock

from app.harness.policy import PolicyDenied
from app.harness.research_types import WireReply
from app.harness.search import ReplayMismatch
from app.harness.web_policy import Destination, public_ip, verify_peer


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Native pinning primitive; not wired to any enabled live adapter factory."""
    def __init__(self, target: Destination, timeout: float):
        self.tls_context = ssl.create_default_context()
        super().__init__(target.hostname, port=target.port, timeout=timeout, context=self.tls_context)
        self.target = target

    def connect(self):
        # Connect to the validated IP, never resolve hostname again. TLS keeps original SNI/verification.
        raw = socket.create_connection((public_ip(self.target.ip), self.target.port), timeout=self.timeout)
        try:
            verify_peer(self.target, raw.getpeername()[0])
            self.sock = self.tls_context.wrap_socket(raw, server_hostname=self.target.hostname)
            verify_peer(self.target, self.sock.getpeername()[0])
        except BaseException:
            raw.close()
            if self.sock:
                self.sock.close()
            raise


class RecordedWeb:
    def __init__(self, path: Path, before_request: Callable[[str], None] | None = None):
        manifest = json.loads((path.parent / "manifest.json").read_text())
        raw = path.read_bytes()
        if manifest["sha256"].get(path.name) != sha256(raw).hexdigest():
            raise ReplayMismatch("research_recording_hash_mismatch")
        self.case = json.loads(raw)
        if self.case.get("label") != "DEMO" or self.case.get("dataset_version") != "research-demo-v1" or self.case.get("schema_version") != "research-1.0":
            raise ReplayMismatch("research_recording_version_mismatch")
        self.lock = Lock()
        self.cursors: dict[str, int] = {}
        self.dns_cursors: dict[str, int] = {}
        self.requests: list[str] = []
        self.before_request = before_request
        self.resolved_operations: set[tuple[str, int]] = set()

    def resolve(self, host: str, *, operation_id: str | None = None, attempt: int = 1) -> tuple[str, ...]:
        with self.lock:
            answers = self.case["dns"].get(host)
            if answers is None:
                raise PolicyDenied("unrecorded_dns")
            ordinal = self.dns_cursors.get(host, 0)
            self.dns_cursors[host] = ordinal + 1
            if operation_id is not None:
                self.resolved_operations.add((operation_id, attempt))
            return tuple(answers[min(ordinal, len(answers) - 1)])

    def observe_cached(self, host: str, operation_id: str, attempt: int) -> None:
        with self.lock:
            key = operation_id, attempt
            if key not in self.resolved_operations:
                self.resolved_operations.add(key)
                self.dns_cursors[host] = self.dns_cursors.get(host, 0) + 1

    def exchange(self, target: Destination, *, method: str, query: dict | None, timeout: float, attempt: int | None = None) -> WireReply:
        key = method + " " + target.url
        if query is not None:
            key += " " + sha256(json.dumps(query, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        with self.lock:
            sequence = self.case["responses"].get(key)
            ordinal = attempt - 1 if attempt is not None else self.cursors.get(key, 0)
            if sequence is None or ordinal >= len(sequence):
                raise ReplayMismatch("unrecorded_http_request")
            item = sequence[ordinal]
            if item.get("query") != query:
                raise ReplayMismatch("research_arguments_mismatch")
            self.cursors[key] = ordinal + 1
            self.requests.append(key)
        if self.before_request:
            self.before_request(key)
        reply = dict(item["reply"])
        reply.setdefault("peer_ip", target.ip)
        if reply.get("body") is not None and len(reply["body"].encode()) > 256000:
            reply = {"status": 0, "failure": "response_limit"}
        return WireReply.model_validate(reply)
