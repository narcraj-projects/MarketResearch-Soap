"""Fenced, owner-scoped analysis snapshots and immutable independent review receipts."""
from uuid import UUID, uuid5

from sqlalchemy import func, select, update

from app import models as m
from app.agents.analyst import analyze
from app.agents.correction import correct
from app.agents.reviewer import review_payload
from app.agents.evidence_catalog import catalog
from app.agents.normalization import normalize_price
from app.harness.analysis_types import AnalysisDraft, Competitor, EvidencePack, ReviewResult
from app.harness.lease import Lease
from app.harness.policy import PolicyDenied
from app.harness.research_types import CompetitorResearch
from app.repository import digest, owner_transaction


class AnalysisService:
    def __init__(self, engine, lease: Lease):
        self.engine, self.lease = engine, lease

    def pack(self) -> EvidencePack:
        with owner_transaction(self.engine, self.lease.owner_id) as repo:
            run = self.lease.guard(repo)
            checkpoint = dict(run["checkpoint"] or {})
            if (checkpoint.get("research") or {}).get("state") != "research_complete":
                raise PolicyDenied("research_not_complete")
            config = checkpoint.get("analysis")
            if config is None:
                config = {"schema_version": "analysis-1.0", "as_of": repo.conn.execute(select(func.clock_timestamp())).scalar_one().isoformat(),
                    "freshness_days": 30, "analyst": "comparison-rules-1.0", "reviewer": "independent-review-1.0"}
                checkpoint["analysis"] = config
                repo.conn.execute(update(m.runs).where(m.runs.c.id == run["id"]).values(checkpoint=checkpoint))
            if config.get("schema_version") != "analysis-1.0" or config.get("analyst") != "comparison-rules-1.0" or config.get("reviewer") != "independent-review-1.0":
                raise PolicyDenied("analysis_version_mismatch")
            ids = [UUID(cid) for cid in checkpoint["research"]["competitor_ids"]]
            competitors = tuple(Competitor(competitor_id=cid, name=repo.get(m.competitors, cid)["name"], canonical_url=repo.get(m.competitors, cid)["canonical_url"]) for cid in ids)
            supplemented = (checkpoint.get("live_evidence_supplement") or {}).get("lanes", {})
            research = tuple(CompetitorResearch.model_validate(supplemented.get(str(row["competitor_id"]), row["data"])) for row in repo.list(m.research_tasks, run["id"], limit=3))
            research = tuple(sorted(research, key=lambda row: ids.index(row.competitor_id)))
            for lane in research:
                for source in lane.sources:
                    stored = repo.get(m.sources, source.source_id)
                    doc = repo.conn.execute(select(m.source_documents).where(m.source_documents.c.source_id == source.source_id,
                        m.source_documents.c.owner_id == repo.owner, m.source_documents.c.run_id == run["id"])).mappings().one()
                    if (stored["run_id"] != run["id"] or stored["canonical_url"] != source.canonical_url or stored["content_hash"] != source.content_hash
                        or stored["retrieved_at"] != source.retrieved_at or stored["excerpt"] != source.excerpt or doc["body"] != source.body
                        or doc["text_hash"] != source.text_hash or tuple(doc["structured"]) != source.structured or tuple(doc["links"]) != source.links):
                        raise PolicyDenied("analysis_source_record_mismatch")
            return EvidencePack(label="LIVE" if run["checkpoint"]["artifact"]["label"] == "LIVE" else "DEMO", run_id=run["id"], as_of=config["as_of"], freshness_days=config["freshness_days"], competitors=competitors, research=research)

    def build(self, revision: int, prior_report_id: UUID | None = None) -> tuple[dict, tuple[str, ...]]:
        pack = self.pack()
        targets: tuple[str, ...] = ()
        if prior_report_id:
            with owner_transaction(self.engine, self.lease.owner_id) as repo:
                self.lease.guard(repo)
                prior = repo.get(m.reports, prior_report_id)
                if prior["run_id"] != self.lease.run_id:
                    raise PolicyDenied("correction_run_mismatch")
                assessment = self.receipt(repo, prior)
            draft, targets = correct(pack, AnalysisDraft.model_validate(prior["data"]["analysis"]), assessment)
        else:
            draft = analyze(pack)
        with owner_transaction(self.engine, self.lease.owner_id) as repo:
            run = self.lease.guard(repo)
            from app.reporting import snapshot
            ownership = {source.source_id: source.competitor_id for lane in pack.research for source in lane.sources}
            for candidate in run["checkpoint"]["artifact"]["discovery"]["pool"]:
                ownership.update({UUID(source_id): UUID(candidate["candidate_id"]) for source_id in candidate["source_ids"]})
            source_rows = [dict(row) | {"competitor_id": ownership.get(row["id"])} for row in repo.conn.execute(select(m.sources).where(
                m.sources.c.owner_id == repo.owner, m.sources.c.run_id == pack.run_id).order_by(m.sources.c.id)).mappings()]
            presentation = snapshot(repo.get(m.briefs, run["brief_id"]), draft, source_rows, run["checkpoint"]["artifact"])
            return {"schema_version": "analysis-report-1.0", "label": pack.label, "revision": revision,
                "analysis": draft.model_dump(mode="json"), "presentation": presentation.model_dump(mode="json"),
                "shortlist": run["checkpoint"]["artifact"], "support_status": "unreviewed",
                "methodology": {"analyst": "comparison-rules-1.0", "reviewer": "independent-review-1.0", "provider": "none", "model": "none",
                    "source_support": "not_adjudicated", "freshness_days": pack.freshness_days, "correction_targets": list(targets)}}, targets

    def normalize(self) -> None:
        pack = self.pack()
        catalog(pack)  # Validate raw source/extraction bindings before numeric processing.
        rows = tuple(normalize_price(lane.competitor_id, product, next(s for s in lane.sources if s.source_id == page.source_id))
            for lane in pack.research for page in lane.pages for product in page.products)
        normalized_hash = digest([row.model_dump(mode="json") for row in rows])
        with owner_transaction(self.engine, self.lease.owner_id) as repo:
            run = self.lease.guard(repo)
            checkpoint = dict(run["checkpoint"])
            state = dict(checkpoint["analysis"])
            if state.get("normalization_hash") and state["normalization_hash"] != normalized_hash:
                raise PolicyDenied("normalization_snapshot_mismatch")
            if not state.get("normalization_hash"):
                state["normalization_hash"] = normalized_hash
                checkpoint["analysis"] = state
                repo.conn.execute(update(m.runs).where(m.runs.c.id == run["id"]).values(checkpoint=checkpoint))
                repo.event(run["id"], "analysis.normalized", {"schema_version": "1.0", "items": len(rows),
                    "eligible": sum(row.unit_price_100g is not None for row in rows), "normalization_hash": normalized_hash})

    @staticmethod
    def receipt(repo, report: dict) -> ReviewResult:
        identifier = uuid5(report["id"], "analysis.review:1.0")
        row = repo.get(m.evaluation_results, identifier)
        if row["run_id"] != report["run_id"] or row["data"]["report_hash"] != report["content_hash"]:
            raise PolicyDenied("review_receipt_mismatch")
        result = ReviewResult.model_validate(row["data"]["assessment"])
        if result.draft_hash != digest(report["data"]["analysis"]):
            raise PolicyDenied("review_draft_mismatch")
        return result

    def assess(self, report_id: UUID, *, revisions_remaining: bool) -> ReviewResult:
        pack = self.pack()
        with owner_transaction(self.engine, self.lease.owner_id) as repo:
            self.lease.guard(repo)
            report = repo.get(m.reports, report_id)
            if report["run_id"] != pack.run_id or digest(report["data"]) != report["content_hash"]:
                raise PolicyDenied("review_report_mismatch")
            previous = repo.conn.execute(select(m.evaluation_results.c.id).where(m.evaluation_results.c.id == uuid5(report_id, "analysis.review:1.0"), m.evaluation_results.c.owner_id == repo.owner)).first()
            if previous:
                return self.receipt(repo, report)
        result = review_payload(pack, report["data"]["analysis"], revisions_remaining=revisions_remaining)
        with owner_transaction(self.engine, self.lease.owner_id) as repo:
            self.lease.guard(repo)
            case_id = uuid5(pack.run_id, "analysis-review-validator:1.0")
            if repo.conn.execute(select(m.evaluation_cases.c.id).where(m.evaluation_cases.c.id == case_id, m.evaluation_cases.c.owner_id == repo.owner)).first() is None:
                repo.conn.execute(m.evaluation_cases.insert().values(id=case_id, owner_id=repo.owner, case_id="analysis-review-validator", dataset_version="analysis-review-1.0",
                    data={"label": pack.label, "purpose": "Deterministic draft validation receipt, not a business acceptance score"}))
            repo.conn.execute(m.evaluation_results.insert().values(id=uuid5(report_id, "analysis.review:1.0"), owner_id=repo.owner, run_id=pack.run_id,
                case_id=case_id, outcome=result.decision, data={"label": pack.label, "report_id": str(report_id), "report_hash": report["content_hash"], "assessment": result.model_dump(mode="json")}))
            repo.event(pack.run_id, "analysis.reviewed", {"report_id": str(report_id), "decision": result.decision,
                "corrections": sum(i.severity == "correction" for i in result.issues), "warnings": sum(i.severity == "warning" for i in result.issues), "schema_version": "1.0"})
        return result
