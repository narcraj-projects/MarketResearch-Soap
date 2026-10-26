"""Model narratives remain separate from deterministic observed facts/math."""
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class LiveSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class ScoutPick(LiveSchema):
    name: str = Field(min_length=1, max_length=300)
    source_ids: tuple[UUID, ...] = Field(min_length=1, max_length=3)
    product_quote: str = Field(min_length=1, max_length=600)
    geography_quote: str = Field(min_length=1, max_length=600)
    rationale: str = Field(min_length=1, max_length=700)


class ScoutPicks(LiveSchema):
    candidates: tuple[ScoutPick, ...] = Field(max_length=3)
    insufficiency_reason: str | None


class EvidenceNote(LiveSchema):
    text: str = Field(min_length=1, max_length=1000)
    source_ids: tuple[UUID, ...] = Field(min_length=1, max_length=5)
    kind: Literal["source_claim", "interpretation", "hypothesis"]


class ResearchDigest(LiveSchema):
    notes: tuple[EvidenceNote, ...] = Field(max_length=8)
    missing_information: tuple[str, ...] = Field(max_length=12)


class LiveOpportunity(LiveSchema):
    title: str = Field(min_length=1, max_length=180)
    rationale: str = Field(min_length=1, max_length=1200)
    premise_finding_ids: tuple[UUID, ...] = Field(min_length=1, max_length=12)
    assumptions: tuple[str, ...] = Field(min_length=1, max_length=5)
    next_step: str = Field(min_length=1, max_length=600)
    kind: Literal["hypothesis"] = "hypothesis"


class LiveSynthesis(LiveSchema):
    summary: str = Field(min_length=1, max_length=2000)
    notes: tuple[EvidenceNote, ...] = Field(max_length=9)
    opportunities: tuple[LiveOpportunity, ...] = Field(max_length=5)
    limitations: tuple[str, ...] = Field(min_length=1, max_length=12)
    insufficiency_reason: str | None


class LiveCritique(LiveSchema):
    decision: Literal["ready_for_human", "unresolved"]
    issues: tuple[str, ...] = Field(max_length=12)
    support_status: Literal["model_review_only_not_human_adjudicated"] = "model_review_only_not_human_adjudicated"


class LiveNarrative(LiveSchema):
    provider: str
    model: str
    prompt_version: Literal["live-pilot-1.0"] = "live-pilot-1.0"
    provisional_model: Literal[True] = True
    synthesis: LiveSynthesis
    critique: LiveCritique
