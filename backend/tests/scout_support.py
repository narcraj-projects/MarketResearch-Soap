"""Test-only in-memory accounting; production Scout uses PostgresSearchLedger."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from threading import Lock
from uuid import UUID

from app.harness.contracts import Budget, RunContext, Versions
from app.harness.policy import PolicyDenied

NOW = datetime(2026, 10, 25, tzinfo=timezone.utc)


def versions():
    return Versions(graph="scout-1.0", model="none", provider="none", prompt="deterministic-scout-1.0", tools="tavily-search-1.0", dataset="scout-demo-v1")


def context(**changes):
    return RunContext.model_validate(dict(run_id=UUID(int=1), user_id=UUID(int=2), trace_id=UUID(int=3), brief_version=1, run_version=2,
        phase="discover", deadline=NOW + timedelta(minutes=5), versions=versions(), budget=Budget(max_calls=6, max_tokens=0, max_cost=1)) | changes)


class Clock:
    def __init__(self):
        self.time = NOW
        self.delays = []

    def now(self):
        return self.time

    def sleep(self, delay):
        self.delays.append(delay)
        self.time += timedelta(seconds=delay)


class MemoryLedger:
    def __init__(self):
        self.rows = {}
        self.lock = Lock()

    def reserve(self, context, call, fingerprint, cost, now):
        with self.lock:
            key = (context.run_id, context.user_id, call.operation_id, call.attempt)
            if key in self.rows:
                record = self.rows[key]
                if record["fingerprint"] != fingerprint:
                    raise PolicyDenied("operation_payload_conflict")
                if record["outcome"] is None:
                    raise PolicyDenied("uncertain_attempt")
                return record["outcome"]
            owned = [r for k, r in self.rows.items() if k[:2] == key[:2]]
            if len(owned) + 1 > context.budget.max_calls or sum((r["cost"] for r in owned), Decimal(0)) + cost > context.budget.max_cost:
                raise PolicyDenied("budget")
            self.rows[key] = {"fingerprint": fingerprint, "cost": cost, "outcome": None}
            return None

    def complete(self, context, call, fingerprint, outcome, now):
        with self.lock:
            self.rows[(context.run_id, context.user_id, call.operation_id, call.attempt)]["outcome"] = outcome
