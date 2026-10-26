"""The sole Scout tool dispatcher: validate, authorize, reserve, bounded dispatch, journal."""
from collections.abc import Callable
from datetime import datetime, timezone
from hashlib import sha256
import json
import random
import time
from uuid import uuid5

from pydantic import TypeAdapter

from app.adapters.tavily import ADAPTER_VERSION, TavilyAdapter, _GATEWAY_PERMIT
from .contracts import Phase, Role, RunContext, SearchCall, ToolCall, ToolResult, Usage
from .policy import PolicyDenied, authorize_access
from .search import AttemptOutcome, SearchCost, SearchExecution, SearchLedger


class SearchGateway:
    def preflight(self, context: RunContext) -> None:
        self.adapter.ensure_offline()

    def __init__(self, adapter: TavilyAdapter, ledger: SearchLedger, cost: SearchCost,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc), sleep: Callable[[float], None] = time.sleep,
                 jitter: Callable[[], float] | None = None, guard: Callable[[], None] = lambda: None):
        self.adapter, self.ledger, self.cost = adapter, ledger, cost
        self.clock, self.sleep = clock, sleep
        self.jitter = jitter or random.Random(0).random
        self.guard = guard

    def execute(self, context: RunContext, call: ToolCall) -> SearchExecution:
        context = RunContext.model_validate(context.model_dump())
        validated = TypeAdapter(ToolCall).validate_python(call.model_dump())
        if not isinstance(validated, SearchCall) or validated.attempt != 1 or validated.agent != Role.SCOUT or context.phase != Phase.DISCOVER:
            raise PolicyDenied("search_gateway_only_initial_attempt")
        if context.versions.tools != ADAPTER_VERSION:
            raise PolicyDenied("tool_version_mismatch")
        self.preflight(context)  # Fail before budget reservation; live dispatch requires a separate scoped permit.
        if self.cost.per_attempt_upper_bound_usd is None:
            raise PolicyDenied("unknown_cost")
        outcome: AttemptOutcome | None = None
        stop = "exhausted"
        last_attempt = 0
        for attempt in range(1, 4):
            current = SearchCall.model_validate(validated.model_dump() | {"attempt": attempt})
            authorize_access(context, current, self.clock())
            fingerprint = sha256(json.dumps({"call": current.model_dump(mode="json"), "versions": context.versions.model_dump(mode="json"),
                "pricing": self.cost.model_dump(mode="json")}, sort_keys=True).encode()).hexdigest()
            try:
                cached = self.ledger.reserve(context, current, fingerprint, self.cost.per_attempt_upper_bound_usd, self.clock())
            except PolicyDenied as error:
                if str(error) not in {"budget", "deadline", "uncertain_attempt"} or outcome is None:
                    raise
                stop = str(error)
                break
            outcome = cached
            if cached is not None:
                self.adapter.observe_cached(current)
            if outcome is None:
                seconds = min(current.timeout_seconds, (context.deadline - self.clock()).total_seconds())
                if seconds <= 0:
                    outcome = AttemptOutcome(status="timeout")
                else:
                    self.guard()
                    outcome = self.adapter._dispatch(context, current, seconds, self.clock(), permit=_GATEWAY_PERMIT)
                outcome = AttemptOutcome.model_validate(outcome.model_dump())
                self.ledger.complete(context, current, fingerprint, outcome, self.clock())
            last_attempt = attempt
            if outcome.status == "ok" or not outcome.retryable:
                stop = "complete"
                break
            if attempt < 3:
                delay = max(outcome.retry_after_seconds or 0, 0.5 * 2 ** (attempt - 1) + self.jitter() * 0.25)
                if self.clock().timestamp() + delay >= context.deadline.timestamp():
                    stop = "deadline"
                    break
                self.sleep(delay)
        assert outcome is not None
        codes = {"timeout": "timeout", "rate_limited": "429", "denied": "access_denied", "unavailable": "missing", "invalid": "schema_invalid"}
        result = ToolResult.model_validate(dict(operation_id=validated.operation_id, attempt=last_attempt, status=outcome.status,
            payload_ref=uuid5(context.run_id, f"search:{validated.operation_id}:{last_attempt}") if outcome.status == "ok" else None,
            error_code=codes.get(outcome.status), usage=Usage(calls=last_attempt, tokens=0, cost=last_attempt * self.cost.per_attempt_upper_bound_usd)))
        # Accounting is per durable attempt row, never an invented provider-billing total.
        return SearchExecution.model_validate(dict(result=result, payload=outcome.payload, stop_reason=stop))
