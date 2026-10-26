"""Conservative deterministic soap Scout, with no model-selected identities."""
from __future__ import annotations
from decimal import Decimal
from hashlib import sha256
import re
from typing import TYPE_CHECKING, Literal
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from app.api_schemas import BriefCreate
from app.harness.contracts import Contract
from app.harness.search import SearchSource

SCORER_VERSION = "soap-scout-1.0"


class Fit(Contract):
    dimension: Literal["product", "customer", "geography", "price", "channel"]
    status: Literal["match", "partial", "unknown", "no_match"]
    quote: str | None = Field(default=None, max_length=1000)
    rationale: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def evidence(self):
        if (self.status == "unknown") != (self.quote is None):
            raise ValueError("fit_quote_required")
        return self


class RankedCandidate(Contract):
    candidate_id: UUID
    name: str = Field(min_length=1, max_length=300)
    canonical_url: str
    domain: str
    source_ids: tuple[UUID, ...] = Field(min_length=1)
    excerpt_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    fits: tuple[Fit, ...] = Field(min_length=5, max_length=5)
    score: Decimal = Field(ge=0, le=5)
    known_dimensions: int = Field(ge=0, le=5)
    rationale: str
    classification: Literal["interpretation"] = "interpretation"


class Exclusion(Contract):
    source_id: UUID
    reason: Literal["unsubstantiated_identity", "irrelevant_product", "not_a_maker", "geography_unconfirmed", "duplicate_domain"]


class Discovery(Contract):
    label: Literal["DEMO", "LIVE"] = "DEMO"
    scorer_version: Literal["soap-scout-1.0"] = "soap-scout-1.0"
    pool: tuple[RankedCandidate, ...]
    candidates: tuple[RankedCandidate, ...] = Field(max_length=3)
    excluded: tuple[Exclusion, ...]
    insufficiency_reason: str | None

    @model_validator(mode="after")
    def selection(self):
        by_id = {candidate.candidate_id: candidate for candidate in self.pool}
        if len(by_id) != len(self.pool) or len({c.domain for c in self.pool}) != len(self.pool):
            raise ValueError("duplicate_candidate")
        if len({c.candidate_id for c in self.candidates}) != len(self.candidates):
            raise ValueError("duplicate_selection")
        if any(by_id.get(c.candidate_id) != c for c in self.candidates):
            raise ValueError("invented_candidate")
        if len(self.candidates) < 3 and not self.insufficiency_reason:
            raise ValueError("insufficiency_required")
        return self


class DiscoveryArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    schema_version: Literal["scout-1.0"] = "scout-1.0"
    label: Literal["DEMO", "LIVE"] = "DEMO"
    discovery: Discovery
    competitor_ids: tuple[UUID, ...] = Field(max_length=3)
    insufficiency_reason: str | None
    stop_reason: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def ids_match(self):
        if self.competitor_ids != tuple(c.candidate_id for c in self.discovery.candidates) or self.insufficiency_reason != self.discovery.insufficiency_reason:
            raise ValueError("artifact_selection_mismatch")
        return self


def _quote(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, re.IGNORECASE)
    return match[0] if match else None


def rank(brief: BriefCreate, run_id: UUID, sources: tuple[SearchSource, ...]) -> Discovery:
    """Identity is an exact title string ALSO present in a maker's snippet.

    Snippet similarity is candidate relevance evidence, not verified brand facts.
    Unknown fields contribute no points but have a separate known-dimension count.
    """
    pool: dict[str, RankedCandidate] = {}
    excluded = []
    for source in sources:
        name = re.split(r"\s(?:\||—|–|-)\s", source.title, maxsplit=1)[0].strip()
        reason = None
        if len(name) > 300 or not name or not re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", source.excerpt, re.IGNORECASE):
            reason = "unsubstantiated_identity"
        product = _quote(r"\b(?:handmade|cold[ -]process)\s+soap(?:s|\s+bars)?\b", source.excerpt)
        if not product:
            reason = reason or "irrelevant_product"
        if not _quote(r"\b(?:soap maker|artisan maker|we make|manufacturer)\b", source.excerpt) or _quote(r"\b(?:reseller|directory|marketplace|unrelated|not a maker)\b", source.excerpt):
            reason = reason or "not_a_maker"
        # Geography is literal evidence, not inferred from domain, currency or name.
        geography_terms = [part.strip() for part in brief.geography.split(",") if part.strip() and part.strip().lower() != "online-first"]
        geography = next((found for term in geography_terms if (found := _quote(r"\b" + re.escape(term) + r"\b", source.excerpt))), None)
        if not geography:
            reason = reason or "geography_unconfirmed"
        if reason:
            excluded.append(Exclusion.model_validate(dict(source_id=source.source_id, reason=reason)))
            continue
        stopwords = {"demo", "target", "customer", "customers", "shoppers", "buyers", "with", "and", "for", "the"}
        customer_terms = sorted({t for t in re.findall(r"[a-z]{3,}", brief.customer.lower()) if t not in stopwords})
        customer_matches = [q for term in customer_terms if (q := _quote(r"\b" + re.escape(term) + r"\b", source.excerpt))]
        customer_quote = " ".join(customer_matches) if customer_matches else None
        # Noncontiguous terms remain separate evidence; the rationale never presents this as a verbatim sentence.
        if customer_quote and customer_quote not in source.excerpt:
            customer_quote = customer_matches[0]
        segment = brief.preferences.price_segment
        price = None if segment == "Let agent find out" else _quote(re.escape(segment), source.excerpt)
        channel = _quote(r"\b(?:online|direct to consumer|own website)\b", source.excerpt)
        customer_status: Literal["match", "partial", "unknown"] = "match" if customer_terms and len(customer_matches) == len(customer_terms) else "partial" if customer_matches else "unknown"
        fits = (
            Fit(dimension="product", status="match", quote=product, rationale="Explicit handmade/cold-process soap wording."),
            Fit(dimension="customer", status=customer_status, quote=customer_quote, rationale="Literal brief terms overlap; unknown means no matching audience evidence."),
            Fit(dimension="geography", status="match", quote=geography, rationale="Target market is explicitly mentioned; delivery still needs human verification."),
            Fit(dimension="price", status="match" if price else "unknown", quote=price, rationale="Only an explicit segment label counts; no price band is inferred."),
            Fit(dimension="channel", status="match" if channel else "unknown", quote=channel, rationale="Online-channel evidence for this online-first MVP; other channels remain unknown."),
        )
        score = sum((Decimal(1) if f.status == "match" else Decimal("0.5") if f.status == "partial" else Decimal(0) for f in fits), Decimal(0))
        candidate = RankedCandidate(candidate_id=uuid5(run_id, "candidate:" + source.domain), name=name, canonical_url=source.canonical_url,
            domain=source.domain, source_ids=(source.source_id,), excerpt_hash=sha256(source.excerpt.encode()).hexdigest(), fits=fits, score=score,
            known_dimensions=sum(f.status != "unknown" for f in fits),
            rationale="Search snippet names this maker and explicitly mentions matching soap and target market. " +
                "; ".join(f"{f.dimension}: {f.status}" for f in fits) + ". Unreviewed discovery interpretation; verify identity, delivery and source support before deeper research.")
        previous = pool.get(source.domain)
        if previous:
            excluded.append(Exclusion(source_id=source.source_id, reason="duplicate_domain"))
            if candidate.score > previous.score:
                pool[source.domain] = candidate
        else:
            pool[source.domain] = candidate
    ordered = tuple(sorted(pool.values(), key=lambda c: (-c.score, c.domain, c.name)))
    return Discovery(pool=ordered, candidates=ordered[:3], excluded=tuple(excluded),
        insufficiency_reason=f"Only {len(ordered)} search-backed maker candidates met product, identity and market checks; no quota filler. Clarify the brief or approve fewer." if len(ordered) < 3 else None)
