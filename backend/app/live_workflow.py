"""Live agents use the existing leased graph, evidence store and human interrupts."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from hashlib import sha256
import re
from uuid import UUID, uuid5

import httpx

from app.adapters.tavily import TavilyAdapter
from app.agents.scout import Discovery, Exclusion, Fit, RankedCandidate
from app.harness.contracts import RunContext, Versions
from app.harness.gateway import SearchGateway
from app.harness.live_models import LiveModelGateway
from app.harness.live_policy import CREDIT_USD, LivePermit, LiveSecrets
from app.harness.live_types import LiveNarrative, LiveSynthesis, LiveCritique, ScoutPicks, ResearchDigest
from app.harness.policy import PolicyDenied
from app.harness.retrieval import ResearchGateway
from app.harness.search import SearchCost
from app.harness.search_store import PostgresSearchLedger
from app.repository import digest
from app import models as m
from app.workflow import Workflow


class LiveTavilyAdapter(TavilyAdapter):
    def __init__(self, permit: LivePermit, *, transport=None):
        self.permit, self.mock, self.ordinal = permit, transport, 0

    def ensure_offline(self):
        raise PolicyDenied("live_adapter_requires_live_gateway")

    def _preflight(self, context: RunContext):
        if context.mode != "live":
            raise PolicyDenied("live_context_required")
        self.permit.check(context.run_id, context.user_id)
        if LiveSecrets().lather_tavily_api_key is None:
            raise PolicyDenied("tavily_key_missing")

    def _client(self, seconds):
        self.ordinal += 1
        from app.adapters.live_web import PinnedTavilyTransport
        return httpx.Client(transport=self.mock or PinnedTavilyTransport(), timeout=seconds, follow_redirects=False, trust_env=False)

    def _headers(self):
        key = LiveSecrets().lather_tavily_api_key
        if key is None:
            raise PolicyDenied("tavily_key_missing")
        return {"Authorization": "Bearer " + key.get_secret_value()}

    def observe_cached(self, call):
        pass


class LiveSearchGateway(SearchGateway):
    supplementary_query: str | None = None
    continuation_query: str | None = None
    def __init__(self, adapter, ledger, ranker, **kwargs):
        super().__init__(adapter, ledger, SearchCost(per_attempt_upper_bound_usd=CREDIT_USD, pricing_version="tavily-basic-1-credit-2026-10-26"), **kwargs)
        self.ranker = ranker

    def preflight(self, context):
        self.adapter._preflight(context)


class LiveResearchGateway(ResearchGateway):
    def attempt_cost(self, call):
        return CREDIT_USD if call.tool in {"public.news", "public.search"} else Decimal(0)

    def news(self, context, competitor_id, name):
        return self.search_evidence(context, competitor_id, name, product=True) + super().news(context, competitor_id, name)


class LiveScout:
    def __init__(self, models):
        self.models, self.cache = models, {}

    def __call__(self, brief, run_id, sources):
        # Candidate eligibility comes from literal public evidence, not currency,
        # domain suffix or model confidence. The model ranks only eligible sources.
        blocked = {"instagram.com", "facebook.com", "youtube.com", "amazon.com", "amazon.in", "etsy.com", "exportersindia.com", "tradewheel.com", "indiamart.com"}
        eligible = [s for s in sources if s.domain not in blocked and re.search(re.escape(brief.geography), s.excerpt, re.I)
            and re.search(r"\bsoap", s.excerpt, re.I) and not re.search(r"manufactur|private.label|/blogs?/|top-\d|buy.leads|/buyers", s.title + " " + s.canonical_url, re.I)]
        ordered = sorted(eligible, key=lambda row: str(row.source_id))
        key = digest([brief.model_dump(mode="json"), [row.model_dump(mode="json") for row in ordered]])
        if key in self.cache:
            return self.cache[key]
        if not ordered:
            return Discovery(label="LIVE", pool=(), candidates=(), excluded=(), insufficiency_reason="No first-party retail soap sources with explicit target-market text passed the evidence filter. No quota filler.")
        picks = ScoutPicks.model_validate(self.models.invoke("scout",
            "Select up to three distinct first-party retail handmade-soap brand websites relevant to Petite Batch's Indian consumer market."
            " Reject B2B-only/private-label contract manufacturers, directories, social media, marketplaces and generic lists."
            " A blog list mentioning other brands is not evidence that its host makes those products."
            " Names must appear verbatim in supplied title/excerpt. product_quote and geography_quote must be exact substrings of one cited excerpt."
            " Do not manufacture a third candidate. Explain insufficiency when fewer than three.",
            {"brief": brief.model_dump(mode="json"), "sources": [{"id": str(s.source_id), "url": s.canonical_url, "domain": s.domain, "title": s.title, "excerpt": s.excerpt[:1800]} for s in ordered]}, ScoutPicks.model_json_schema()))
        pool, used = [], set()
        by_id = {s.source_id: s for s in sources}
        for pick in picks.candidates:
            refs = [by_id[sid] for sid in pick.source_ids if sid in by_id]
            if len(refs) != len(pick.source_ids) or not refs or len({s.domain for s in refs}) != 1:
                raise PolicyDenied("scout_source_scope_invalid")
            source = refs[0]
            if source.domain in used or source.domain in {"amazon.in", "flipkart.com", "indiamart.com", "justdial.com", "youtube.com", "instagram.com"}:
                continue
            if not any(pick.name.casefold() in (s.title + " " + s.excerpt).casefold() for s in refs):
                raise PolicyDenied("unsubstantiated_live_identity")
            product_match = next((re.search(r"[^.\n]{0,70}\bsoaps?\b[^.\n]{0,70}", s.excerpt, re.I) for s in refs if re.search(r"\bsoap", s.excerpt, re.I)), None)
            geography_match = next((re.search(re.escape(brief.geography), s.excerpt, re.I) for s in refs if re.search(re.escape(brief.geography), s.excerpt, re.I)), None)
            if not product_match or not geography_match:
                continue
            used.add(source.domain)
            fits = (Fit(dimension="product", status="match", quote=product_match[0], rationale="Exact soap wording independently located in the cited excerpt."),
                Fit(dimension="geography", status="partial", quote=geography_match[0], rationale="Exact target-market wording independently located in the cited excerpt; delivery still needs founder review."),
                *(Fit(dimension=dimension, status="unknown", quote=None, rationale="Not independently established from discovery evidence.") for dimension in ("customer", "price", "channel")))
            pool.append(RankedCandidate(candidate_id=uuid5(run_id, "candidate:" + source.domain), name=pick.name, canonical_url=source.canonical_url,
                domain=source.domain, source_ids=pick.source_ids, excerpt_hash=sha256(source.excerpt.encode()).hexdigest(), fits=fits,
                score=Decimal("1.5"), known_dimensions=2, rationale=pick.rationale + " Provisional model relevance interpretation; inspect sources before approval."))
        selected_ids = {sid for candidate in pool for sid in candidate.source_ids}
        result = Discovery(label="LIVE", pool=tuple(pool), candidates=tuple(pool), excluded=tuple(Exclusion(source_id=s.source_id, reason="unsubstantiated_identity") for s in sources if s.source_id not in selected_ids),
            insufficiency_reason=(picks.insufficiency_reason or "Fewer than three source-backed candidates passed validation; no quota filler.") if len(pool) < 3 else None)
        self.cache[key] = result
        return result


class LiveWorkflow(Workflow):
    def __init__(self, engine, lease, deadline, scout, web, *, permit):
        super().__init__(engine, lease, deadline, scout, web)
        self.label, self.permit = "LIVE", permit
        self.models = LiveModelGateway(engine, lease, permit)
        self.ranker = LiveScout(self.models)
        self.search_store = PostgresSearchLedger(engine, lease, ranker=self.ranker)

    def scout_versions(self):
        return Versions(graph="scout-1.0", model=self.permit.model, provider=self.permit.provider, prompt="live-pilot-1.0", tools="tavily-search-1.0", dataset="live-public-1.0")

    def research_versions(self):
        return self.scout_versions().model_copy(update={"graph": "research-1.0", "tools": "public-research-1.0"})

    def discovery_gateway(self):
        gateway = LiveSearchGateway(self.scout, self.search_store, self.ranker, guard=lambda: self.lease.check(self.engine))
        gateway.supplementary_query = self.permit.supplementary_query
        gateway.continuation_query = self.permit.continuation_query
        return gateway

    def research_gateway(self):
        return LiveResearchGateway(self.web, self.research_store, guard=lambda: self.lease.check(self.engine))

    def research(self, state):
        result = super().research(state)
        with self.transaction() as repo:
            tasks = repo.list(m.research_tasks, self.lease.run_id, limit=3)
            supplement = (repo.get(m.runs, self.lease.run_id)["checkpoint"].get("live_evidence_supplement") or {}).get("lanes", {})
            tasks = [dict(task) | {"data": supplement.get(str(task["competitor_id"]), task["data"])} for task in tasks]
        def summarize(task):
            docs = task["data"]["sources"]
            usable = [s for s in docs if s["access_status"] == "ok" and s.get("excerpt") and s["evidence_kind"] != "robots_policy"]
            usable.sort(key=lambda s: (bool(re.search(r"soap|/product-page/", s["canonical_url"], re.I)), s["retrieved_at"]), reverse=True)
            note = ResearchDigest.model_validate(self.models.invoke("researcher",
                "Extract source-attributed notes on pricing, core products/features, positioning, channels and dated news."
                " Cite only provided source_ids, distinguish interpretation from source claims, and explicitly list missing information."
                " Structured products and arithmetic are validated separately by code; do not infer weights or prices.",
                {"competitor_id": str(task["competitor_id"]), "sources": [{"id": s["source_id"], "url": s["canonical_url"], "title": s["title"], "excerpt": s["excerpt"][:1800], "retrieved_at": s["retrieved_at"]} for s in usable[:8]],
                    "structured_products": [product for page in task["data"]["pages"][:3] for product in page["products"][:2]]}, ResearchDigest.model_json_schema()))
            allowed = {UUID(s["source_id"]) for s in usable}
            if any(not set(row.source_ids) <= allowed for row in note.notes):
                raise PolicyDenied("researcher_citation_invalid")
            return note
        with ThreadPoolExecutor(max_workers=3) as pool:
            tuple(pool.map(summarize, tasks))
        return result

    def draft(self, state):
        if state.revision == 3:
            from app.services.live_correction import corrected_draft
            return corrected_draft(self, state)
        data = super().draft(state)
        analysis = data["analysis"]
        known = [row for row in analysis["findings"] if row["value"] is not None and row["evidence"]]
        chosen = []
        for comparison in analysis["comparisons"]:
            for field in ("product", "price", "weight_g", "ingredients", "marketing_claim", "positioning", "channels", "public_review"):
                candidate = next((row for row in known if row["competitor_id"] == comparison["competitor_id"] and row["field"] == field), None)
                if candidate:
                    chosen.append(candidate)
        selected = [{"finding_id": row["finding_id"], "competitor_id": row["competitor_id"], "field": row["field"], "kind": row["kind"], "value": str(row["value"])[:500],
            "evidence": [{"source_id": ref["source_id"], "quote": ref["quote"][:500]} for ref in row["evidence"][:2]]} for row in chosen]
        with self.transaction() as repo:
            receipts = repo.list(m.tool_attempts, self.lease.run_id, limit=10000)
            researcher_notes = [row["outcome"]["output"] for row in receipts if row["outcome"] and row["outcome"].get("role") == "researcher" and row["outcome"].get("output")][-len(analysis["comparisons"]):]
            rows = repo.list(m.sources, self.lease.run_id, limit=1000)
        provided_ids = {str(ref["source_id"]) for row in selected for ref in row["evidence"]}
        provided_ids |= {sid for digest_row in researcher_notes for note in digest_row["notes"] for sid in note["source_ids"]}
        model_sources = [{"source_id": str(row["id"]), "url": row["canonical_url"], "excerpt": (row["excerpt"] or "")[:3000]}
            for row in rows if str(row["id"]) in provided_ids and row["access_status"] == "ok" and row["excerpt"]]
        allowed_source_ids = sorted({row["source_id"] for row in model_sources})
        synthesis_schema = LiveSynthesis.model_json_schema()
        synthesis_schema["$defs"]["EvidenceNote"]["properties"]["source_ids"]["items"]["enum"] = allowed_source_ids
        synthesis_schema["$defs"]["LiveOpportunity"]["properties"]["premise_finding_ids"]["items"]["enum"] = [row["finding_id"] for row in selected]
        if not selected:
            synthesis_schema["properties"]["opportunities"]["maxItems"] = 0
        if not allowed_source_ids:
            synthesis_schema["properties"]["notes"]["maxItems"] = 0
        raw = self.models.invoke("analyst",
            "Write a grounded competitor briefing and 3-5 testable opportunity hypotheses only when the supplied evidence permits."
            " Every note must cite supplied source IDs; each opportunity must cite finding IDs. Do not introduce new facts,"
            " clinical efficacy, market share or unstated prices. Explain missing data and fewer than three opportunities.",
            {"revision": state.revision, "required_corrections": state.issues, "competitors": [{"id": row["competitor_id"], "name": row["name"]} for row in analysis["comparisons"]], "sampled_findings": selected,
                "researcher_notes": researcher_notes, "source_excerpts": model_sources,
                "sample_note": f"Only {len(selected)} of {len(known)} known findings are supplied to the model; full deterministic findings remain in the report."}, synthesis_schema)
        synthesis = LiveSynthesis.model_validate(raw)
        source_ids = {UUID(row["source_id"]) for row in model_sources} | {UUID(ref["source_id"]) for row in selected for ref in row["evidence"]}
        finding_ids = {UUID(row["finding_id"]) for row in selected}
        if any(not set(row.source_ids) <= source_ids for row in synthesis.notes) or any(not set(row.premise_finding_ids) <= finding_ids for row in synthesis.opportunities):
            raise PolicyDenied("analyst_citation_invalid")
        if len(synthesis.opportunities) < 3 and not synthesis.insufficiency_reason:
            raise PolicyDenied("analyst_shortfall_unexplained")
        critique = LiveCritique.model_validate(self.models.invoke("reviewer",
            "Independently check the proposed briefing against the supplied atomic findings and evidence quotes."
            " Reject unsupported factual premises, wrong-source citations, invented prices or medical efficacy."
            " Return ready_for_human only when no material unsupported statement is identified. This is not human adjudication.",
            {"synthesis": synthesis.model_dump(mode="json"), "findings": selected, "source_excerpts": model_sources}, LiveCritique.model_json_schema()))
        narrative = LiveNarrative(provider=self.permit.provider, model=self.permit.model, synthesis=synthesis, critique=critique)
        data["live_narrative"] = narrative.model_dump(mode="json")
        data["presentation"]["live_narrative"] = narrative.model_dump(mode="json")
        data["presentation"]["coverage"] |= {"citation_presence": None, "quote_coverage": None,
            "denominator_definition": "Structured deterministic findings are counted below. AI prose/notes have not been fully atomized or human-adjudicated; overall report claim coverage is unmeasured. No >=90% acceptance pass is claimed."}
        data["methodology"] |= {"provider": self.permit.provider, "model": self.permit.model, "prompt_version": "live-pilot-1.0", "provisional_model": True,
            "roles": ["scout", "researcher", "analyst", "reviewer"], "orchestrator": "deterministic LangGraph", "benchmark": "not_completed"}
        return data

    def review(self, state):
        result = super().review(state)
        with self.transaction() as repo:
            report = repo.get(m.reports, UUID(state.report_id))
        critique = report["data"]["live_narrative"]["critique"]
        if critique["decision"] != "ready_for_human" or critique["issues"]:
            result |= {"review_ok": False, "review_decision": "revise" if state.revision < state.revision_limit else "unresolved", "issues": ["live_narrative"]}
        return result
