"""Owner-bound research transactions; parallel lanes share budgets, never evidence state."""
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
import json
from threading import BoundedSemaphore, Lock
from weakref import WeakKeyDictionary
from uuid import UUID, uuid5

from sqlalchemy import Engine, insert, select, text, update

from app import models as m
from app.agents.extraction import canonical, contradictions, extract
from app.agents.normalization import normalize_price
from app.agents.snippet_extraction import eligible
from app.repository import Repository, digest, owner_transaction
from .contracts import Approval, Budget, Phase, RunContext, Versions
from .policy import PolicyDenied
from .lease import Lease
from .research_types import CompetitorResearch, ResearchCall, RetrievedSource, WireOutcome
from .web_policy import safe_url
from .search_store import PostgresSearchLedger

# Session advisory locks need connections throughout a lane. Bound them across
# ALL runs sharing an engine, leaving transaction/heartbeat capacity in the pool.
_lane_slots: WeakKeyDictionary = WeakKeyDictionary()
_lane_slots_lock = Lock()


class ResearchStore:
    def __init__(self, engine: Engine, lease: Lease | None = None):
        self.engine, self.lease = engine, lease
        with _lane_slots_lock:
            self.lane_slots = _lane_slots.setdefault(engine, BoundedSemaphore(3))

    def _approved(self, repo: Repository, run: dict, competitor_id: UUID | None = None) -> tuple[dict, dict]:
        checkpoint = run["checkpoint"] or {}
        if run["status"] != "researching" or checkpoint.get("schema_version") != "scout-1.0":
            raise PolicyDenied("shortlist_approval_required")
        request = repo.get(m.approval_requests, UUID(checkpoint["request_id"]))
        decision = repo.conn.execute(select(m.approval_decisions).where(m.approval_decisions.c.request_id == request["id"],
            m.approval_decisions.c.owner_id == repo.owner)).mappings().first()
        if (not decision or decision["decision"] != "approve" or request["state"] != "decided" or request["gate"] != "shortlist"
            or request["artifact_hash"] != checkpoint["artifact_hash"] or request["artifact_hash"] != digest(request["artifact"])
            or request["artifact_version"] != checkpoint["artifact_version"] or decision["artifact_hash"] != request["artifact_hash"]):
            raise PolicyDenied("shortlist_approval_required")
        if competitor_id is not None and str(competitor_id) not in request["artifact"]["competitor_ids"]:
            raise PolicyDenied("competitor_not_approved")
        return request, dict(decision)

    def begin(self, run_id: UUID, owner_id: UUID, deadline: datetime, versions: Versions) -> tuple[RunContext, tuple[dict, ...]]:
        with owner_transaction(self.engine, owner_id) as repo:
            run = PostgresSearchLedger.locked(repo, run_id, self.lease)
            request, decision = self._approved(repo, run)
            checkpoint = dict(run["checkpoint"])
            approved_ids = tuple(UUID(value) for value in request["artifact"]["competitor_ids"])
            competitors = tuple(repo.get(m.competitors, cid) for cid in approved_ids)
            state = checkpoint.get("research")
            if state is None:
                deadline = min(deadline, datetime.fromisoformat(checkpoint["deadline"]))
                state = {"schema_version": "research-1.0", "deadline": deadline.isoformat(), "versions": versions.model_dump(mode="json"),
                    "state": "researching", "competitor_ids": [str(cid) for cid in approved_ids]}
                checkpoint["research"] = state
                repo.conn.execute(update(m.runs).where(m.runs.c.id == run_id).values(checkpoint=checkpoint, version=run["version"] + 1))
                run["version"] += 1
                repo.event(run_id, "research.started", {"agent": "researcher", "label": "DEMO", "lanes": len(competitors)})
            if state["versions"] != versions.model_dump(mode="json") or state["competitor_ids"] != [str(cid) for cid in approved_ids]:
                raise PolicyDenied("research_checkpoint_mismatch")
            approval = Approval(request_id=request["id"], decision_id=decision["id"], run_id=run_id, owner_id=owner_id,
                artifact_hash=request["artifact_hash"], artifact_version=request["artifact_version"], gate="shortlist", decision="approve", decided_at=decision["created_at"])
            attempts = repo.conn.execute(select(m.tool_attempts).where(m.tool_attempts.c.run_id == run_id, m.tool_attempts.c.owner_id == owner_id)).mappings().all()
            usage = repo.conn.execute(select(m.usage).where(m.usage.c.run_id == run_id, m.usage.c.owner_id == owner_id)).mappings().all()
            keys = {(a["operation_id"], a["attempt"]) for a in attempts}
            other = [u for u in usage if (u["operation_id"], u["attempt"]) not in keys]
            completed = [a for a in attempts if a["state"] == "completed"]
            reserved = [a for a in attempts if a["state"] == "reserved"]
            budget = Budget(max_calls=run["budget"]["max_calls"], max_tokens=run["budget"]["max_tokens"], max_cost=run["budget"]["max_cost_usd"],
                used_calls=len(completed) + sum(u["calls"] for u in other), reserved_calls=len(reserved), used_tokens=sum(u["tokens"] for u in usage),
                used_cost=sum((a["cost_upper_bound_usd"] for a in completed), Decimal(0)) + sum((u["cost_usd"] for u in other), Decimal(0)),
                reserved_cost=sum((a["cost_upper_bound_usd"] for a in reserved), Decimal(0)))
            return RunContext(mode="live" if versions.dataset.startswith("live-") else "replay", live_authorization_id=uuid5(run_id, "live-permit-1.0") if versions.dataset.startswith("live-") else None,
                run_id=run_id, user_id=owner_id, trace_id=checkpoint["trace_id"], brief_version=repo.get(m.briefs, run["brief_id"])["version"],
                run_version=run["version"], versions=versions, phase=Phase.RESEARCH, deadline=datetime.fromisoformat(state["deadline"]),
                budget=budget,
                shortlist_hash=request["artifact_hash"], shortlist_version=request["artifact_version"], approvals=(approval,)), competitors

    def _active(self, repo: Repository, context: RunContext, cid: UUID, now: datetime, *, completion=False) -> dict:
        run = PostgresSearchLedger.locked(repo, context.run_id, self.lease)
        request, decision = self._approved(repo, run, cid)
        state = (run["checkpoint"] or {}).get("research") or {}
        if (run["version"] != context.run_version or state.get("versions") != context.versions.model_dump(mode="json")
            or state.get("deadline") != context.deadline.isoformat() or context.shortlist_hash != request["artifact_hash"]
            or len(context.approvals) != 1 or context.approvals[0].decision_id != decision["id"] or context.phase != Phase.RESEARCH):
            raise PolicyDenied("stale_research_context")
        if not completion and now >= context.deadline:
            raise PolicyDenied("deadline")
        return run

    @contextmanager
    def lane(self, context: RunContext, competitor_id: UUID):
        timeout = min(10.0, max(0.0, (context.deadline - datetime.now(context.deadline.tzinfo)).total_seconds()))
        if not self.lane_slots.acquire(timeout=timeout):
            raise PolicyDenied("research_capacity")
        try:
            with self._locked_lane(context, competitor_id):
                yield
        finally:
            self.lane_slots.release()

    @contextmanager
    def _locked_lane(self, context: RunContext, competitor_id: UUID):
        with owner_transaction(self.engine, context.user_id) as repo:
            self._active(repo, context, competitor_id, datetime.now(context.deadline.tzinfo))
        key = int.from_bytes(sha256(f"{context.user_id}:{context.run_id}:{competitor_id}".encode()).digest()[:8], "big", signed=True)
        # Session lock, NOT an open database transaction during HTTP. A dead process releases its connection/lock.
        with self.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            if not conn.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}).scalar_one():
                raise PolicyDenied("research_lane_busy")
            try:
                yield
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})

    def reserve(self, context: RunContext, call: ResearchCall, attempt: int, fingerprint: str, cost: Decimal, now: datetime) -> WireOutcome | None:
        with owner_transaction(self.engine, context.user_id) as repo:
            run = self._active(repo, context, call.competitor_id, now)
            rows = repo.conn.execute(select(m.tool_attempts).where(m.tool_attempts.c.run_id == context.run_id, m.tool_attempts.c.owner_id == context.user_id)).mappings().all()
            if context.mode == "live":
                from .live_policy import load_permit, enforce_credit_cap
                enforce_credit_cap(rows, load_permit(context.run_id, context.user_id), cost)
            for row in rows:
                if row["operation_id"] == call.operation_id and row["attempt"] == attempt:
                    if row["request_hash"] != fingerprint:
                        raise PolicyDenied("operation_payload_conflict")
                    if row["state"] == "reserved":
                        raise PolicyDenied("uncertain_attempt")
                    return WireOutcome.model_validate(row["outcome"])
            usage = repo.conn.execute(select(m.usage).where(m.usage.c.run_id == context.run_id, m.usage.c.owner_id == context.user_id)).mappings().all()
            keys = {(r["operation_id"], r["attempt"]) for r in rows}
            other = [u for u in usage if (u["operation_id"], u["attempt"]) not in keys]
            if (len(rows) + sum(u["calls"] for u in other) + 1 > run["budget"]["max_calls"]
                or sum((r["cost_upper_bound_usd"] for r in rows), Decimal(0)) + sum((u["cost_usd"] for u in other), Decimal(0)) + cost > Decimal(run["budget"]["max_cost_usd"])
                or sum(u["tokens"] for u in usage) > run["budget"]["max_tokens"]):
                raise PolicyDenied("budget")
            repo.conn.execute(insert(m.tool_attempts).values(id=uuid5(context.run_id, f"research:{call.operation_id}:{attempt}"), owner_id=context.user_id,
                run_id=context.run_id, operation_id=call.operation_id, attempt=attempt, request_hash=fingerprint, cost_upper_bound_usd=cost, state="reserved", outcome=None))
            repo.event(context.run_id, "tool.reserved", {"agent": "researcher", "tool": call.tool, "operation_id": str(call.operation_id), "attempt": attempt, "label": "DEMO"})
            return None

    def _put_source(self, repo: Repository, run_id: UUID, source: RetrievedSource) -> None:
        prior = repo.conn.execute(select(m.sources).where(m.sources.c.id == source.source_id, m.sources.c.owner_id == repo.owner)).mappings().first()
        if prior:
            document = repo.conn.execute(select(m.source_documents).where(m.source_documents.c.source_id == source.source_id, m.source_documents.c.owner_id == repo.owner)).mappings().one()
            if (prior["run_id"] != run_id or prior["canonical_url"] != source.canonical_url or prior["content_hash"] != source.content_hash
                or document["body"] != source.body or document["excerpt"] != source.excerpt or document["structured"] != list(source.structured)):
                raise PolicyDenied("source_payload_conflict")
            return
        # Ingress comes from the journal, never a proposed agent/model source object.
        if source.access_status == "ok":
            recorded = False
            outcomes = repo.conn.execute(select(m.tool_attempts.c.outcome).where(m.tool_attempts.c.run_id == run_id,
                m.tool_attempts.c.owner_id == repo.owner, m.tool_attempts.c.state == "completed")).scalars()
            for data in outcomes:
                if not isinstance(data, dict) or data.get("schema_version") != "research-1.0":
                    continue
                outcome = WireOutcome.model_validate(data)
                if outcome.competitor_id != source.competitor_id:
                    continue
                if outcome.source and outcome.source == source:
                    recorded = True
                if source.evidence_kind == "search_snippet" and outcome.reply.status == 200 and outcome.reply.body:
                    try:
                        response = json.loads(outcome.reply.body)
                        for hit in response.get("results", []):
                            if isinstance(hit, dict) and hit.get("content") == source.body and safe_url(hit.get("url", "")) == source.canonical_url:
                                recorded = True
                    except (ValueError, TypeError, PolicyDenied):
                        pass
            if not recorded:
                raise PolicyDenied("unrecorded_source_payload")
        repo.conn.execute(insert(m.sources).values(id=source.source_id, owner_id=repo.owner, run_id=run_id, canonical_url=source.canonical_url,
            title=source.title, publisher=source.publisher, retrieved_at=source.retrieved_at, content_hash=source.content_hash,
            access_status=source.access_status, excerpt=source.excerpt, evidence_kind=source.evidence_kind))
        repo.conn.execute(insert(m.source_documents).values(id=uuid5(source.source_id, "document"), owner_id=repo.owner, run_id=run_id, source_id=source.source_id,
            body=source.body, excerpt=source.excerpt, text_hash=source.text_hash, structured=list(source.structured), links=list(source.links), reason=source.reason))

    def complete(self, context: RunContext, call: ResearchCall, attempt: int, fingerprint: str, outcome: WireOutcome, now: datetime) -> None:
        outcome = WireOutcome.model_validate(outcome.model_dump())
        with owner_transaction(self.engine, context.user_id) as repo:
            self._active(repo, context, call.competitor_id, now, completion=True)
            row_id = uuid5(context.run_id, f"research:{call.operation_id}:{attempt}")
            row = repo.get(m.tool_attempts, row_id)
            if row["state"] != "reserved" or row["request_hash"] != fingerprint or outcome.competitor_id != call.competitor_id:
                raise PolicyDenied("stale_attempt")
            # Mark the typed wire outcome complete inside this transaction before source ingress resolution.
            repo.conn.execute(update(m.tool_attempts).where(m.tool_attempts.c.id == row_id, m.tool_attempts.c.owner_id == context.user_id).values(state="completed", outcome=outcome.model_dump(mode="json")))
            if outcome.source:
                if (outcome.source.competitor_id != call.competitor_id or outcome.source.canonical_url != call.url
                    or (outcome.source.access_status == "ok" and outcome.source.body != outcome.reply.body)):
                    raise PolicyDenied("cross_competitor_source")
                self._put_source(repo, context.run_id, outcome.source)
            repo.create(m.usage, {"run_id": context.run_id, "operation_id": call.operation_id, "attempt": attempt, "calls": 1, "tokens": 0, "cost_usd": row["cost_upper_bound_usd"]})
            repo.event(context.run_id, "tool.completed", {"agent": "researcher", "tool": call.tool, "operation_id": str(call.operation_id), "attempt": attempt,
                "status": outcome.reply.status, "code": outcome.reply.failure or "received"})
            if outcome.reply.status in {429, 500, 502, 503, 504} or outcome.reply.failure == "timeout":
                repo.event(context.run_id, "tool.retryable_failure", {"tool": call.tool, "agent": "researcher", "attempt": attempt,
                    "code": outcome.reply.failure or str(outcome.reply.status), "retry_limit": 3, "label": "DEMO"})
            if outcome.reply.status == 200 and attempt > 1:
                repo.event(context.run_id, "tool.recovered", {"tool": call.tool, "agent": "researcher", "attempt": attempt, "label": "DEMO"})

    def cached_task(self, context: RunContext, cid: UUID) -> CompetitorResearch | None:
        with owner_transaction(self.engine, context.user_id) as repo:
            self._active(repo, context, cid, context.deadline, completion=True)
            row = repo.conn.execute(select(m.research_tasks).where(m.research_tasks.c.run_id == context.run_id,
                m.research_tasks.c.owner_id == context.user_id, m.research_tasks.c.competitor_id == cid)).mappings().first()
            return CompetitorResearch.model_validate(row["data"]) if row else None

    def save_task(self, context: RunContext, cid: UUID, sources: tuple[RetrievedSource, ...], limitations: tuple[str, ...]) -> CompetitorResearch:
        with owner_transaction(self.engine, context.user_id) as repo:
            self._active(repo, context, cid, context.deadline, completion=True)
            competitor = repo.get(m.competitors, cid)
            from .urls import normalize_url
            domain = normalize_url(competitor["canonical_url"], demo=True)[1]
            unique = {source.source_id: RetrievedSource.model_validate(source.model_dump()) for source in sources}
            for source in unique.values():
                if source.competitor_id != cid:
                    raise PolicyDenied("cross_competitor_source")
                self._put_source(repo, context.run_id, source)
            pages = tuple(extract(source, competitor["name"], first_party=normalize_url(source.canonical_url, demo=True)[1] == domain)
                for source in unique.values() if source.evidence_kind == "page_excerpt" or eligible(source, normalize_url(source.canonical_url, demo=True)[1] == domain))
            for page in pages:
                observations = list(page.observations)
                for index, product in enumerate(page.products):
                    pid = uuid5(cid, f"product:{product.source_id}:{product.locator}:{index}")
                    repo.conn.execute(insert(m.products).values(id=pid, owner_id=context.user_id, run_id=context.run_id, competitor_id=cid, sku=product.sku,
                        name=product.name, ingredients=list(product.ingredients) if product.ingredients is not None else None,
                        attributes={"label": "DEMO", "source_id": str(product.source_id), "variant": product.variant, "weight_g": str(product.weight_g) if product.weight_g is not None else None,
                            "weight_basis": product.weight_basis, "pack_qty": product.pack_qty, "observations": [o.model_dump(mode="json") for o in product.observations]}))
                    if product.amount is not None and product.currency is not None:
                        normalized = normalize_price(cid, product, unique[product.source_id])
                        repo.create(m.prices, {"run_id": context.run_id, "product_id": pid, "source_id": product.source_id, "amount": product.amount, "currency": product.currency,
                            "total_weight_g": normalized.total_weight_g, "pack_qty": product.pack_qty, "observed_at": unique[product.source_id].retrieved_at,
                            "normalization_data": {"schema_version": "normalization-1.0", "eligible": normalized.unit_price_100g is not None, "observation": normalized.model_dump(mode="json")}})
                    observations.extend(product.observations)
                for index, observation in enumerate(observations):
                    if observation.value is None:
                        continue
                    for evidence in observation.evidence:
                        evidence_source = unique.get(evidence.source_id)
                        if (evidence_source is None or evidence_source.access_status != "ok" or not evidence_source.excerpt or evidence.quote not in evidence_source.excerpt
                            or sha256(evidence.quote.encode()).hexdigest() != evidence.quote_hash):
                            raise PolicyDenied("claim_evidence_mismatch")
                    claim = repo.create(m.claims, {"run_id": context.run_id, "text": observation.field + ": " + canonical(observation.value),
                        "kind": observation.kind, "material": True, "review_status": "flagged" if observation.kind == "competitor_marketing_claim" else "unreviewed"})
                    for evidence in observation.evidence:
                        repo.create(m.claim_sources, {"run_id": context.run_id, "claim_id": claim["id"], "source_id": evidence.source_id, "quote": evidence.quote, "excerpt_hash": evidence.quote_hash, "locator": evidence.locator})
            limitations = tuple(dict.fromkeys([*limitations, *(limit for page in pages for limit in page.limitations),
                *(source.reason for source in unique.values() if source.reason)]))
            state = "complete" if any(page.products for page in pages) and not limitations else "partial"
            result = CompetitorResearch.model_validate(dict(label="LIVE" if context.mode == "live" else "DEMO", competitor_id=cid, state=state, sources=tuple(unique.values()), pages=pages,
                conflicts=contradictions(pages), limitations=limitations))
            repo.conn.execute(insert(m.research_tasks).values(id=uuid5(cid, "research-task"), owner_id=context.user_id, run_id=context.run_id,
                competitor_id=cid, state=state, data=result.model_dump(mode="json")))
            repo.event(context.run_id, "research.competitor.completed", {"agent": "researcher", "competitor_id": str(cid), "state": state, "sources": len(unique)})
            return result

    def finish(self, context: RunContext) -> None:
        with owner_transaction(self.engine, context.user_id) as repo:
            run = PostgresSearchLedger.locked(repo, context.run_id, self.lease)
            request, _ = self._approved(repo, run)
            if run["checkpoint"]["research"]["state"] == "research_complete":
                return
            rows = repo.list(m.research_tasks, context.run_id, limit=1000)
            checkpoint = dict(run["checkpoint"])
            checkpoint["research"] = dict(checkpoint["research"]) | {"state": "research_complete", "completed_competitor_ids": [str(row["competitor_id"]) for row in rows]}
            if set(checkpoint["research"]["completed_competitor_ids"]) != set(request["artifact"]["competitor_ids"]):
                raise PolicyDenied("research_incomplete")
            repo.conn.execute(update(m.runs).where(m.runs.c.id == context.run_id).values(checkpoint=checkpoint))
            repo.event(context.run_id, "research.completed", {"agent": "researcher", "label": "DEMO", "lanes": len(rows)})
