"""Exact in-process DEMO HTTP replay, with no network fallback."""
from hashlib import sha256
import json
from pathlib import Path

import httpx

from .search import ReplayMismatch


class RecordedTavily:
    def __init__(self, case_path: Path):
        manifest = json.loads((case_path.parent / "manifest.json").read_text(encoding="utf8"))
        raw = case_path.read_bytes()
        if manifest["sha256"].get(case_path.name) != sha256(raw).hexdigest():
            raise ReplayMismatch("recording_hash_mismatch")
        self.case = json.loads(raw)
        if (self.case.get("label") != "DEMO" or self.case.get("dataset_version") != "scout-demo-v1"
            or self.case.get("schema_version") != "1.0" or self.case.get("tools_version") != "tavily-search-1.0"
            or self.case.get("scorer_version") != "soap-scout-1.0"):
            raise ReplayMismatch("recording_version_mismatch")
        self.ordinal = 0
        self.dispatched: set[int] = set()
        self.consumed: set[int] = set()
        self.transport = httpx.MockTransport(self._handle)
        setattr(self.transport, "_lather_replay_cached", self._cached)

    def _index(self, payload: dict, attempt: int) -> int:
        matching = [i for i, step in enumerate(self.case["steps"]) if step["request"] == payload]
        if not matching:
            raise ReplayMismatch("request_mismatch")
        if attempt <= 0 or attempt > len(matching):
            raise ReplayMismatch("extra_operation")
        return matching[attempt - 1]

    def _cached(self, payload: dict, attempt: int):
        index = self._index(payload, attempt)
        if any(i not in self.consumed for i in range(index)):
            raise ReplayMismatch("request_order_mismatch")
        self.consumed.add(index)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        attempt = request.extensions.get("lather_replay_attempt", self.ordinal + 1)
        if isinstance(attempt, bool) or not isinstance(attempt, int):
            raise ReplayMismatch("recording_attempt_mismatch")
        payload = json.loads(request.content)
        if "lather_replay_attempt" in request.extensions:
            index = self._index(payload, attempt)
        else:
            index = attempt - 1
        if index < 0 or index >= len(self.case["steps"]):
            raise ReplayMismatch("extra_operation")
        step = self.case["steps"][index]
        if index in self.dispatched:
            raise ReplayMismatch("extra_operation")
        if any(i not in self.consumed for i in range(index)):
            raise ReplayMismatch("request_order_mismatch")
        if request.method != "POST" or str(request.url) != "https://api.tavily.com/search" or payload != step["request"]:
            raise ReplayMismatch("request_mismatch")
        self.ordinal += 1
        self.dispatched.add(index)
        self.consumed.add(index)
        if step.get("fault") == "timeout":
            raise httpx.ReadTimeout("DEMO timeout", request=request)
        return httpx.Response(step["status"], headers=step.get("headers", {}), json=step.get("response", {}))

    def assert_finished(self) -> None:
        if self.consumed != set(range(len(self.case["steps"]))):
            raise ReplayMismatch("missing_operation")
