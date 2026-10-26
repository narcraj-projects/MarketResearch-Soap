"""Exact versioned offline response tapes. No SDK, credential, resolver or live fallback."""
from hashlib import sha256
import json
from threading import Lock
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from .contracts import Versions
from .search import ReplayMismatch


def fingerprint(value) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


class ReplayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    schema_version: Literal["replay-1.0"] = "replay-1.0"
    kind: Literal["search", "model", "tool"]
    operation: str = Field(min_length=1, max_length=200)
    attempt: int = Field(ge=1, le=3, strict=True)
    versions: Versions
    arguments: JsonValue


class ReplayStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    label: Literal["DEMO"] = "DEMO"
    request: ReplayRequest
    raw_response: str = Field(max_length=256000)
    response_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def intact(self):
        if sha256(self.raw_response.encode()).hexdigest() != self.response_hash:
            raise ValueError("replay_response_hash_mismatch")
        return self


class ReplayTape:
    """Independent logical lanes; ordered attempts within each lane, duplicate reads stable."""
    def __init__(self, steps: tuple[ReplayStep, ...]):
        # Frozen Pydantic models are shallow: snapshot canonical arguments rather
        # than retaining caller-owned mutable JSON objects as the expected input.
        validated = tuple(ReplayStep.model_validate(s.model_dump()) for s in steps)
        self.steps = {(s.request.operation, s.request.attempt): (fingerprint(s.request.model_dump(mode="json")), s.raw_response) for s in validated}
        if len(self.steps) != len(steps):
            raise ReplayMismatch("duplicate_replay_step")
        for operation in {s.request.operation for s in validated}:
            ordinals = sorted(s.request.attempt for s in validated if s.request.operation == operation)
            if ordinals != list(range(1, len(ordinals) + 1)):
                raise ReplayMismatch("noncontiguous_replay_steps")
        self.seen: set[tuple[str, int]] = set()
        self.lock = Lock()

    def consume(self, request: ReplayRequest) -> str:
        with self.lock:
            key = request.operation, request.attempt
            step = self.steps.get(key)
            if step is None or fingerprint(request.model_dump(mode="json")) != step[0]:
                raise ReplayMismatch("replay_request_or_version_mismatch")
            if request.attempt > 1 and (request.operation, request.attempt - 1) not in self.seen:
                raise ReplayMismatch("replay_attempt_order_mismatch")
            self.seen.add(key)
            return step[1]

    def assert_finished(self):
        if self.seen != set(self.steps):
            raise ReplayMismatch("missing_replay_operation")
