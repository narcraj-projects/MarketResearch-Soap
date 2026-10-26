"""One bounded supplement, preserving report v1 and every original source.

Run only after the user's explicit additional-ten-credit approval. This CLI is
bound to the existing local pilot and never approves a report.
"""

from datetime import datetime, timezone
import json
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from sqlalchemy import create_engine, update

from app import models as m
from app.adapters.live_web import LivePublicWeb
from app.agents.extraction import extract, contradictions
from app.agents.snippet_extraction import eligible
from app.harness.checkpointer import OwnerPostgresSaver
from app.harness.lease import JobQueue
from app.harness.live_policy import ROOT, LivePermit, load_permit
from app.harness.research_types import CompetitorResearch
from app.harness.urls import normalize_url
from app.live_workflow import LiveWorkflow, LiveTavilyAdapter
from app.repository import owner_transaction
from app.workflow import build_graph
from tools.workflow_demo import local_config


def main():
    cfg = local_config()
    raw = json.loads((ROOT / ".cache/live-authorization.json").read_text())
    owner, run_id = UUID(cfg["users"][0]["id"]), UUID(raw["run_id"])
    permit = load_permit(run_id, owner)
    engine = create_engine(cfg["runtime_url"], hide_parameters=True)
    with owner_transaction(engine, owner) as repo:
        run = repo.get(m.runs, run_id)
        cp = dict(run["checkpoint"])
        continuing = (
            run["status"] == "researching"
            and cp.get("live_evidence_supplement") is not None
        )
        if run["status"] != "report_review" and not continuing:
            raise ValueError("only_once_before_final_approval")
        if any(
            row["gate"] == "report" and row["state"] == "decided"
            for row in repo.list(m.approval_requests, run_id)
        ):
            raise ValueError("cannot_revise_decided_report")
        prior_tasks = repo.list(m.research_tasks, run_id, limit=3)
        cp.setdefault(
            "live_evidence_supplement",
            {
                "started_at": datetime.now(timezone.utc).isoformat(),
                "prior_tasks": [row["data"] for row in prior_tasks],
                "prior_analysis": cp.pop("analysis", None),
                "authorization": "User explicitly approved another 10 Tavily credits; total 20, model cap unchanged USD5.",
            },
        )
        repo.conn.execute(
            update(m.approval_requests)
            .where(
                m.approval_requests.c.run_id == run_id,
                m.approval_requests.c.owner_id == owner,
                m.approval_requests.c.state == "pending",
            )
            .values(state="superseded")
        )
        repo.conn.execute(
            update(m.runs)
            .where(m.runs.c.id == run_id, m.runs.c.owner_id == owner)
            .values(status="researching", version=run["version"] + 1, checkpoint=cp)
        )
        repo.conn.execute(
            update(m.jobs)
            .where(m.jobs.c.run_id == run_id, m.jobs.c.owner_id == owner)
            .values(state="queued")
        )
        repo.event(
            run_id,
            "live.supplement_authorized",
            {
                "label": "LIVE",
                "total_tavily_credit_cap": 20,
                "model_cap_usd": "5",
                "prior_report_preserved": True,
            },
        )
    expanded = LivePermit.model_validate(
        permit.model_dump()
        | {
            "max_tavily_credits": 20,
            "approval_note": "User approved another 10 Tavily credits on 2026-10-26; total 20. Original USD5 LLM cap unchanged.",
        }
    )
    (ROOT / ".cache/live-authorization.json").write_text(
        expanded.model_dump_json(indent=2), encoding="utf8"
    )
    with owner_transaction(engine, owner) as repo:
        run = repo.get(m.runs, run_id)
        budget = dict(run["budget"]) | {"max_cost_usd": "5.16"}
        repo.conn.execute(
            update(m.runs)
            .where(m.runs.c.id == run_id, m.runs.c.owner_id == owner)
            .values(budget=budget)
        )
    queue = JobQueue(engine, owner)
    lease = queue.claim(uuid4(), 300, run_id)
    if lease is None:
        raise ValueError("supplement_lease_unavailable")
    try:
        workflow = LiveWorkflow(
            engine,
            lease,
            queue.deadline(run_id),
            LiveTavilyAdapter(expanded),
            LivePublicWeb(expanded),
            permit=expanded,
        )
        context, competitors = workflow.research_store.begin(
            run_id, owner, workflow.deadline, workflow.research_versions()
        )
        gateway = workflow.research_gateway()
        for competitor in competitors:
            domain = (
                urlsplit(competitor["canonical_url"]).hostname or ""
            ).removeprefix("www.")
            additional = []
            for suffix in (
                "soap product price ingredients weight grams",
                "handmade soap ingredients benefits buy price",
                '"soap" "125" price ingredients',
            ):
                query = "site:" + domain + " " + suffix
                additional.extend(
                    gateway.search_evidence(
                        context,
                        competitor["id"],
                        competitor["name"],
                        product=True,
                        query_override=query,
                        approved_domain=domain,
                    )
                )
            with owner_transaction(engine, owner) as repo:
                lease.guard(repo)
                task = next(
                    row
                    for row in repo.list(m.research_tasks, run_id, limit=3)
                    if row["competitor_id"] == competitor["id"]
                )
                completed_lanes = (
                    repo.get(m.runs, run_id)["checkpoint"].get(
                        "live_evidence_supplement"
                    )
                    or {}
                ).get("lanes", {})
                old = CompetitorResearch.model_validate(
                    completed_lanes.get(str(competitor["id"]), task["data"])
                )
                sources = tuple(
                    {
                        source.source_id: source
                        for source in (*additional, *old.sources)
                    }.values()
                )
                for source in additional:
                    workflow.research_store._put_source(repo, run_id, source)
                pages = tuple(
                    extract(
                        source,
                        competitor["name"],
                        first_party=normalize_url(source.canonical_url, demo=True)[1]
                        == domain,
                    )
                    for source in sources
                    if source.evidence_kind == "page_excerpt"
                    or eligible(
                        source,
                        normalize_url(source.canonical_url, demo=True)[1] == domain,
                    )
                )
                revised = CompetitorResearch(
                    label="LIVE",
                    competitor_id=competitor["id"],
                    state="partial",
                    sources=sources,
                    pages=pages,
                    conflicts=contradictions(pages),
                    limitations=tuple(
                        dict.fromkeys(
                            (
                                *old.limitations,
                                "supplemented_search_evidence_not_full_page",
                                *(x for page in pages for x in page.limitations),
                            )
                        )
                    ),
                )
                current = lease.guard(repo)
                revised_cp = dict(current["checkpoint"])
                supplement = dict(revised_cp["live_evidence_supplement"])
                supplement["lanes"] = dict(supplement.get("lanes", {})) | {
                    str(competitor["id"]): revised.model_dump(mode="json")
                }
                revised_cp["live_evidence_supplement"] = supplement
                repo.conn.execute(
                    update(m.runs)
                    .where(m.runs.c.id == run_id, m.runs.c.owner_id == owner)
                    .values(checkpoint=revised_cp)
                )
                repo.event(
                    run_id,
                    "research.supplemented",
                    {
                        "label": "LIVE",
                        "competitor_id": str(competitor["id"]),
                        "additional_sources": len(additional),
                        "original_state_preserved": True,
                    },
                )
                print(
                    json.dumps(
                        {
                            "competitor": competitor["name"],
                            "new_sources": len(additional),
                            "new_urls": [source.canonical_url for source in additional],
                        }
                    ),
                    flush=True,
                )
        # Populate fresh Researcher outputs before drafting v2. Existing sources and
        # old model receipts remain in Postgres; successful unchanged calls reuse.
        graph = build_graph(workflow, OwnerPostgresSaver(engine, lease))
        graph.update_state(
            {"configurable": {"thread_id": str(run_id)}},
            {
                "phase": "research",
                "revision": 1,
                "prior_report_id": None,
                "report_id": None,
                "request_id": None,
                "final": None,
                "review_ok": False,
                "issues": [],
            },
            as_node="shortlist_review",
        )
        print(
            "PASS bounded source supplement saved; immutable v1 retained; v2 scheduled; final approval still required.",
            flush=True,
        )
    finally:
        queue.release(lease, done=False)
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        import traceback

        print(
            json.dumps(
                {
                    "error_class": type(error).__name__,
                    "locations": [
                        {
                            "file": frame.filename.rsplit("\\", 1)[-1],
                            "line": frame.lineno,
                        }
                        for frame in traceback.extract_tb(error.__traceback__)
                        if "site-packages" not in frame.filename
                    ],
                    "details": "private details suppressed",
                }
            )
        )
        raise SystemExit(1) from None
