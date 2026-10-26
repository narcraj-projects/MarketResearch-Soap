"""Typed, replay-only LangGraph orchestration. HTTP commands cannot drive this graph."""
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from typing import Literal
from uuid import UUID, uuid5

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, update

from app import models as m
from app.adapters.public_web import RecordedWeb
from app.adapters.tavily import TavilyAdapter
from app.agents.researcher import research_parallel
from app.harness.checkpointer import GRAPH_VERSION
from app.harness.contracts import Versions
from app.harness.gateway import SearchGateway
from app.harness.lease import Lease
from app.harness.policy import PolicyDenied
from app.harness.recordings import RecordedTavily
from app.harness.research_store import ResearchStore
from app.harness.retrieval import ResearchGateway
from app.harness.search import SearchCost
from app.harness.search_store import PostgresSearchLedger
from app.repository import digest, owner_transaction
from app.services.discovery import discover
from app.services.analysis import AnalysisService


class WorkflowState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["workflow-1.2"] = "workflow-1.2"
    run_id: str = Field(pattern=r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$")
    phase: Literal["validate", "discover", "shortlist_review", "research", "normalize", "analyze", "review", "revise", "final_approval", "save", "stopped"] = "validate"
    shortlist: Literal["approve", "reject", "request_changes"] | None = None
    final: Literal["approve", "reject", "request_changes"] | None = None
    revision: int = Field(default=0, ge=0, le=3)
    revision_limit: int = Field(default=1, ge=0, le=3)
    review_ok: bool = False
    review_decision: Literal["ready_for_human", "revise", "unresolved"] | None = None
    prior_report_id: str | None = None
    report_id: str | None = None
    request_id: str | None = None
    issues: list[str] = Field(default_factory=list)
    manual_correction_request: UUID | None = None

    @model_validator(mode="after")
    def bounded_correction_reference(self):
        if (self.revision > 2 or self.revision_limit > 2) and self.manual_correction_request is None:
            raise ValueError("manual_correction_reference_required")
        return self


class Workflow:
    """Provider-neutral replay workflow with independent analysis/review boundaries."""
    def __init__(self, engine, lease: Lease, deadline: datetime, scout: RecordedTavily, web: RecordedWeb):
        self.engine, self.lease, self.deadline = engine, lease, deadline
        self.label = "DEMO"
        self.scout, self.web = scout, web
        self.search_store = PostgresSearchLedger(engine, lease)
        self.research_store = ResearchStore(engine, lease)

    def analysis_service(self):
        return AnalysisService(self.engine, self.lease)

    def scout_versions(self):
        return Versions(graph="scout-1.0", model="none", provider="none", prompt="deterministic-scout-1.0", tools="tavily-search-1.0", dataset="scout-demo-v1")

    def research_versions(self):
        return Versions(graph="research-1.0", model="none", provider="none", prompt="attributed-extraction-1.0", tools="public-research-1.0", dataset="research-demo-v1")

    def discovery_gateway(self):
        return SearchGateway(TavilyAdapter(self.scout.transport), self.search_store,
            SearchCost(per_attempt_upper_bound_usd=Decimal(0), pricing_version="DEMO-zero-spend"), guard=lambda: self.lease.check(self.engine))

    def research_gateway(self):
        return ResearchGateway(self.web, self.research_store, guard=lambda: self.lease.check(self.engine))

    def transaction(self):
        return owner_transaction(self.engine, self.lease.owner_id)

    def check(self, state: WorkflowState, *, tools: bool = False):
        if state.run_id != str(self.lease.run_id):
            raise PolicyDenied("workflow_run_mismatch")
        self.lease.check(self.engine)
        if tools and datetime.now(timezone.utc) >= self.deadline:
            raise PolicyDenied("deadline")

    def event(self, state: WorkflowState, phase: str):
        self.check(state)
        with self.transaction() as repo:
            self.lease.guard(repo)
            repo.event(self.lease.run_id, "workflow.node", {"node": phase, "graph_version": GRAPH_VERSION, "label": self.label})

    def validate(self, state: WorkflowState):
        self.check(state, tools=True)
        with self.transaction() as repo:
            run = self.lease.guard(repo)
            # Full brief validation also happens in discovery. No substituted brief.
            from app.api_schemas import BriefCreate
            row = repo.get(m.briefs, run["brief_id"])
            BriefCreate.model_validate({key: row[key] for key in BriefCreate.model_fields})
        self.event(state, "validate")
        return {"phase": "discover"}

    def discover(self, state: WorkflowState):
        self.check(state, tools=True)
        with self.transaction() as repo:
            run = self.lease.guard(repo)
            ready = "artifact" in (run["checkpoint"] or {})
            if ready:
                snapshot = PostgresSearchLedger.snapshot(repo, self.lease.run_id)
        if not ready:
            versions = self.scout_versions()
            context, brief = self.search_store.begin(self.lease.run_id, self.lease.owner_id, self.deadline, versions)
            gateway = self.discovery_gateway()
            snapshot = discover(context, brief, gateway, self.search_store)
        self.event(state, "discover")
        return {"phase": "shortlist_review" if snapshot["request_id"] else "stopped"}

    def gate(self, state: WorkflowState, gate: Literal["shortlist", "report"]):
        self.check(state)
        with self.transaction() as repo:
            run = self.lease.guard(repo)
            if gate == "shortlist":
                request_id = UUID(run["checkpoint"]["request_id"])
            else:
                if state.request_id is None:
                    raise PolicyDenied("report_request_missing")
                request_id = UUID(state.request_id)
            pending = repo.get(m.approval_requests, request_id)
        # Always interrupt even if an HTTP decision raced the graph checkpoint. The
        # worker supplies only the persisted decision ID; this value cannot approve.
        resumed = interrupt({"gate": gate, "request_id": str(request_id), "artifact_hash": pending["artifact_hash"], "artifact_version": pending["artifact_version"]})
        self.check(state)
        with self.transaction() as repo:
            run = self.lease.guard(repo)
            pending = repo.get(m.approval_requests, request_id)
            decisions = repo.conn.execute(select(m.approval_decisions).where(m.approval_decisions.c.owner_id == repo.owner,
                m.approval_decisions.c.run_id == self.lease.run_id, m.approval_decisions.c.request_id == request_id)).mappings().all()
            if len(decisions) != 1 or pending["state"] != "decided":
                raise PolicyDenied("durable_approval_required")
            decision = decisions[0]
            if (resumed != str(decision["id"]) or pending["artifact_hash"] != decision["artifact_hash"]
                or pending["artifact_version"] != decision["artifact_version"]):
                raise PolicyDenied("stale_approval")
            if gate == "shortlist" and digest(pending["artifact"]) != pending["artifact_hash"]:
                raise PolicyDenied("shortlist_integrity_error")
        return {"shortlist" if gate == "shortlist" else "final": decision["decision"],
            "phase": "research" if gate == "shortlist" else "save"}

    def research(self, state: WorkflowState):
        self.check(state, tools=True)
        versions = self.research_versions()
        context, competitors = self.research_store.begin(self.lease.run_id, self.lease.owner_id, self.deadline, versions)
        research_parallel(context, competitors, self.research_gateway(), self.research_store)
        self.event(state, "research")
        return {"phase": "normalize"}

    def normalize(self, state: WorkflowState):
        self.check(state)
        self.analysis_service().normalize()
        self.event(state, "normalize")
        return {"phase": "analyze"}

    def draft(self, state: WorkflowState) -> dict:
        data, _ = self.analysis_service().build(state.revision,
            UUID(state.prior_report_id) if state.prior_report_id else None)
        return data

    def analyze(self, state: WorkflowState):
        self.check(state)
        report_id = uuid5(self.lease.run_id, f"workflow-report:{state.revision + 1}")
        with self.transaction() as repo:
            self.lease.guard(repo)
            existing = repo.conn.execute(select(m.reports).where(m.reports.c.id == report_id, m.reports.c.owner_id == repo.owner)).mappings().first()
        if existing is None:
            draft = self.draft(state)
            with self.transaction() as repo:
                self.lease.guard(repo)
                repo.conn.execute(m.reports.insert().values(id=report_id, owner_id=repo.owner, run_id=self.lease.run_id,
                    version=state.revision + 1, content_hash=digest(draft), data=draft))
        self.event(state, "analyze")
        return {"phase": "review", "report_id": str(report_id)}

    def review(self, state: WorkflowState):
        self.check(state)
        result = self.analysis_service().assess(UUID(state.report_id or ""),
            revisions_remaining=state.revision < state.revision_limit)
        self.event(state, "review")
        return {"phase": "review", "issues": [i.target for i in result.issues if i.severity == "correction"],
            "review_ok": result.decision == "ready_for_human", "review_decision": result.decision}

    def revise(self, state: WorkflowState):
        self.check(state)
        if state.revision >= state.revision_limit:
            raise PolicyDenied("revision_limit")
        self.event(state, "revise")
        # Only reviewer-named targets are corrected against the same frozen evidence pack.
        return {"phase": "analyze", "revision": state.revision + 1, "review_ok": False, "prior_report_id": state.report_id, "report_id": None}

    def final_approval(self, state: WorkflowState):
        self.check(state)
        report_id = UUID(state.report_id or "")
        request_id = uuid5(report_id, "final-approval")
        with self.transaction() as repo:
            run = self.lease.guard(repo)
            report = repo.get(m.reports, report_id)
            if AnalysisService.receipt(repo, report).decision != "ready_for_human":
                raise PolicyDenied("independent_review_required")
            existing = repo.conn.execute(select(m.approval_requests).where(m.approval_requests.c.id == request_id, m.approval_requests.c.owner_id == repo.owner)).mappings().first()
            if existing is None:
                repo.conn.execute(m.approval_requests.insert().values(id=request_id, owner_id=repo.owner, run_id=self.lease.run_id, gate="report",
                    artifact_version=report["version"], artifact_hash=report["content_hash"], state="pending", artifact={"report_id": str(report_id)}))
                repo.conn.execute(update(m.runs).where(m.runs.c.id == self.lease.run_id).values(status="report_review", version=run["version"] + 1))
                repo.event(self.lease.run_id, "approval.pending", {"gate": "report", "request_id": str(request_id), "artifact_hash": report["content_hash"]})
        return self.gate(state.model_copy(update={"request_id": str(request_id)}), "report") | {"request_id": str(request_id)}

    def save(self, state: WorkflowState):
        self.check(state)
        if state.final != "approve":
            raise PolicyDenied("final_approval_required")
        with self.transaction() as repo:
            run = self.lease.guard(repo)
            request = repo.get(m.approval_requests, UUID(state.request_id or ""))
            report = repo.get(m.reports, UUID(state.report_id or ""))
            if AnalysisService.receipt(repo, report).decision != "ready_for_human":
                raise PolicyDenied("independent_review_required")
            decisions = repo.conn.execute(select(m.approval_decisions).where(m.approval_decisions.c.request_id == request["id"],
                m.approval_decisions.c.owner_id == repo.owner)).mappings().all()
            if (len(decisions) != 1 or decisions[0]["decision"] != "approve" or request["state"] != "decided"
                or request["artifact"]["report_id"] != str(report["id"]) or decisions[0]["artifact_hash"] != report["content_hash"]
                or digest(report["data"]) != report["content_hash"] or request["artifact_version"] != report["version"]):
                raise PolicyDenied("final_approval_required")
            if run["status"] != "complete":
                repo.conn.execute(update(m.runs).where(m.runs.c.id == self.lease.run_id).values(status="complete", version=run["version"] + 1))
                repo.event(self.lease.run_id, "run.completed", {"report_id": str(report["id"]), "artifact_hash": report["content_hash"], "label": self.label})
        return {"phase": "save"}

    def stopped(self, state: WorkflowState):
        self.check(state)
        with self.transaction() as repo:
            run = self.lease.guard(repo)
            if run["status"] != "partial":
                repo.conn.execute(update(m.runs).where(m.runs.c.id == self.lease.run_id).values(status="partial", version=run["version"] + 1))
                repo.event(self.lease.run_id, "workflow.stopped", {"code": "review_or_approval_failed"})
        return {"phase": "stopped"}


def inventory_issues(data: dict, content_hash: str) -> list[str]:
    """Mechanical presence/quote checks only; never a semantic-support score."""
    issues = []
    if digest(data) != content_hash:
        issues.append("report_hash")
    sources = {str(s["id"]): s for s in data.get("sources", [])}
    claims = {str(c["id"]): c for c in data.get("claims", [])}
    links = data.get("claim_sources", [])
    for claim_id, claim in claims.items():
        evidence = [link for link in links if str(link["claim_id"]) == claim_id]
        if claim["material"] and not evidence:
            issues.append("citation_missing")
        for link in evidence:
            source = sources.get(str(link["source_id"]))
            if (source is None or source["access_status"] != "ok" or not link["quote"]
                or link["quote"] not in (source.get("excerpt") or "")
                or sha256(link["quote"].encode()).hexdigest() != link["excerpt_hash"]):
                issues.append("citation_invalid")
        if claim["review_status"] == "supported":
            issues.append("semantic_support_not_adjudicated")
    return sorted(set(issues))


def review_route(state: WorkflowState) -> str:
    if state.review_decision == "unresolved":
        return "stopped"
    return "final_approval" if state.review_ok else "revise" if state.revision < state.revision_limit else "stopped"


def build_graph(workflow: Workflow, checkpointer):
    builder = StateGraph(WorkflowState)
    for name in ("validate", "discover", "research", "normalize", "analyze", "review", "revise", "final_approval", "save", "stopped"):
        builder.add_node(name, getattr(workflow, name))
    builder.add_node("shortlist_review", lambda state: workflow.gate(state, "shortlist"))
    builder.add_edge(START, "validate")
    builder.add_edge("validate", "discover")
    builder.add_conditional_edges("discover", lambda state: state.phase, {"shortlist_review": "shortlist_review", "stopped": "stopped"})
    builder.add_conditional_edges("shortlist_review", lambda state: state.shortlist == "approve", {True: "research", False: "stopped"})
    for start, end in (("research", "normalize"), ("normalize", "analyze"), ("analyze", "review"), ("revise", "analyze")):
        builder.add_edge(start, end)
    builder.add_conditional_edges("review", review_route, {name: name for name in ("final_approval", "revise", "stopped")})
    builder.add_conditional_edges("final_approval", lambda state: state.final == "approve", {True: "save", False: "stopped"})
    builder.add_edge("save", END)
    builder.add_edge("stopped", END)
    return builder.compile(checkpointer=checkpointer)
