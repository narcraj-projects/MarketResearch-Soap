"""Search transactions. Network operations never hold these database locks."""
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID, uuid4, uuid5

from sqlalchemy import Engine, and_, insert, select, update

from app import models as m
from app.api_schemas import BriefCreate
from app.agents.scout import DiscoveryArtifact, rank
from app.repository import Repository, digest, owner_transaction
from .contracts import Budget, Phase, RunContext, SearchCall, Versions
from .policy import PolicyDenied
from .lease import Lease, require_fence
from .search import AttemptOutcome, SearchSource


class PostgresSearchLedger:
    def __init__(self, engine: Engine, lease: Lease | None = None, *, ranker=rank):
        self.engine, self.lease = engine, lease
        self.ranker = ranker

    @staticmethod
    def locked(repo: Repository, run_id: UUID, lease: Lease | None = None) -> dict:
        row = repo.conn.execute(select(m.runs).where(m.runs.c.id == run_id, m.runs.c.owner_id == repo.owner).with_for_update()).mappings().first()
        if row is None:
            raise PolicyDenied("run_not_found")
        run = dict(row)
        require_fence(repo, run, lease)
        return run

    def begin(self, run_id: UUID, owner_id: UUID, deadline: datetime, versions: Versions) -> tuple[RunContext, BriefCreate]:
        with owner_transaction(self.engine, owner_id) as repo:
            run = self.locked(repo, run_id, self.lease)
            brief_row = repo.get(m.briefs, run["brief_id"])
            brief = BriefCreate.model_validate({key: brief_row[key] for key in BriefCreate.model_fields})
            if run["status"] != "queued":
                raise PolicyDenied("run_not_discovering")
            checkpoint = run["checkpoint"]
            if checkpoint is None:
                checkpoint = {"schema_version": "scout-1.0", "versions": versions.model_dump(mode="json"), "deadline": deadline.isoformat(),
                    "trace_id": str(uuid4()), "stage": "discover", "brief_hash": digest(brief.model_dump(mode="json")), "completed_operations": []}
                repo.conn.execute(update(m.runs).where(m.runs.c.id == run_id).values(checkpoint=checkpoint, version=run["version"] + 1))
                run["version"] += 1
                repo.event(run_id, "scout.started", {"agent": "scout", "label": "DEMO", "graph": versions.graph})
            if checkpoint.get("schema_version") != "scout-1.0" or checkpoint.get("versions") != versions.model_dump(mode="json") or checkpoint.get("brief_hash") != digest(brief.model_dump(mode="json")):
                raise PolicyDenied("checkpoint_version_mismatch")
            attempts = repo.conn.execute(select(m.tool_attempts).where(m.tool_attempts.c.run_id == run_id, m.tool_attempts.c.owner_id == owner_id)).mappings().all()
            usage = repo.conn.execute(select(m.usage).where(m.usage.c.run_id == run_id, m.usage.c.owner_id == owner_id)).mappings().all()
            keys = {(a["operation_id"], a["attempt"]) for a in attempts}
            other_usage = [u for u in usage if (u["operation_id"], u["attempt"]) not in keys]
            completed = [a for a in attempts if a["state"] == "completed"]
            reserved = [a for a in attempts if a["state"] == "reserved"]
            context = RunContext(mode="live" if versions.dataset.startswith("live-") else "replay", live_authorization_id=uuid5(run_id, "live-permit-1.0") if versions.dataset.startswith("live-") else None,
                run_id=run_id, user_id=owner_id, trace_id=checkpoint["trace_id"], brief_version=brief_row["version"], run_version=run["version"],
                versions=versions, phase=Phase.DISCOVER, deadline=datetime.fromisoformat(checkpoint["deadline"]),
                budget=Budget(max_calls=run["budget"]["max_calls"], max_tokens=run["budget"]["max_tokens"], max_cost=run["budget"]["max_cost_usd"],
                    used_calls=len(completed) + sum(u["calls"] for u in other_usage), reserved_calls=len(reserved), used_tokens=sum(u["tokens"] for u in usage),
                    used_cost=sum((a["cost_upper_bound_usd"] for a in completed), Decimal(0)) + sum((u["cost_usd"] for u in other_usage), Decimal(0)),
                    reserved_cost=sum((a["cost_upper_bound_usd"] for a in reserved), Decimal(0))))
            return context, brief

    def check_context(self, repo: Repository, context: RunContext, now: datetime, *, completion: bool = False) -> dict:
        run = self.locked(repo, context.run_id, self.lease)
        checkpoint = run["checkpoint"] or {}
        if run["status"] != "queued" or run["version"] != context.run_version or checkpoint.get("stage") != "discover":
            raise PolicyDenied("stale_run_or_gate")
        if checkpoint.get("versions") != context.versions.model_dump(mode="json") or checkpoint.get("deadline") != context.deadline.isoformat():
            raise PolicyDenied("context_mismatch")
        if not completion and now >= context.deadline:
            raise PolicyDenied("deadline")
        return run

    def reserve(self, context: RunContext, call: SearchCall, fingerprint: str, cost: Decimal, now: datetime) -> AttemptOutcome | None:
        with owner_transaction(self.engine, context.user_id) as repo:
            run = self.check_context(repo, context, now)
            attempts = repo.conn.execute(select(m.tool_attempts).where(m.tool_attempts.c.run_id == context.run_id,
                m.tool_attempts.c.owner_id == context.user_id)).mappings().all()
            for prior in attempts:
                if prior["operation_id"] == call.operation_id and prior["attempt"] == call.attempt:
                    if prior["request_hash"] != fingerprint:
                        raise PolicyDenied("operation_payload_conflict")
                    if prior["state"] == "reserved":
                        raise PolicyDenied("uncertain_attempt")
                    return AttemptOutcome.model_validate(prior["outcome"])
            # Count other tool/model usage too, without double-counting journaled search attempts.
            usage = repo.conn.execute(select(m.usage).where(m.usage.c.run_id == context.run_id, m.usage.c.owner_id == context.user_id)).mappings().all()
            attempted = {(a["operation_id"], a["attempt"]) for a in attempts}
            other_usage = [u for u in usage if (u["operation_id"], u["attempt"]) not in attempted]
            total_calls = len(attempts) + sum(u["calls"] for u in other_usage)
            total_cost = sum((a["cost_upper_bound_usd"] for a in attempts), Decimal(0)) + sum((u["cost_usd"] for u in other_usage), Decimal(0))
            if context.mode == "live":
                from .live_policy import load_permit, enforce_credit_cap
                permit = load_permit(context.run_id, context.user_id)
                enforce_credit_cap(attempts, permit, cost)
            # All reservations, including uncertain failures, retain their upper bound.
            if (total_calls + 1 > run["budget"]["max_calls"] or total_cost + cost > Decimal(run["budget"]["max_cost_usd"])
                or sum(u["tokens"] for u in usage) > run["budget"]["max_tokens"]):
                raise PolicyDenied("budget")
            repo.conn.execute(insert(m.tool_attempts).values(id=uuid5(context.run_id, f"search:{call.operation_id}:{call.attempt}"),
                owner_id=context.user_id, run_id=context.run_id, operation_id=call.operation_id, attempt=call.attempt,
                request_hash=fingerprint, cost_upper_bound_usd=cost, state="reserved", outcome=None))
            repo.event(context.run_id, "tool.reserved", {"operation_id": str(call.operation_id), "attempt": call.attempt, "agent": "scout", "tool": call.tool,
                "accounting": "DEMO_conservative_reservation", "cost_upper_bound_usd": str(cost)})
            return None

    def complete(self, context: RunContext, call: SearchCall, fingerprint: str, outcome: AttemptOutcome, now: datetime) -> None:
        outcome = AttemptOutcome.model_validate(outcome.model_dump())
        with owner_transaction(self.engine, context.user_id) as repo:
            run = self.check_context(repo, context, now, completion=True)
            where = and_(m.tool_attempts.c.run_id == context.run_id, m.tool_attempts.c.owner_id == context.user_id,
                m.tool_attempts.c.operation_id == call.operation_id, m.tool_attempts.c.attempt == call.attempt)
            attempt = repo.conn.execute(select(m.tool_attempts).where(where)).mappings().one()
            if attempt["request_hash"] != fingerprint or attempt["state"] != "reserved":
                raise PolicyDenied("stale_attempt")
            if outcome.payload:
                for source in outcome.payload.sources:
                    if source.content_hash != sha256(source.excerpt.encode()).hexdigest():
                        raise PolicyDenied("source_hash_mismatch")
                    repo.conn.execute(insert(m.sources).values(id=source.source_id, owner_id=context.user_id, run_id=context.run_id,
                        canonical_url=source.canonical_url, title=source.title, publisher=source.publisher, retrieved_at=source.retrieved_at,
                        content_hash=source.content_hash, access_status=source.access_status, excerpt=source.excerpt, evidence_kind=source.evidence_kind))
            repo.create(m.usage, {"run_id": context.run_id, "operation_id": call.operation_id, "attempt": call.attempt, "calls": 1, "tokens": 0,
                "cost_usd": attempt["cost_upper_bound_usd"]})
            repo.conn.execute(update(m.tool_attempts).where(where).values(state="completed", outcome=outcome.model_dump(mode="json")))
            checkpoint = dict(run["checkpoint"])
            checkpoint["completed_attempts"] = sorted(set(checkpoint.get("completed_attempts", [])) | {f"{call.operation_id}:{call.attempt}"})
            if outcome.status == "ok" or not outcome.retryable or call.attempt == 3:
                checkpoint["completed_operations"] = sorted(set(checkpoint["completed_operations"]) | {str(call.operation_id)})
            repo.conn.execute(update(m.runs).where(m.runs.c.id == context.run_id).values(checkpoint=checkpoint))
            repo.event(context.run_id, "tool.completed", {"agent": "scout", "tool": call.tool, "operation_id": str(call.operation_id),
                "attempt": call.attempt, "outcome": outcome.status, "source_count": len(outcome.payload.sources) if outcome.payload else 0})
            if outcome.retryable:
                repo.event(context.run_id, "tool.retryable_failure", {"tool": call.tool, "agent": "scout", "attempt": call.attempt, "code": outcome.status,
                    "retry_limit": 3, "operation_id": str(call.operation_id), "label": "DEMO"})
            if outcome.status == "ok" and call.attempt > 1:
                repo.event(context.run_id, "tool.recovered", {"tool": call.tool, "agent": "scout", "attempt": call.attempt, "operation_id": str(call.operation_id), "label": "DEMO"})

    def finish(self, context: RunContext, brief: BriefCreate, *, stop_reason: str | None = None) -> dict:
        with owner_transaction(self.engine, context.user_id) as repo:
            run = self.locked(repo, context.run_id, self.lease)
            if run["status"] != "queued":
                return self.snapshot(repo, context.run_id)
            self.check_context(repo, context, context.deadline, completion=True)
            attempts = repo.list(m.tool_attempts, context.run_id, limit=1000)
            if any(a["state"] == "reserved" for a in attempts):
                raise PolicyDenied("uncertain_attempt")  # Do not turn in-flight work into an approvable artifact.
            sources: list[SearchSource] = []
            for row in attempts:
                if row["outcome"].get("schema_version") == "model-live-1.0":
                    continue
                result = AttemptOutcome.model_validate(row["outcome"])
                if result.payload:
                    sources.extend(result.payload.sources)
            # Recompute from trusted journal and persisted brief, never accept a proposed/model candidate pool.
            persisted = repo.get(m.briefs, run["brief_id"])
            authoritative_brief = BriefCreate.model_validate({key: persisted[key] for key in BriefCreate.model_fields})
            if authoritative_brief != brief:
                raise PolicyDenied("brief_changed")
            discovery = self.ranker(authoritative_brief, context.run_id, tuple(sources))
            for candidate in discovery.candidates:
                repo.conn.execute(insert(m.competitors).values(id=candidate.candidate_id, owner_id=context.user_id, run_id=context.run_id,
                    name=candidate.name, canonical_url=candidate.canonical_url))
            artifact = DiscoveryArtifact(label=discovery.label, discovery=discovery, competitor_ids=tuple(c.candidate_id for c in discovery.candidates),
                insufficiency_reason=discovery.insufficiency_reason, stop_reason=stop_reason).model_dump(mode="json")
            checkpoint = dict(run["checkpoint"]) | {"artifact": artifact, "artifact_hash": digest(artifact), "artifact_version": 1}
            if discovery.candidates:
                pending = repo.create(m.approval_requests, {"run_id": context.run_id, "gate": "shortlist", "artifact_version": 1,
                    "artifact_hash": digest(artifact), "state": "pending", "artifact": artifact})
                checkpoint |= {"stage": "shortlist_review", "request_id": str(pending["id"])}
                status = "shortlist_review"
                repo.event(context.run_id, "approval.pending", {"gate": "shortlist", "request_id": str(pending["id"]), "artifact_hash": digest(artifact)})
            else:
                checkpoint |= {"stage": "clarification_required", "request_id": None}
                status = "partial"
                repo.event(context.run_id, "scout.insufficient", {"code": stop_reason or "no_credible_candidates"})
            repo.conn.execute(update(m.runs).where(m.runs.c.id == context.run_id).values(status=status, version=run["version"] + 1,
                checkpoint=checkpoint, failure_code=stop_reason))
            if self.lease is None:
                repo.conn.execute(update(m.jobs).where(m.jobs.c.run_id == context.run_id, m.jobs.c.owner_id == context.user_id).values(state="done"))
            return self.snapshot(repo, context.run_id)

    @staticmethod
    def snapshot(repo: Repository, run_id: UUID) -> dict:
        run = repo.get(m.runs, run_id)
        checkpoint = run["checkpoint"] or {}
        if checkpoint.get("schema_version") != "scout-1.0" or "artifact" not in checkpoint:
            raise PolicyDenied("shortlist_not_ready")
        return {"run_id": run_id, "run_version": run["version"], "status": run["status"], "request_id": checkpoint.get("request_id"),
            "artifact_hash": checkpoint["artifact_hash"], "artifact_version": checkpoint["artifact_version"], "artifact": checkpoint["artifact"]}
