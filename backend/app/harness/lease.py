"""Database-clock leases. All managed writes lock run then job and verify the fence."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, update

from app import models as m
from app.repository import Repository, owner_transaction
from app.queue_policy import claim_available, DEFAULT_LIMITS
from .policy import PolicyDenied


@dataclass(frozen=True)
class Lease:
    run_id: UUID
    owner_id: UUID
    worker_id: UUID
    generation: int

    def guard(self, repo: Repository, run: dict | None = None) -> dict:
        if repo.owner != self.owner_id:
            raise PolicyDenied("lease_owner_mismatch")
        if run is None:
            row = repo.conn.execute(select(m.runs).where(m.runs.c.id == self.run_id,
                m.runs.c.owner_id == repo.owner).with_for_update()).mappings().first()
            if row is None:
                raise PolicyDenied("run_not_found")
            run = dict(row)
        job = repo.conn.execute(select(m.jobs).where(m.jobs.c.run_id == self.run_id,
            m.jobs.c.owner_id == repo.owner).with_for_update()).mappings().one()
        now = repo.conn.execute(select(func.clock_timestamp())).scalar_one()
        if (run["id"] != self.run_id or run["status"] == "cancelled" or not job["managed"]
            or job["state"] != "claimed" or job["worker_id"] != self.worker_id
            or job["generation"] != self.generation or job["lease_until"] is None or now >= job["lease_until"]):
            raise PolicyDenied("lease_lost_or_cancelled")
        return run

    def check(self, engine) -> None:
        with owner_transaction(engine, self.owner_id) as repo:
            self.guard(repo)


def require_fence(repo: Repository, run: dict, lease: Lease | None) -> None:
    job = repo.conn.execute(select(m.jobs).where(m.jobs.c.run_id == run["id"], m.jobs.c.owner_id == repo.owner)).mappings().first()
    if job and job["managed"]:
        if lease is None:
            raise PolicyDenied("worker_lease_required")
        lease.guard(repo, run)


class JobQueue:
    """Workers are explicitly scoped to an authenticated owner; no bypass-RLS queue role."""
    def __init__(self, engine, owner_id: UUID, *, limits=DEFAULT_LIMITS):
        self.engine, self.owner = engine, owner_id
        self.limits = limits

    def claim(self, worker_id: UUID, seconds: int = 30, run_id: UUID | None = None) -> Lease | None:
        if not 2 <= seconds <= 300:
            raise ValueError("lease_seconds")
        with owner_transaction(self.engine, self.owner) as repo:
            if not claim_available(repo, self.limits):
                return None
            query = select(m.runs).join(m.jobs, m.jobs.c.run_id == m.runs.c.id).where(
                m.runs.c.owner_id == self.owner, m.jobs.c.managed,
                m.runs.c.status.not_in(("cancelled", "failed", "partial")),
                (m.jobs.c.state == "queued") | ((m.jobs.c.state == "claimed") & (m.jobs.c.lease_until <= func.clock_timestamp()))
            ).order_by(m.jobs.c.created_at).with_for_update(of=m.runs, skip_locked=True).limit(1)
            if run_id is not None:
                query = query.where(m.runs.c.id == run_id)
            candidates = repo.conn.execute(query).mappings().first()
            if candidates is None:
                return None
            job = repo.conn.execute(select(m.jobs).where(m.jobs.c.run_id == candidates["id"],
                m.jobs.c.owner_id == self.owner).with_for_update()).mappings().one()
            generation = job["generation"] + 1
            repo.conn.execute(update(m.jobs).where(m.jobs.c.id == job["id"]).values(state="claimed", worker_id=worker_id,
                generation=generation, heartbeat_at=func.clock_timestamp(), lease_until=func.clock_timestamp() + timedelta(seconds=seconds)))
            repo.event(candidates["id"], "worker.claimed", {"generation": generation, "recovered": job["state"] == "claimed"})
            return Lease(candidates["id"], self.owner, worker_id, generation)

    def heartbeat(self, lease: Lease, seconds: int = 30) -> None:
        if not 2 <= seconds <= 300:
            raise ValueError("lease_seconds")
        with owner_transaction(self.engine, self.owner) as repo:
            lease.guard(repo)
            repo.conn.execute(update(m.jobs).where(m.jobs.c.run_id == lease.run_id, m.jobs.c.owner_id == self.owner).values(
                heartbeat_at=func.clock_timestamp(), lease_until=func.clock_timestamp() + timedelta(seconds=seconds)))

    def release(self, lease: Lease, *, done: bool = True, failure: str | None = None, waiting_request: UUID | None = None) -> None:
        with owner_transaction(self.engine, self.owner) as repo:
            run = lease.guard(repo)
            if waiting_request:
                decided = repo.conn.execute(select(m.approval_decisions.c.id).where(m.approval_decisions.c.request_id == waiting_request,
                    m.approval_decisions.c.run_id == lease.run_id, m.approval_decisions.c.owner_id == self.owner)).first()
                if decided:
                    done = False
            if failure:
                repo.conn.execute(update(m.runs).where(m.runs.c.id == lease.run_id).values(status="partial", failure_code=failure, version=run["version"] + 1))
                repo.conn.execute(update(m.approval_requests).where(m.approval_requests.c.run_id == lease.run_id,
                    m.approval_requests.c.owner_id == self.owner, m.approval_requests.c.state == "pending").values(state="superseded"))
                repo.event(lease.run_id, "workflow.stopped", {"code": failure})
            repo.conn.execute(update(m.jobs).where(m.jobs.c.run_id == lease.run_id, m.jobs.c.owner_id == self.owner).values(
                state="done" if done else "queued", worker_id=None, lease_until=None))

    def deadline(self, run_id: UUID) -> datetime:
        with owner_transaction(self.engine, self.owner) as repo:
            repo.get(m.runs, run_id)
            return repo.conn.execute(select(m.jobs.c.deadline).where(m.jobs.c.run_id == run_id, m.jobs.c.owner_id == self.owner)).scalar_one()
