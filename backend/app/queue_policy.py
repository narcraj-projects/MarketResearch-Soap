"""Owner-scoped durable bounds. No RLS bypass to count another tenant's jobs."""
from dataclasses import dataclass
from hashlib import sha256

from fastapi import HTTPException
from sqlalchemy import func, select, text

from app import models as m


@dataclass(frozen=True)
class QueueLimits:
    outstanding: int = 128
    active: int = 4

    def __post_init__(self):
        if not 1 <= self.active <= self.outstanding <= 128:
            raise ValueError("invalid_queue_limits")


DEFAULT_LIMITS = QueueLimits()


def lock_owner(repo):
    key = int.from_bytes(sha256(f"queue:{repo.owner}".encode()).digest()[:8], "big", signed=True)
    repo.conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def admission(repo, limits=DEFAULT_LIMITS):
    # Serialize count+insert, including requests with different idempotency keys.
    lock_owner(repo)
    # Waiting for an approval reserves its slot too: approval/resume cannot
    # overfill a queue whose apparent free slots are only interrupted jobs.
    count = repo.conn.execute(select(func.count()).select_from(m.runs).where(
        m.runs.c.owner_id == repo.owner,
        m.runs.c.status.not_in(("complete", "cancelled", "partial", "failed")))).scalar_one()
    if count >= limits.outstanding:
        raise HTTPException(429, "queue_capacity", headers={"Retry-After": "60"})


def claim_available(repo, limits=DEFAULT_LIMITS):
    lock_owner(repo)
    count = repo.conn.execute(select(func.count()).select_from(m.jobs).where(
        m.jobs.c.owner_id == repo.owner, m.jobs.c.state == "claimed",
        m.jobs.c.lease_until > func.clock_timestamp())).scalar_one()
    return count < limits.active
