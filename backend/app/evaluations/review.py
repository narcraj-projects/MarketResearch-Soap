"""Authenticated human review receipts, bound to immutable reports and evidence.

These receipts are separate from agent output. Fixture receipts never count as
business-owner ratings or trusted human support in an acceptance measurement.
"""
from hashlib import sha256
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid5

from fastapi import HTTPException
from pydantic import Field, JsonValue, model_validator
from sqlalchemy import select

from app import models as m
from app.config import Settings
from app.evaluations.contracts import EvalSchema
from app.evaluations.dataset import require_evaluation
from app.reporting import report_view
from app.repository import digest

CHECKS = ("all_atomic_components", "relevance", "attribution", "date_freshness", "sku_variant_pack_currency", "contradictions", "medical_claim_scope")


class ReviewEvidence(EvalSchema):
    source_id: UUID
    url: str | None
    retrieved_at: datetime
    content_hash: str | None
    excerpt: str | None
    quote: str
    quote_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    provenance_intact: bool


class ReviewClaim(EvalSchema):
    claim_id: UUID
    statement_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    text: str
    field: str
    value: JsonValue
    kind: Literal["fact", "source_claim"]
    competitor_id: UUID
    product_locator: str | None
    evidence: tuple[ReviewEvidence, ...]
    agent_support_status: Literal["unreviewed"] = "unreviewed"


class ReviewPacket(EvalSchema):
    schema_version: Literal["review-packet-1.0"] = "review-packet-1.0"
    label: Literal["DEMO"]
    run_id: UUID
    report_id: UUID
    report_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    approval: str
    required_checks: tuple[str, ...]
    material_claims: int = Field(ge=0)
    claims: tuple[ReviewClaim, ...]
    semantic_support: Literal["not_adjudicated"] = "not_adjudicated"
    instructions: str


class SupportReview(EvalSchema):
    report_id: UUID
    report_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    claim_id: UUID
    statement_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    disposition: Literal["supported", "contradicted", "insufficient"]
    source_ids: tuple[UUID, ...]
    checks_completed: tuple[str, ...]
    rationale: str = Field(min_length=10, max_length=4000)
    purpose: Literal["human_review", "demo_fixture"]
    attestation: Literal["I personally reviewed every factual component and its evidence"]

    @model_validator(mode="after")
    def complete_checks(self):
        if set(self.checks_completed) != set(CHECKS) or len(self.checks_completed) != len(CHECKS) or len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError("complete_unique_review_checks_required")
        if self.disposition == "supported" and not self.source_ids:
            raise ValueError("support_requires_sources")
        return self


class OwnerRating(EvalSchema):
    report_id: UUID
    report_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    useful: bool = Field(strict=True)
    purpose: Literal["human_review", "demo_fixture"]
    relevance: str = Field(min_length=5, max_length=1500)
    evidence_clarity: str = Field(min_length=5, max_length=1500)
    comparability: str = Field(min_length=5, max_length=1500)
    actionable_hypotheses: str = Field(min_length=5, max_length=1500)
    limitations: str = Field(min_length=5, max_length=1500)
    attestation: Literal["I am the business owner and personally assessed this report"]


class ReviewReceipt(EvalSchema):
    id: UUID
    report_id: UUID
    report_hash: str
    kind: Literal["claim_support", "owner_usefulness"]
    purpose: Literal["human_review", "demo_fixture"]
    disposition: str


class SupportMetrics(EvalSchema):
    material_claims: int = Field(ge=0)
    reviewed: int = Field(ge=0)
    supported: int = Field(ge=0)
    confirmed_lower_bound: float | None = Field(ge=0, le=1)
    support_coverage: float | None = Field(ge=0, le=1)
    status: Literal["passed", "failed", "not_evaluated", "incomplete"]


def packet(repo, run_id: UUID, report_id: UUID) -> dict:
    run, report = repo.get(m.runs, run_id), repo.get(m.reports, report_id)
    if report["run_id"] != run_id:
        raise HTTPException(404, "not_found")
    view = report_view(repo, run, report)
    if view.snapshot is None or report["content_hash"] != digest(report["data"]):
        raise HTTPException(409, "intact_report_snapshot_required")
    source_map = {str(source.id): source for source in view.snapshot.sources}
    claims = []
    for finding in view.snapshot.analysis.findings:
        if finding.value is None or finding.kind not in {"fact", "source_claim"}:
            continue
        references = []
        for link in finding.evidence:
            source = source_map.get(str(link.source_id))
            if source is None:
                continue
            intact = source.access_status == "ok" and link.quote in (source.excerpt or "") and sha256(link.quote.encode()).hexdigest() == link.quote_hash
            references.append({"source_id": str(source.id), "url": source.canonical_url, "retrieved_at": source.retrieved_at.isoformat(),
                "content_hash": source.content_hash, "excerpt": source.excerpt, "quote": link.quote, "quote_hash": link.quote_hash,
                "provenance_intact": intact})
        data = finding.model_dump(mode="json")
        claims.append({"claim_id": str(finding.finding_id), "statement_hash": digest(data), "text": finding.text, "field": finding.field,
            "value": finding.value, "kind": finding.kind, "competitor_id": str(finding.competitor_id), "product_locator": finding.product_locator,
            "evidence": references, "agent_support_status": "unreviewed"})
    return {"schema_version": "review-packet-1.0", "label": view.snapshot.label, "run_id": str(run_id), "report_id": str(report_id),
        "report_hash": report["content_hash"], "approval": view.approval.state, "required_checks": list(CHECKS),
        "material_claims": len(claims), "claims": claims, "semantic_support": "not_adjudicated",
        "instructions": "Exact quotes are provenance only. Judge every atomic component, relevance, attribution, scope/date, contradictions and medical wording; return insufficient when uncertain."}


def _gate(repo, settings: Settings, purpose, owner=False):
    ids = settings.business_owner_ids if owner else settings.trusted_reviewer_ids
    if repo.owner not in ids:
        raise HTTPException(403, "trusted_business_owner_required" if owner else "trusted_human_reviewer_required")
    if purpose == "demo_fixture":
        try:
            require_evaluation(settings, repo.conn.engine)
        except ValueError:
            raise HTTPException(403, "fixture_reviews_require_isolated_evaluation") from None


def submit(repo, settings: Settings, run_id: UUID, body: SupportReview | OwnerRating, key: str) -> ReviewReceipt:
    owner_rating = isinstance(body, OwnerRating)
    _gate(repo, settings, body.purpose, owner=owner_rating)
    current = packet(repo, run_id, body.report_id)
    if current["report_hash"] != body.report_hash:
        raise HTTPException(409, "stale_report_hash")
    if owner_rating and current["approval"] != "saved":
        raise HTTPException(409, "owner_rating_requires_approved_saved_report")
    if isinstance(body, SupportReview):
        claim = next((row for row in current["claims"] if row["claim_id"] == str(body.claim_id)), None)
        if claim is None or claim["statement_hash"] != body.statement_hash:
            raise HTTPException(409, "stale_or_unknown_claim")
        sources = {row["source_id"]: row for row in claim["evidence"]}
        if any(str(identifier) not in sources for identifier in body.source_ids):
            raise HTTPException(409, "evidence_not_bound_to_claim")
        if body.disposition == "supported" and not all(sources[str(identifier)]["provenance_intact"] for identifier in body.source_ids):
            raise HTTPException(409, "support_requires_intact_evidence")
    kind = "owner_usefulness" if owner_rating else "claim_support"
    outcome_text = "rated" if isinstance(body, OwnerRating) else body.disposition
    receipt_text = ("useful" if body.useful else "not_useful") if isinstance(body, OwnerRating) else body.disposition
    def command():
        case_id = uuid5(body.report_id, "human-review-contract-1.0")
        existing = repo.conn.execute(select(m.evaluation_cases.c.id).where(m.evaluation_cases.c.id == case_id, m.evaluation_cases.c.owner_id == repo.owner)).first()
        if not existing:
            repo.conn.execute(m.evaluation_cases.insert().values(id=case_id, owner_id=repo.owner, case_id="human-review-contract",
                dataset_version="human-review-1.0", data={"purpose": "Hash-bound authenticated review receipts; no automatic semantic judgment"}))
        row = repo.create(m.evaluation_results, {"run_id": run_id, "case_id": case_id, "outcome": outcome_text,
            "data": {"schema_version": "human-review-1.0", "kind": kind, "reviewer_id": str(repo.owner), **body.model_dump(mode="json")}})
        return {"id": str(row["id"]), "report_id": str(body.report_id), "report_hash": body.report_hash, "kind": kind,
            "purpose": body.purpose, "disposition": receipt_text}
    return ReviewReceipt.model_validate(repo.idempotent(f"human-review:{kind}:{run_id}", key, body.model_dump(mode="json"), command))


def coverage(review_packet: dict, receipts: list[dict], trusted_ids: tuple[UUID, ...]) -> dict:
    # Only server-authenticated human receipts for this exact report/statement count.
    latest = {}
    claims = {row["claim_id"]: row for row in review_packet["claims"]}
    for row in receipts:
        data = row.get("data", {})
        if row.get("owner_id") not in trusted_ids or data.get("reviewer_id") != str(row.get("owner_id")) or str(row.get("run_id")) != review_packet["run_id"]:
            continue
        if (data.get("schema_version") != "human-review-1.0" or data.get("kind") != "claim_support" or data.get("purpose") != "human_review"
            or data.get("report_hash") != review_packet["report_hash"] or data.get("report_id") != review_packet["report_id"]):
            continue
        claim = claims.get(data.get("claim_id"))
        if claim and claim["statement_hash"] == data.get("statement_hash"):
            latest[claim["claim_id"]] = data
    total = len(claims)
    supported = sum(row["disposition"] == "supported" for row in latest.values())
    complete = total > 0 and len(latest) == total
    return {"material_claims": total, "reviewed": len(latest), "supported": supported,
        "confirmed_lower_bound": supported / total if latest and total else None,
        "support_coverage": supported / total if complete else None,
        "status": "passed" if complete and supported / total >= .9 else "failed" if complete else "not_evaluated" if not latest else "incomplete"}


def owner_gate(cohort: list[dict], ratings: list[dict], trusted_ids: tuple[UUID, ...]) -> dict:
    if len(cohort) != 5 or len({row["run_id"] for row in cohort}) != 5:
        return {"status": "not_evaluated", "denominator": 5, "rated": 0, "useful": None, "reason": "Five distinct predeclared reports are required."}
    latest = {}
    expected = {(row["report_id"], row["report_hash"]) for row in cohort}
    for row in ratings:
        data = row.get("data", {})
        if row.get("owner_id") not in trusted_ids or data.get("reviewer_id") != str(row.get("owner_id")):
            continue
        key = (data.get("report_id"), data.get("report_hash"))
        if data.get("schema_version") == "human-review-1.0" and data.get("purpose") == "human_review" and data.get("kind") == "owner_usefulness" and key in expected:
            latest[key] = data
    useful = sum(row["useful"] is True for row in latest.values())
    return {"status": "passed" if len(latest) == 5 and useful >= 4 else "failed" if len(latest) == 5 else "not_evaluated",
        "denominator": 5, "rated": len(latest), "useful": useful if len(latest) == 5 else None}
