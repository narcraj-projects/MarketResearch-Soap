"""Skeleton agent handoffs; referential/provenance checks belong to the harness."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AnyHttpUrl, Field, model_validator

from .contracts import Claim, Contract, Digest, EvidenceLink, Positive, Role, RunContext, Text


class AgentInput(Contract):
    context: RunContext
    agent: Role
    input_artifact_ids: tuple[UUID, ...]


class Source(Contract):
    source_id: UUID
    canonical_url: AnyHttpUrl
    title: Text
    publisher: Text
    retrieved_at: datetime
    content_hash: Digest | None
    access_status: Literal["ok", "denied", "unavailable"]

    @model_validator(mode="after")
    def source_shape(self):
        if self.retrieved_at.utcoffset() is None or (self.access_status == "ok" and self.content_hash is None):
            raise ValueError("source_date_or_hash_missing")
        return self


class UnreviewedEvidence(EvidenceLink):
    support: Literal["unreviewed"] = "unreviewed"
    adjudicator: None = None
    rationale: None = None


class AgentClaim(Claim):
    evidence: tuple[UnreviewedEvidence, ...] = ()


class Candidate(Contract):
    candidate_id: UUID
    name: Text
    evidence: tuple[UnreviewedEvidence, ...] = Field(min_length=1)
    rationale: Text


class ScoutOutput(Contract):
    candidates: tuple[Candidate, ...] = Field(max_length=3)
    insufficiency_reason: Text | None = None

    @model_validator(mode="after")
    def sufficient(self):
        if len(self.candidates) < 3 and self.insufficiency_reason is None:
            raise ValueError("insufficiency_reason_required")
        if len({c.candidate_id for c in self.candidates}) != len(self.candidates):
            raise ValueError("duplicate_candidate")
        return self


class FieldObservation(Contract):
    field: Literal["brand", "product", "variant", "price", "weight", "ingredients", "claims", "positioning", "audience", "channels", "packaging", "feedback", "news"]
    value: Text | None = None
    unavailable_reason: Text | None = None
    evidence: tuple[UnreviewedEvidence, ...] = ()

    @model_validator(mode="after")
    def observation_shape(self):
        if (self.value is None) == (self.unavailable_reason is None):
            raise ValueError("value_or_unavailable_required")
        if self.value is not None and not self.evidence:
            raise ValueError("observed_value_requires_evidence")
        return self


class ResearcherOutput(Contract):
    competitor_id: UUID
    sources: tuple[Source, ...]
    observations: tuple[FieldObservation, ...]
    limitations: tuple[Text, ...] = ()


class Opportunity(Contract):
    evidence_claim_ids: tuple[UUID, ...] = Field(min_length=1)
    rationale: Text
    potential_benefit: Text
    assumptions: tuple[Text, ...] = Field(min_length=1)
    next_step: Text
    status: Literal["hypothesis"] = "hypothesis"


class AnalystOutput(Contract):
    claims: tuple[AgentClaim, ...]
    opportunities: tuple[Opportunity, ...] = Field(max_length=5)
    insufficiency_reason: Text | None = None

    @model_validator(mode="after")
    def count_target(self):
        if len(self.opportunities) < 3 and self.insufficiency_reason is None:
            raise ValueError("opportunity_shortfall_requires_reason")
        return self


class ReviewerOutput(Contract):
    draft_version: Positive
    draft_hash: Digest
    decision: Literal["ready_for_human", "revise", "unresolved"]
    flagged_claim_ids: tuple[UUID, ...]
    limitations: tuple[Text, ...]
    # No field can grant human approval or mutate support adjudication authority.
