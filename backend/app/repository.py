"""Owner filters plus transaction-local RLS identity and transactional commands."""
from contextlib import contextmanager
from datetime import timedelta
from hashlib import sha256
import json
from typing import Any
from uuid import UUID, uuid4, uuid5

from fastapi import HTTPException
from sqlalchemy import Engine, String, and_, cast, func, insert, select, text, update
from sqlalchemy.engine import Connection

from app import models as m
from app.api_schemas import DecisionCreate, RunCreate
from app.queue_policy import admission


def digest(data: Any) -> str:
    return sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@contextmanager
def owner_transaction(engine: Engine, owner: UUID):
    with engine.begin() as conn:
        privileged = conn.execute(text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")).scalar_one()
        if privileged:
            raise RuntimeError("runtime_role_must_not_bypass_rls")
        conn.execute(text("SET LOCAL ROLE lather_api"))
        conn.execute(text("SELECT set_config('request.jwt.claim.sub', :owner, true)"), {"owner": str(owner)})
        conn.execute(text("SELECT set_config('request.jwt.claims', :claims, true)"), {"claims": json.dumps({"sub": str(owner), "role": "authenticated"})})
        yield Repository(conn, owner)


class Repository:
    def __init__(self, conn: Connection, owner: UUID):
        self.conn = conn
        self.owner = owner

    def get(self, table, identifier: UUID) -> dict:
        row = self.conn.execute(select(table).where(table.c.id == identifier, table.c.owner_id == self.owner)).mappings().first()
        if row is None:
            raise HTTPException(404, "not_found")
        return dict(row)

    def create(self, table, values: dict) -> dict:
        return dict(self.conn.execute(insert(table).values(id=uuid4(), owner_id=self.owner, **values).returning(table)).mappings().one())

    def list(self, table, run_id: UUID | None = None, limit: int = 50, after: int = 0, offset: int = 0) -> list[dict]:
        query = select(table).where(table.c.owner_id == self.owner)
        if run_id is not None:
            self.get(m.runs, run_id)
            query = query.where(table.c.run_id == run_id)
        if table is m.events:
            query = query.where(table.c.sequence > after).order_by(table.c.sequence)
        else:
            query = query.order_by(table.c.created_at, table.c.id)
        return [dict(row) for row in self.conn.execute(query.limit(limit).offset(offset)).mappings()]

    def event(self, run_id: UUID, kind: str, data: dict) -> None:
        # Every caller holds the run row lock (or owns the new uncommitted run).
        sequence = self.conn.execute(select(func.coalesce(func.max(m.events.c.sequence), 0) + 1).where(m.events.c.run_id == run_id)).scalar_one()
        self.create(m.events, {"run_id": run_id, "sequence": sequence, "kind": kind, "data": data | {"schema_version": "1.0"}})

    def report(self, run_id: UUID) -> dict:
        run = self.get(m.runs, run_id)
        query = select(m.reports).where(m.reports.c.owner_id == self.owner, m.reports.c.run_id == run_id)
        if run["status"] == "complete":
            query = query.join(m.approval_requests, and_(m.approval_requests.c.owner_id == self.owner,
                m.approval_requests.c.run_id == run_id, m.approval_requests.c.gate == "report",
                m.approval_requests.c.artifact["report_id"].astext == cast(m.reports.c.id, String))).join(m.approval_decisions,
                and_(m.approval_decisions.c.request_id == m.approval_requests.c.id,
                     m.approval_decisions.c.owner_id == self.owner, m.approval_decisions.c.decision == "approve"))
        row = self.conn.execute(query.order_by(m.reports.c.version.desc()).limit(1)).mappings().first()
        if row is None:
            raise HTTPException(404, "not_found")
        report = dict(row)
        if report["data"].get("schema_version") == "analysis-report-1.0" and digest(report["data"]) != report["content_hash"]:
            raise HTTPException(409, "report_integrity_error")
        receipt = self.conn.execute(select(m.evaluation_results.c.data).where(m.evaluation_results.c.run_id == run_id,
            m.evaluation_results.c.owner_id == self.owner, m.evaluation_results.c.id == uuid5(report["id"], "analysis.review:1.0"))).scalar_one_or_none()
        if receipt and receipt["report_hash"] == report["content_hash"]:
            report["review"] = receipt["assessment"]
        return report

    def idempotent(self, operation: str, key: str, payload: dict, command) -> dict:
        key_hash = digest(key)
        lock = int.from_bytes(sha256(f"{self.owner}:{operation}:{key_hash}".encode()).digest()[:8], "big", signed=True)
        self.conn.execute(text("SELECT pg_advisory_xact_lock(:lock)"), {"lock": lock})
        where = and_(m.idempotency.c.owner_id == self.owner, m.idempotency.c.operation == operation, m.idempotency.c.key_hash == key_hash)
        previous = self.conn.execute(select(m.idempotency).where(where)).mappings().first()
        if previous:
            if previous["request_hash"] != digest(payload):
                raise HTTPException(409, "idempotency_payload_conflict")
            return previous["response"]
        response = command()
        serializable = json.loads(json.dumps(response, default=str))
        self.create(m.idempotency, {"operation": operation, "key_hash": key_hash, "request_hash": digest(payload), "response": serializable})
        return serializable

    def start(self, body: RunCreate, key: str) -> dict:
        def command():
            self.get(m.briefs, body.brief_id)
            admission(self)
            run = self.create(m.runs, {"brief_id": body.brief_id, "status": "queued", "version": 1, "budget": body.budget.model_dump(mode="json")})
            self.create(m.jobs, {"run_id": run["id"], "state": "queued"})
            self.event(run["id"], "run.queued", {})
            return run
        return self.idempotent("start", key, body.model_dump(mode="json"), command)

    def decide(self, run_id: UUID, gate: str, body: DecisionCreate, key: str) -> dict:
        def command():
            run = self.conn.execute(select(m.runs).where(m.runs.c.id == run_id, m.runs.c.owner_id == self.owner).with_for_update()).mappings().first()
            if run is None:
                raise HTTPException(404, "not_found")
            pending = self.get(m.approval_requests, body.request_id)
            if pending["run_id"] != run_id:
                raise HTTPException(404, "not_found")
            if (pending["gate"] != gate or pending["state"] != "pending" or pending["artifact_version"] != body.artifact_version
                or pending["artifact_hash"] != body.artifact_hash or run["version"] != body.expected_run_version
                or run["status"] != {"shortlist": "shortlist_review", "report": "report_review"}[gate]):
                raise HTTPException(409, "stale_approval")
            if gate == "shortlist" and body.decision == "approve":
                if pending["artifact"].get("schema_version") == "scout-1.0" and digest(pending["artifact"]) != pending["artifact_hash"]:
                    raise HTTPException(409, "shortlist_integrity_error")
                candidates = pending["artifact"].get("competitor_ids", [])
                if not 1 <= len(candidates) <= 3 or len(set(candidates)) != len(candidates):
                    raise HTTPException(409, "invalid_shortlist")
                if len(candidates) < 3 and not pending["artifact"].get("insufficiency_reason"):
                    raise HTTPException(409, "shortlist_insufficiency_reason_required")
                for candidate in candidates:
                    if self.get(m.competitors, UUID(candidate))["run_id"] != run_id:
                        raise HTTPException(409, "invalid_shortlist")
            if gate == "report":
                report_id = pending["artifact"].get("report_id")
                if report_id is None:
                    raise HTTPException(409, "report_missing")
                report = self.get(m.reports, UUID(report_id))
                if report["run_id"] != run_id or report["version"] != body.artifact_version or report["content_hash"] != body.artifact_hash:
                    raise HTTPException(409, "stale_report")
                if body.decision == "approve" and report["data"].get("schema_version") == "analysis-report-1.0":
                    from app.reporting import ready_receipt
                    if digest(report["data"]) != report["content_hash"]:
                        raise HTTPException(409, "report_integrity_error")
                    receipt = ready_receipt(self, report)
                    if receipt is None or receipt.decision != "ready_for_human":
                        raise HTTPException(409, "independent_review_required")
            decision = self.create(m.approval_decisions, {"run_id": run_id, "request_id": body.request_id, "decision": body.decision,
                "artifact_version": body.artifact_version, "artifact_hash": body.artifact_hash})
            job = self.conn.execute(select(m.jobs).where(m.jobs.c.run_id == run_id, m.jobs.c.owner_id == self.owner).with_for_update()).mappings().one()
            managed = job["managed"]
            next_state = ("researching" if gate == "shortlist" else "complete") if body.decision == "approve" else "partial"
            if managed:
                next_state = "researching" if gate == "shortlist" and body.decision == "approve" else run["status"]
                # A decision can race the worker's interrupt checkpoint. Never steal
                # its lease; release() reconciles the persisted decision atomically.
                if job["state"] != "claimed":
                    self.conn.execute(update(m.jobs).where(m.jobs.c.id == job["id"]).values(state="queued"))
            self.conn.execute(update(m.runs).where(m.runs.c.id == run_id, m.runs.c.owner_id == self.owner).values(status=next_state, version=run["version"] + 1))
            self.conn.execute(update(m.approval_requests).where(m.approval_requests.c.id == body.request_id, m.approval_requests.c.owner_id == self.owner).values(state="decided"))
            self.event(run_id, "approval.decided", {"decision_id": str(decision["id"]), "gate": gate})
            return decision
        return self.idempotent(f"{gate}:{run_id}", key, body.model_dump(mode="json"), command)

    def control(self, run_id: UUID, action: str, expected_version: int, key: str, deadline_seconds: int = 3600) -> dict:
        def command():
            run = self.conn.execute(select(m.runs).where(m.runs.c.id == run_id, m.runs.c.owner_id == self.owner).with_for_update()).mappings().first()
            if run is None:
                raise HTTPException(404, "not_found")
            if run["version"] != expected_version:
                raise HTTPException(409, "stale_run")
            job = self.conn.execute(select(m.jobs).where(m.jobs.c.run_id == run_id, m.jobs.c.owner_id == self.owner).with_for_update()).mappings().one()
            if run["status"] in {"complete", "cancelled", "partial", "failed"}:
                raise HTTPException(409, "terminal_run")
            if action == "cancel":
                # Increment the fence while holding the same lock used by all managed writes.
                self.conn.execute(update(m.jobs).where(m.jobs.c.id == job["id"]).values(state="done", generation=job["generation"] + 1, worker_id=None, lease_until=None))
                self.conn.execute(update(m.approval_requests).where(m.approval_requests.c.run_id == run_id,
                    m.approval_requests.c.owner_id == self.owner, m.approval_requests.c.state == "pending").values(state="superseded"))
                self.conn.execute(update(m.runs).where(m.runs.c.id == run_id).values(status="cancelled", version=run["version"] + 1))
                self.event(run_id, "run.cancelled", {})
            elif action == "resume":
                if not job["managed"]:
                    if run["status"] != "queued" or run["checkpoint"]:
                        raise HTTPException(409, "fresh_workflow_run_required")
                    self.conn.execute(update(m.jobs).where(m.jobs.c.id == job["id"]).values(managed=True, state="queued",
                        deadline=func.clock_timestamp() + timedelta(seconds=deadline_seconds), workflow={"graph_version": "workflow-1.2", "revision_limit": 1,
                            "scout_case": "SC01-clean", "research_case": "R21-parallel", "mode": "replay"}))
                else:
                    pending = self.conn.execute(select(m.approval_requests.c.id).where(m.approval_requests.c.run_id == run_id,
                        m.approval_requests.c.owner_id == self.owner, m.approval_requests.c.state == "pending")).first()
                    if pending:
                        raise HTTPException(409, "approval_pending")
                    if job["state"] in {"queued", "claimed"}:
                        # Idempotent scheduling must not invalidate an in-flight
                        # harness RunContext or extend its original deadline.
                        return self.get(m.runs, run_id)
                    # An active/expired claimed job is recovered by claim(), not stolen here.
                    if job["state"] == "done":
                        self.conn.execute(update(m.jobs).where(m.jobs.c.id == job["id"]).values(state="queued"))
                self.conn.execute(update(m.runs).where(m.runs.c.id == run_id).values(version=run["version"] + 1))
                self.event(run_id, "workflow.queued", {"graph_version": "workflow-1.2", "label": "DEMO"})
            else:
                raise HTTPException(422, "invalid_control")
            return self.get(m.runs, run_id)
        return self.idempotent(f"{action}:{run_id}", key, {"expected_run_version": expected_version, "deadline_seconds": deadline_seconds}, command)
