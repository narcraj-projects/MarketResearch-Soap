"""Deterministic presentation of immutable evidence. No network or publishing capability."""
from hashlib import sha256
import re
from uuid import UUID, uuid5
from typing import Literal

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, func

from app import models as m
from app.api_schemas import BriefRecord, EventRecord, ShortlistSnapshot
from app.harness.analysis_types import AnalysisDraft, ReviewResult
from app.harness.policy import PolicyDenied
from app.harness.search_store import PostgresSearchLedger
from app.repository import digest
from app.report_types import ApprovalView, Coverage, Position, ReportSnapshot, ReportView, RunView, SourceView, HistoryView, HistoryEntry
from app.harness.chaos import ChaosPlan
from app.agents.scout import DiscoveryArtifact


def safe_link(value: str) -> str | None:
    from urllib.parse import urlsplit
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or re.search(r"[\x00-\x20<>\"\\]", value):
            return None
        return value
    except ValueError:
        return None


def source_view(row: dict) -> SourceView:
    return SourceView.model_validate({key: row.get(key) for key in SourceView.model_fields} | {"canonical_url": safe_link(row["canonical_url"])})


def citation_coverage(analysis: AnalysisDraft, sources: dict[UUID, dict]) -> Coverage:
    material = [finding for finding in analysis.findings if finding.value is not None and finding.kind in {"fact", "source_claim"}]
    linked = sum(any(e.source_id in sources for e in finding.evidence) for finding in material)
    intact = 0
    for finding in material:
        if any((source := sources.get(e.source_id)) is not None and source["access_status"] == "ok"
            and source.get("competitor_id") == finding.competitor_id
            and safe_link(source["canonical_url"]) and e.quote in (source.get("excerpt") or "")
            and sha256(e.quote.encode()).hexdigest() == e.quote_hash for e in finding.evidence):
            intact += 1
    fields = [field for competitor in analysis.comparisons for field in competitor.fields]
    unavailable = sum(field.unavailable_reason is not None for field in fields)
    return Coverage(material_facts=len(material), linked=linked, intact_quotes=intact,
        citation_presence=linked / len(material) if material else None, quote_coverage=intact / len(material) if material else None,
        comparison_fields=len(fields), populated_fields=len(fields) - unavailable, unavailable_fields=unavailable)


def positions(analysis: AnalysisDraft) -> tuple[Position, ...]:
    points = []
    for competitor in analysis.comparisons:
        findings = [f for f in analysis.findings if f.competitor_id == competitor.competitor_id and f.field == "positioning" and f.value is not None]
        wording = " ".join(str(f.value) for f in findings).casefold()
        ingredients = bool(re.search(r"\b(?:ingredient|ingredients|oil|oils|natural)\b", wording))
        results = bool(re.search(r"\b(?:results?|benefits?|performance)\b", wording))
        gifting = bool(re.search(r"\b(?:gifts?|gifting|luxe|luxury|premium)\b", wording))
        daily = bool(re.search(r"\b(?:everyday|daily|routine)\b", wording))
        x: Literal["ingredient_led", "mixed", "results_led"] | None = "mixed" if ingredients and results else "ingredient_led" if ingredients else "results_led" if results else None
        y: Literal["everyday", "mixed", "gifting"] | None = "mixed" if gifting and daily else "gifting" if gifting else "everyday" if daily else None
        points.append(Position(competitor_id=competitor.competitor_id, x=x, y=y, premise_ids=tuple(f.finding_id for f in findings),
            explanation="Categorical interpretation of cited positioning words; not a measured market coordinate." if x and y else "One or both axes are unavailable from the retrieved positioning wording; no coordinate inferred."))
    return tuple(points)


def snapshot(brief: dict, analysis: AnalysisDraft, source_rows: list[dict], shortlist: dict | None = None) -> ReportSnapshot:
    source_map = {row["id"]: row for row in source_rows}
    return ReportSnapshot(label=analysis.label, brief=BriefRecord.model_validate(brief), analysis=analysis,
        summary=f"{len(analysis.comparisons)} competitors compared from {'recorded' if analysis.label == 'DEMO' else 'live retrieved'} evidence; {len(analysis.opportunities)} conditional opportunities. Missing and conflicting observations remain visible. Strategic usefulness and genuine source support have not been independently established.",
        scope=f"{brief['category']} · {brief['geography']} · {brief['customer']}. Objective: {brief['objective']}. Findings are dated snapshots, not permanently current prices or proven demand.",
        coverage=citation_coverage(analysis, source_map), positioning=positions(analysis), sources=tuple(source_view(row) for row in source_rows), shortlist=DiscoveryArtifact.model_validate(shortlist) if shortlist else None)


def ready_receipt(repo, report: dict) -> ReviewResult | None:
    row = repo.conn.execute(select(m.evaluation_results).where(m.evaluation_results.c.id == uuid5(report["id"], "analysis.review:1.0"),
        m.evaluation_results.c.owner_id == repo.owner, m.evaluation_results.c.run_id == report["run_id"])).mappings().first()
    if not row or row["data"].get("report_hash") != report["content_hash"]:
        return None
    try:
        result = ReviewResult.model_validate(row["data"]["assessment"])
        analysis = report["data"].get("analysis")
        if result.draft_hash != digest(analysis) or not isinstance(analysis, dict) or result.input_hash != analysis.get("input_hash"):
            return None
        return result
    except (KeyError, ValidationError):
        return None


def approval_view(repo, run: dict, report: dict, review: ReviewResult | None) -> ApprovalView:
    requests = repo.conn.execute(select(m.approval_requests).where(m.approval_requests.c.owner_id == repo.owner,
        m.approval_requests.c.run_id == run["id"], m.approval_requests.c.gate == "report",
        m.approval_requests.c.artifact["report_id"].astext == str(report["id"]))).mappings().all()
    base = {"artifact_version": report["version"], "artifact_hash": report["content_hash"]}
    if len(requests) != 1 or review is None or review.decision != "ready_for_human":
        return ApprovalView(state="unavailable", **base)
    request = requests[0]
    if request["artifact_hash"] != report["content_hash"] or request["artifact_version"] != report["version"]:
        return ApprovalView(state="unavailable", **base)
    decision = repo.conn.execute(select(m.approval_decisions).where(m.approval_decisions.c.request_id == request["id"],
        m.approval_decisions.c.owner_id == repo.owner, m.approval_decisions.c.run_id == run["id"])).mappings().first()
    if decision and request["state"] == "decided" and decision["artifact_hash"] == report["content_hash"] and decision["artifact_version"] == report["version"]:
        state: Literal["saved", "approved_awaiting_save", "rejected"] = ("saved" if run["status"] == "complete" else "approved_awaiting_save") if decision["decision"] == "approve" else "rejected"
        return ApprovalView(state=state, request_id=request["id"], decision_id=decision["id"], decision=decision["decision"], decided_at=decision["created_at"], **base)
    return ApprovalView(state="pending" if request["state"] == "pending" else "unavailable", request_id=request["id"],
        can_decide=request["state"] == "pending" and run["status"] == "report_review", **base)


def report_view(repo, run: dict, report: dict) -> ReportView:
    if digest(report["data"]) != report["content_hash"]:
        raise HTTPException(409, "report_integrity_error")
    review = ready_receipt(repo, report)
    presentation, reason = None, None
    projection: Literal["persisted", "legacy_immutable_inputs", "unavailable"] = "unavailable"
    try:
        if report["data"].get("presentation") is not None:
            presentation = ReportSnapshot.model_validate(report["data"]["presentation"])
            if presentation.analysis.model_dump(mode="json") != report["data"]["analysis"]:
                raise ValueError("presentation_analysis_mismatch")
            projection = "persisted"
        else:
            analysis = AnalysisDraft.model_validate(report["data"]["analysis"])
            source_ids = {e.source_id for finding in analysis.findings for e in finding.evidence} | {p.source_id for p in analysis.normalized_prices}
            ownership = {UUID(source["source_id"]): UUID(source["competitor_id"]) for lane in repo.list(m.research_tasks, run["id"], limit=3) for source in lane["data"]["sources"]}
            rows = [dict(row) | {"competitor_id": ownership.get(row["id"])} for row in repo.conn.execute(select(m.sources).where(m.sources.c.owner_id == repo.owner,
                m.sources.c.run_id == run["id"], m.sources.c.id.in_(source_ids)).order_by(m.sources.c.id)).mappings()]
            presentation = snapshot(repo.get(m.briefs, run["brief_id"]), analysis, rows, report["data"].get("shortlist"))
            projection = "legacy_immutable_inputs"
        if presentation.analysis.run_id != run["id"] or presentation.brief.id != run["brief_id"] or presentation.brief.owner_id != repo.owner:
            raise ValueError("presentation_scope_mismatch")
    except (KeyError, ValueError, ValidationError):
        presentation = None
        projection = "unavailable"
        reason = "This draft has no valid structured report presentation. Its persisted review and issues remain available."
    approval = approval_view(repo, run, report, review)
    if presentation is None:
        approval = approval.model_copy(update={"can_decide": False})
    return ReportView(id=report["id"], version=report["version"], content_hash=report["content_hash"], created_at=report["created_at"],
        snapshot=presentation, unavailable_reason=reason, review=review, approval=approval,
        export_allowed=presentation is not None and approval.state == "saved", projection=projection)


def workspace(repo, run_id: UUID | None, report_version: int | None = None) -> RunView:
    if run_id is None:
        latest = repo.conn.execute(select(m.runs.c.id).where(m.runs.c.owner_id == repo.owner).order_by(m.runs.c.created_at.desc(), m.runs.c.id.desc()).limit(1)).scalar_one_or_none()
        if latest is None:
            return RunView(run=None)
        run_id = latest
    run = repo.get(m.runs, run_id)
    brief = repo.get(m.briefs, run["brief_id"])
    shortlist = None
    try:
        shortlist = PostgresSearchLedger.snapshot(repo, run_id)
    except PolicyDenied:
        pass
    competitors = repo.list(m.competitors, run_id, limit=3)
    if shortlist:
        ordering = {str(cid): index for index, cid in enumerate(shortlist["artifact"]["competitor_ids"])}
        competitors.sort(key=lambda candidate: ordering.get(str(candidate["id"]), 99))
    source_rows = repo.list(m.sources, run_id, limit=1000)
    usage = repo.list(m.usage, run_id, limit=10000)
    reserved = repo.conn.execute(select(func.count()).select_from(m.tool_attempts).where(m.tool_attempts.c.run_id == run_id,
        m.tool_attempts.c.owner_id == repo.owner, m.tool_attempts.c.state == "reserved")).scalar_one()
    events = [dict(row) for row in repo.conn.execute(select(m.events).where(m.events.c.run_id == run_id,
        m.events.c.owner_id == repo.owner).order_by(m.events.c.sequence.desc()).limit(100)).mappings()][::-1]
    checkpoint_at = repo.conn.execute(select(func.max(m.graph_checkpoints.c.created_at)).where(m.graph_checkpoints.c.run_id == run_id, m.graph_checkpoints.c.owner_id == repo.owner)).scalar_one()
    completed_nodes = sorted(set(repo.conn.execute(select(m.events.c.data["node"].astext).where(m.events.c.run_id == run_id,
        m.events.c.owner_id == repo.owner, m.events.c.kind == "workflow.node")).scalars()))
    research = []
    for row in repo.list(m.research_tasks, run_id, limit=3):
        observations = [observation for page in row["data"]["pages"] for observation in [*page["observations"], *(o for p in page["products"] for o in p["observations"])]]
        research.append({"competitor_id": row["competitor_id"], "state": row["state"], "sources": len(row["data"]["sources"]),
            "observations": len(observations), "known": sum(o["value"] is not None for o in observations), "unavailable": sum(o["value"] is None for o in observations), "limitations": row["data"]["limitations"]})
    report = None
    available = repo.conn.execute(select(m.reports.c.id).where(m.reports.c.run_id == run_id, m.reports.c.owner_id == repo.owner).limit(1)).first()
    if report_version is not None:
        from app.history import exact_report
        report = report_view(repo, run, exact_report(repo, run_id, report_version))
    elif available:
        report = report_view(repo, run, repo.report(run_id))
    job = repo.conn.execute(select(m.jobs.c.workflow).where(m.jobs.c.run_id == run_id, m.jobs.c.owner_id == repo.owner)).scalar_one_or_none()
    displayed_cost = sum(u["cost_usd"] for u in usage)
    if job and job.get("mode") == "live":
        # Completed model receipts reconcile known usage; uncertain attempts retain
        # their full reservation. The immutable usage journal keeps original holds.
        displayed_cost = repo.conn.execute(select(func.coalesce(func.sum(m.tool_attempts.c.cost_upper_bound_usd), 0)).where(
            m.tool_attempts.c.run_id == run_id, m.tool_attempts.c.owner_id == repo.owner)).scalar_one()
    chaos = None
    if job and job.get("chaos"):
        try:
            chaos = ChaosPlan.model_validate(job["chaos"])
        except ValidationError:
            pass  # Invalid plans are never rendered as active/authorized controls.
    all_events = repo.conn.execute(select(m.events.c.kind, m.events.c.data).where(m.events.c.run_id == run_id, m.events.c.owner_id == repo.owner)).all()
    recovery = {"retryable_failures": sum(kind == "tool.retryable_failure" for kind, data in all_events),
        "tool_recoveries": sum(kind == "tool.recovered" for kind, data in all_events), "schema_failures": sum(kind == "model.output_invalid" for kind, data in all_events),
        "model_repairs": sum(kind == "model.replay_validated" and data.get("repaired") is True for kind, data in all_events),
        "worker_recoveries": sum(kind == "worker.claimed" and data.get("recovered") is True for kind, data in all_events)}
    return RunView(label="LIVE" if job and job.get("mode") == "live" else "DEMO" if shortlist or report or run["checkpoint"] or (job and job.get("mode") == "replay") else None, run=run, brief=brief, shortlist=ShortlistSnapshot.model_validate(shortlist) if shortlist else None,
        competitors=competitors, sources=[source_view(row) for row in source_rows], research=research, events=[EventRecord.model_validate(row) for row in events],
        event_count=events[-1]["sequence"] if events else 0, checkpoint_at=checkpoint_at, completed_nodes=completed_nodes, report=report, chaos=chaos, recovery=recovery,
        usage={"calls": sum(u["calls"] for u in usage), "reserved_calls": reserved, "retries": sum(u["calls"] for u in usage if u["attempt"] > 1),
            "tokens": sum(u["tokens"] for u in usage), "cost_upper_bound_usd": str(displayed_cost)})


def history_view(repo, limit: int, offset: int) -> HistoryView:
    total = repo.conn.execute(select(func.count()).select_from(m.runs).where(m.runs.c.owner_id == repo.owner)).scalar_one()
    runs = repo.conn.execute(select(m.runs).where(m.runs.c.owner_id == repo.owner).order_by(m.runs.c.created_at.desc(), m.runs.c.id.desc()).limit(limit).offset(offset)).mappings().all()
    entries = []
    for run in runs:
        brief = repo.get(m.briefs, run["brief_id"])
        report = repo.conn.execute(select(m.reports).where(m.reports.c.owner_id == repo.owner, m.reports.c.run_id == run["id"]).order_by(m.reports.c.version.desc()).limit(1)).mappings().first()
        workflow = repo.conn.execute(select(m.jobs.c.workflow).where(m.jobs.c.owner_id == repo.owner, m.jobs.c.run_id == run["id"])).scalar_one_or_none()
        count = repo.conn.execute(select(func.count()).select_from(m.competitors).where(m.competitors.c.owner_id == repo.owner, m.competitors.c.run_id == run["id"])).scalar_one()
        report_count = repo.conn.execute(select(func.count()).select_from(m.reports).where(m.reports.c.owner_id == repo.owner, m.reports.c.run_id == run["id"])).scalar_one()
        saved_version = None
        saved_as_of = None
        if run["status"] == "complete" and report:
            try:
                saved = report_view(repo, dict(run), repo.report(run["id"]))
                saved_version = saved.version if saved.export_allowed else None
                saved_as_of = saved.snapshot.analysis.as_of if saved_version is not None and saved.snapshot else None
            except HTTPException as error:
                if error.status_code not in {404, 409}:
                    raise
        entries.append(HistoryEntry(id=run["id"], created_at=run["created_at"], status=run["status"], category=brief["category"], geography=brief["geography"],
            competitors=count, report_id=report["id"] if report else None, report_version=report["version"] if report else None,
            saved_report_version=saved_version, saved_as_of=saved_as_of, report_versions=report_count,
            label="LIVE" if workflow and workflow.get("mode") == "live" else "DEMO" if (workflow and workflow.get("mode") == "replay") or (report and report["data"].get("label") == "DEMO") else None))
    return HistoryView(entries=entries, total=total)
