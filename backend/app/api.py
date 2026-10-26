from collections.abc import Iterator
from types import GenericAlias
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app import models as m
from app.api_schemas import ApprovalRequestRecord, BriefCreate, BriefRecord, ClaimRecord, CompetitorRecord, DecisionCreate, DecisionRecord, Error, EvaluationRecord, EventRecord, Me, PriceRecord, ProductRecord, ReportRecord, RunCreate, RunRecord, SourceRecord, UsageRecord
from app.auth import Identity, current_user
from app.repository import Repository, owner_transaction
from app.api_schemas import ShortlistSnapshot
from app.harness.search_store import PostgresSearchLedger
from app.harness.policy import PolicyDenied
from app.api_schemas import ClaimEvidenceRecord, ResearchRecord
from app.api_schemas import RunControl, RunResume
from app.event_stream import persisted_stream
from app.report_types import RunView, HistoryView
from app.reporting import workspace, report_view, history_view
from app.report_exports import export_report
from app.history import diff, versions
from app.history_types import HistoryDiff, VersionList
from app.harness.chaos import ChaosCreate, ChaosCapabilities, ChaosQueued, read_fixture, require_test_mode, require_isolated_engine
from app.services.chaos import create_demo
from app.evaluations.review import SupportReview, OwnerRating, ReviewReceipt, ReviewPacket, SupportMetrics, coverage as review_coverage, packet as review_packet, submit as submit_review
from fastapi.responses import Response
from typing import Literal
from sqlalchemy import select

router = APIRouter(prefix="/api", responses={401: {"model": Error}, 404: {"model": Error}, 409: {"model": Error}, 503: {"model": Error}})
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]


def repository(request: Request, identity: Identity = Depends(current_user)) -> Iterator[Repository]:
    if request.app.state.settings.database_url is None:
        raise HTTPException(503, "database_not_configured")
    if request.app.state.engine is None:
        raise HTTPException(503, "database_not_configured")
    try:
        with owner_transaction(request.app.state.engine, identity.user_id) as repo:
            yield repo
    except IntegrityError:
        raise HTTPException(409, "constraint_conflict") from None
    except (SQLAlchemyError, RuntimeError):
        raise HTTPException(503, "storage_unavailable") from None


def chaos_gate(request: Request):
    try:
        require_test_mode(request.app.state.settings)
        require_isolated_engine(request.app.state.engine)
    except PolicyDenied:
        raise HTTPException(403, "chaos_disabled") from None


@router.get("/chaos/capabilities", response_model=ChaosCapabilities)
def chaos_capabilities(request: Request, identity: Identity = Depends(current_user)):
    try:
        require_test_mode(request.app.state.settings)
        require_isolated_engine(request.app.state.engine)
    except PolicyDenied:
        return {"enabled": False, "label": "DEMO", "scenarios": []}
    registry = read_fixture("scenarios.json")
    return {"enabled": True, "label": "DEMO", "scenarios": [{"scenario": row["scenario"], "title": row["title"]} for row in registry["scenarios"]]}


@router.post("/chaos/runs", response_model=ChaosQueued, status_code=201, dependencies=[Depends(chaos_gate)], responses={403: {"model": Error}})
def create_chaos_run(body: ChaosCreate, request: Request, idempotency_key: Key, repo: Repository = Depends(repository, scope="function")):
    return create_demo(repo, body, idempotency_key, request.app.state.settings)


@router.get("/auth/me", response_model=Me)
def me(identity: Identity = Depends(current_user)) -> Me:
    return Me(user_id=identity.user_id)


@router.get("/live-pilot")
def live_pilot_capability(identity: Identity = Depends(current_user)):
    from app.harness.live_policy import ROOT, load_permit
    import json
    try:
        raw = json.loads((ROOT / ".cache/live-authorization.json").read_text())
        permit = load_permit(UUID(raw["run_id"]), identity.user_id)
        return {"enabled": True, "run_id": str(permit.run_id), "tavily_credit_cap": permit.max_tavily_credits,
            "model_usd_cap": str(permit.max_model_usd), "provider": permit.provider, "model": permit.model, "provisional_model": True}
    except (OSError, ValueError, KeyError):
        return {"enabled": False}


@router.get("/runs/{run_id}/review-packet", response_model=ReviewPacket)
def human_review_packet(run_id: UUID, report_id: UUID, repo: Repository = Depends(repository, scope="function")):
    return review_packet(repo, run_id, report_id)


@router.get("/runs/{run_id}/review-metrics", response_model=SupportMetrics)
def human_review_metrics(run_id: UUID, report_id: UUID, request: Request, repo: Repository = Depends(repository, scope="function")):
    current = review_packet(repo, run_id, report_id)
    receipts = repo.conn.execute(select(m.evaluation_results).where(m.evaluation_results.c.owner_id == repo.owner,
        m.evaluation_results.c.run_id == run_id).order_by(m.evaluation_results.c.created_at, m.evaluation_results.c.id)).mappings().all()
    return review_coverage(current, [dict(row) for row in receipts], request.app.state.settings.trusted_reviewer_ids)


@router.post("/runs/{run_id}/claim-reviews", response_model=ReviewReceipt, status_code=201, responses={403: {"model": Error}})
def human_claim_review(run_id: UUID, body: SupportReview, request: Request, idempotency_key: Key, repo: Repository = Depends(repository, scope="function")):
    return submit_review(repo, request.app.state.settings, run_id, body, idempotency_key)


@router.post("/runs/{run_id}/owner-ratings", response_model=ReviewReceipt, status_code=201, responses={403: {"model": Error}})
def human_owner_rating(run_id: UUID, body: OwnerRating, request: Request, idempotency_key: Key, repo: Repository = Depends(repository, scope="function")):
    return submit_review(repo, request.app.state.settings, run_id, body, idempotency_key)


@router.post("/briefs", response_model=BriefRecord, status_code=201)
def create_brief(body: BriefCreate, idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", min_length=8, max_length=128)] = None, repo: Repository = Depends(repository, scope="function")):
    payload = body.model_dump(mode="json")
    def command():
        return repo.create(m.briefs, payload | {"version": 1})
    return repo.idempotent("brief", idempotency_key, payload, command) if idempotency_key else command()


@router.get("/briefs/{brief_id}", response_model=BriefRecord)
def brief(brief_id: UUID, repo: Repository = Depends(repository, scope="function")):
    return repo.get(m.briefs, brief_id)


@router.post("/runs", response_model=RunRecord, status_code=201)
def start(body: RunCreate, idempotency_key: Key, repo: Repository = Depends(repository, scope="function")):
    return repo.start(body, idempotency_key)


@router.get("/runs/{run_id}", response_model=RunRecord)
def run(run_id: UUID, repo: Repository = Depends(repository, scope="function")):
    return repo.get(m.runs, run_id)


@router.get("/runs/{run_id}/shortlist", response_model=ShortlistSnapshot)
def shortlist(run_id: UUID, repo: Repository = Depends(repository, scope="function")):
    try:
        return PostgresSearchLedger.snapshot(repo, run_id)
    except PolicyDenied:
        raise HTTPException(404, "shortlist_not_ready") from None


@router.get("/history", response_model=list[RunRecord])
def history(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), repo: Repository = Depends(repository, scope="function")):
    return repo.list(m.runs, limit=limit, offset=offset)


@router.get("/workspace", response_model=RunView)
def workspace_data(run_id: UUID | None = None, report_version: int | None = Query(None, ge=1), repo: Repository = Depends(repository, scope="function")):
    if report_version is not None and run_id is None:
        raise HTTPException(422, "run_id_required_for_report_version")
    return workspace(repo, run_id, report_version)


@router.get("/history/view", response_model=HistoryView)
def saved_history(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), repo: Repository = Depends(repository, scope="function")):
    return history_view(repo, limit, offset)


@router.get("/runs/{run_id}/versions", response_model=VersionList)
def saved_versions(run_id: UUID, limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0), repo: Repository = Depends(repository, scope="function")):
    return versions(repo, run_id, limit, offset)


@router.get("/history/diff", response_model=HistoryDiff)
def compare_history(before_run: UUID, after_run: UUID, before_version: int = Query(..., ge=1), after_version: int = Query(..., ge=1), repo: Repository = Depends(repository, scope="function")):
    return diff(repo, before_run, after_run, before_version, after_version)


@router.get("/runs/{run_id}/export", response_class=Response, responses={200: {"content": {"text/html": {}, "text/csv": {}}}})
def download_report(run_id: UUID, format: Literal["html", "csv"] = "html", report_id: UUID | None = None, repo: Repository = Depends(repository, scope="function")):
    run = repo.get(m.runs, run_id)
    report = repo.get(m.reports, report_id) if report_id else repo.report(run_id)
    if report["run_id"] != run_id:
        raise HTTPException(404, "not_found")
    view = report_view(repo, run, report)
    content = export_report(view, format)
    return Response(content=content, media_type="text/html" if format == "html" else "text/csv",
        headers={"Content-Disposition": f'attachment; filename="lather-lens-{view.id}-v{view.version}.{format}"',
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"})


@router.get("/runs/{run_id}/report", response_model=ReportRecord)
def report(run_id: UUID, repo: Repository = Depends(repository, scope="function")):
    return repo.report(run_id)


@router.get("/runs/{run_id}/research", response_model=list[ResearchRecord])
def research(run_id: UUID, repo: Repository = Depends(repository, scope="function")):
    return repo.list(m.research_tasks, run_id, limit=3)


@router.get("/runs/{run_id}/claims/{claim_id}/evidence", response_model=list[ClaimEvidenceRecord])
def claim_evidence(run_id: UUID, claim_id: UUID, repo: Repository = Depends(repository, scope="function")):
    if repo.get(m.claims, claim_id)["run_id"] != run_id:
        raise HTTPException(404, "not_found")
    return [dict(row) for row in repo.conn.execute(select(m.claim_sources).where(m.claim_sources.c.owner_id == repo.owner,
        m.claim_sources.c.run_id == run_id, m.claim_sources.c.claim_id == claim_id)).mappings()]


@router.post("/runs/{run_id}/shortlist-decision", response_model=DecisionRecord)
def shortlist_decision(run_id: UUID, body: DecisionCreate, idempotency_key: Key, repo: Repository = Depends(repository, scope="function")):
    return repo.decide(run_id, "shortlist", body, idempotency_key)


@router.post("/runs/{run_id}/report-decision", response_model=DecisionRecord)
def report_decision(run_id: UUID, body: DecisionCreate, idempotency_key: Key, repo: Repository = Depends(repository, scope="function")):
    return repo.decide(run_id, "report", body, idempotency_key)


@router.post("/runs/{run_id}/resume", response_model=RunRecord)
def resume_run(run_id: UUID, body: RunResume, idempotency_key: Key, repo: Repository = Depends(repository, scope="function")):
    return repo.control(run_id, "resume", body.expected_run_version, idempotency_key, body.deadline_seconds)


@router.post("/runs/{run_id}/cancel", response_model=RunRecord)
def cancel_run(run_id: UUID, body: RunControl, idempotency_key: Key, repo: Repository = Depends(repository, scope="function")):
    return repo.control(run_id, "cancel", body.expected_run_version, idempotency_key)


@router.get("/runs/{run_id}/events/stream", response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}}})
def stream_events(run_id: UUID, request: Request, after: int = Query(0, ge=0), follow_seconds: int = Query(20, ge=0, le=25),
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None, repo: Repository = Depends(repository, scope="function")):
    cursor = after
    if last_event_id is not None:
        if not last_event_id.isascii() or not last_event_id.isdigit() or len(last_event_id) > 10:
            raise HTTPException(400, "invalid_event_cursor")
        cursor = max(after, int(last_event_id))
    # Auth/ownership and first read finish BEFORE HTTP response headers. The function-
    # scoped dependency commits before streaming; later polls use short transactions.
    initial = repo.list(m.events, run_id, limit=100, after=cursor)
    return StreamingResponse(persisted_stream(request.app.state.engine, repo.owner, run_id, cursor, initial,
        follow_seconds=follow_seconds, request=request), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"})


def resource(table):
    def endpoint(run_id: UUID, limit: int = Query(50, ge=1, le=100), after: int = Query(0, ge=0), offset: int = Query(0, ge=0), repo: Repository = Depends(repository, scope="function")):
        return repo.list(table, run_id=run_id, limit=limit, after=after, offset=offset)
    return endpoint


for path, (table, schema) in {"events": (m.events, EventRecord), "competitors": (m.competitors, CompetitorRecord),
    "sources": (m.sources, SourceRecord), "claims": (m.claims, ClaimRecord), "products": (m.products, ProductRecord),
    "prices": (m.prices, PriceRecord), "reports": (m.reports, ReportRecord), "approvals": (m.approval_requests, ApprovalRequestRecord),
    "evals": (m.evaluation_results, EvaluationRecord), "usage": (m.usage, UsageRecord)}.items():
    router.add_api_route(f"/runs/{{run_id}}/{path}", resource(table), methods=["GET"], response_model=GenericAlias(list, schema), name=f"list_{path}")
