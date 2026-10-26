"""Local integration fixture persistence. Actual mechanical review and durable decision."""
from uuid import UUID, uuid4, uuid5

from sqlalchemy import update

from app import models as m
from app.api_schemas import BriefRecord, DecisionCreate, RunCreate
from app.repository import digest, owner_transaction
from tests.history_support import history_document


def seed_history(engine, owner: UUID, mode="same", *, later=False, revisions=False):
    with owner_transaction(engine, owner) as repo:
        brief = repo.create(m.briefs, {"version": 1, "category": "DEMO handmade soap", "geography": "DEMO India", "customer": "DEMO buyer",
            "objective": "DEMO dated comparison", "known_competitors": [], "preferences": {}})
        run = repo.start(RunCreate(brief_id=brief["id"], budget={"max_calls": 40, "max_tokens": 0, "max_cost_usd": "0"}), str(uuid4()))
        run_id = UUID(str(run["id"]))
    view, _ = history_document(mode, later=later, run_id=run_id)
    assert view.review.decision == "ready_for_human", "DEMO mechanical review must actually pass"
    document = view.snapshot.model_copy(update={"brief": BriefRecord.model_validate(brief)})
    reports = []
    with owner_transaction(engine, owner) as repo:
        for candidate in document.shortlist.discovery.candidates:
            repo.conn.execute(m.competitors.insert().values(id=candidate.candidate_id, owner_id=owner, run_id=run_id, name=candidate.name, canonical_url=candidate.canonical_url))
        for source in document.sources:
            repo.conn.execute(m.sources.insert().values(**source.model_dump(exclude={"competitor_id"}, mode="python"), owner_id=owner, run_id=run_id))
        case = repo.create(m.evaluation_cases, {"case_id": "history-DEMO-review", "dataset_version": "history-demo-v1", "data": {"label": "DEMO", "purpose": "Actual mechanical review of generated dated evidence, not business acceptance"}})
        for version in range(1, 3 if revisions else 2):
            data = {"schema_version": "analysis-report-1.0", "label": "DEMO", "analysis": document.analysis.model_dump(mode="json"),
                "presentation": document.model_dump(mode="json"), "shortlist": document.shortlist.model_dump(mode="json"), "revision": version - 1}
            report = repo.create(m.reports, {"run_id": run_id, "version": version, "data": data, "content_hash": digest(data)})
            repo.conn.execute(m.evaluation_results.insert().values(id=uuid5(report["id"], "analysis.review:1.0"), owner_id=owner, run_id=run_id,
                case_id=case["id"], outcome=view.review.decision, data={"label": "DEMO", "report_id": str(report["id"]), "report_hash": report["content_hash"], "assessment": view.review.model_dump(mode="json")}))
            reports.append(report)
        repo.conn.execute(update(m.runs).where(m.runs.c.id == run_id).values(status="report_review"))
        final = reports[-1]
        request = repo.create(m.approval_requests, {"run_id": run_id, "gate": "report", "artifact_version": final["version"],
            "artifact_hash": final["content_hash"], "state": "pending", "artifact": {"report_id": str(final["id"])}})
        repo.decide(run_id, "report", DecisionCreate(request_id=request["id"], artifact_version=final["version"], artifact_hash=final["content_hash"],
            expected_run_version=1, decision="approve"), str(uuid4()))
    return run_id, reports
