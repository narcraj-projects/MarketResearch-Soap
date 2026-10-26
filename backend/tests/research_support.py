"""Offline research harness support; never used as persistence proof."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from threading import Lock
from contextlib import contextmanager
from uuid import UUID

from app.adapters.public_web import RecordedWeb
from app.harness.contracts import Approval, Budget, Phase, RunContext, Versions
from app.harness.policy import PolicyDenied
from app.harness.retrieval import ResearchGateway
from app.agents.extraction import contradictions, extract
from app.harness.research_types import CompetitorResearch
from app.harness.urls import normalize_url

FOLDER = Path(__file__).resolve().parents[1] / "evaluations/fixtures/research-v1"
NOW = datetime(2026, 10, 25, tzinfo=timezone.utc)


def versions():
    return Versions(graph="research-1.0", model="none", provider="none", prompt="attributed-extraction-1.0", tools="public-research-1.0", dataset="research-demo-v1")


def context(**changes):
    approval = Approval(request_id=UUID(int=4), decision_id=UUID(int=5), run_id=UUID(int=1), owner_id=UUID(int=2), gate="shortlist",
        artifact_hash="a" * 64, artifact_version=1, decision="approve", decided_at=NOW)
    return RunContext.model_validate(dict(run_id=UUID(int=1), user_id=UUID(int=2), trace_id=UUID(int=3), brief_version=1, run_version=5,
        versions=versions(), phase=Phase.RESEARCH, deadline=NOW + timedelta(minutes=5), budget=Budget(max_calls=100, max_tokens=0, max_cost=1),
        shortlist_hash="a" * 64, shortlist_version=1, approvals=(approval,)) | changes)


class Clock:
    def __init__(self):
        self.time, self.delays = NOW, []

    def now(self):
        return self.time

    def sleep(self, delay):
        self.delays.append(delay)
        self.time += timedelta(seconds=delay)


class MemoryJournal:
    def __init__(self):
        self.rows = {}
        self.lock = Lock()

    def reserve(self, context, call, attempt, fingerprint, cost, now):
        key = (call.operation_id, attempt)
        with self.lock:
            if key in self.rows:
                row = self.rows[key]
                if row["fingerprint"] != fingerprint:
                    raise PolicyDenied("operation_payload_conflict")
                if row["outcome"] is None:
                    raise PolicyDenied("uncertain_attempt")
                return row["outcome"]
            if len(self.rows) + 1 > context.budget.max_calls or sum((r["cost"] for r in self.rows.values()), Decimal(0)) + cost > context.budget.max_cost:
                raise PolicyDenied("budget")
            self.rows[key] = {"fingerprint": fingerprint, "cost": cost, "outcome": None}
            return None

    def complete(self, context, call, attempt, fingerprint, outcome, now):
        with self.lock:
            self.rows[(call.operation_id, attempt)]["outcome"] = outcome


def setup(case="R01-complete", **changes):
    recording = RecordedWeb(FOLDER / (case + ".json"))
    journal, clock = MemoryJournal(), Clock()
    return recording, journal, clock, ResearchGateway(recording, journal, clock=clock.now, sleep=clock.sleep), context(**changes)


class MemoryResearchState:
    """Evaluation only. It establishes no durability or authenticated ownership."""
    def __init__(self, competitors):
        self.competitors = {competitor["id"]: competitor for competitor in competitors}
        self.results = {}
        self.lock = Lock()

    @contextmanager
    def lane(self, context, competitor_id):
        yield

    def cached_task(self, context, cid):
        return self.results.get(cid)

    def save_task(self, context, cid, sources, limitations):
        competitor = self.competitors[cid]
        domain = normalize_url(competitor["canonical_url"], demo=True)[1]
        unique = {source.source_id: source for source in sources}
        pages = tuple(extract(source, competitor["name"], first_party=normalize_url(source.canonical_url, demo=True)[1] == domain)
            for source in unique.values() if source.evidence_kind == "page_excerpt")
        limitations = tuple(dict.fromkeys([*limitations, *(limitation for page in pages for limitation in page.limitations), *(s.reason for s in unique.values() if s.reason)]))
        result = CompetitorResearch.model_validate(dict(competitor_id=cid, state="complete" if any(p.products for p in pages) and not limitations else "partial",
            sources=tuple(unique.values()), pages=pages, conflicts=contradictions(pages), limitations=limitations))
        with self.lock:
            self.results[cid] = result
        return result

    def finish(self, context):
        pass
