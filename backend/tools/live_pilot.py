"""One explicitly approved local live run. Never print secrets or raw errors."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import create_engine, update

from app import models as m
from app.api_schemas import BriefCreate, RunCreate
from app.harness.live_policy import LivePermit, LiveSecrets, ROOT, CREDIT_USD, load_permit
from app.repository import owner_transaction
from app.worker import run_once
from tools.workflow_demo import local_config


def main():
    parser = argparse.ArgumentParser(description="Explicitly authorized one-run live pilot; no deployment")
    parser.add_argument("action", choices=["create", "search-check", "scout-check", "refine-discovery", "repair-discovery", "resume", "step", "serve", "status"])
    parser.add_argument("--credits", type=int, default=10)
    parser.add_argument("--model-budget", default="5")
    args = parser.parse_args()
    cfg = local_config()
    owner = UUID(cfg["users"][0]["id"])
    engine = create_engine(cfg["runtime_url"], hide_parameters=True, pool_size=5, max_overflow=5, pool_timeout=10)
    try:
        if args.action == "create":
            if (ROOT / ".cache/live-authorization.json").exists():
                raise ValueError("live_approval_already_bound_do_not_create_another_run")
            keys = LiveSecrets()
            if keys.lather_tavily_api_key is None or keys.lather_llm_api_key is None:
                raise ValueError("local_keys_missing")
            expiry = datetime.now(timezone.utc) + timedelta(hours=2)
            # User-specified scope: Petite Batch, India, all requested comparison dimensions.
            brief = BriefCreate(category="Handmade cold-process soap", geography="India", customer="buyers of handmade soap in India",
                objective="For Petite Batch, compare source-backed competitors, products, pricing, ingredients, claims, positioning, channels, feedback and dated news; propose grounded differentiation hypotheses.",
                known_competitors=[], preferences={"price_segment": "Let agent find out"})
            from decimal import Decimal
            permit_budget = Decimal(args.model_budget)
            if not 1 <= args.credits <= 10 or not Decimal(0) <= permit_budget <= 5:
                raise ValueError("approval_cap_exceeded")
            with owner_transaction(engine, owner) as repo:
                saved = repo.create(m.briefs, brief.model_dump(mode="json") | {"version": 1})
                run = repo.start(RunCreate(brief_id=saved["id"], budget={"max_calls": 60, "max_tokens": 500000,
                    "max_cost_usd": str(permit_budget + args.credits * CREDIT_USD)}), str(uuid4()))
                run_id = UUID(str(run["id"]))
                repo.conn.execute(update(m.jobs).where(m.jobs.c.run_id == run_id, m.jobs.c.owner_id == owner).values(managed=True, state="queued", deadline=expiry,
                    workflow={"graph_version": "workflow-1.2", "revision_limit": 1, "mode": "live"}))
                repo.event(run_id, "live.approved", {"label": "LIVE", "tavily_credit_cap": args.credits, "model_usd_cap": str(permit_budget),
                    "approval": "Explicit user approval 2026-10-26", "provider": "fireworks", "provisional_model": True})
            permit = LivePermit(run_id=run_id, owner_id=owner, max_tavily_credits=args.credits, max_model_usd=permit_budget, expires_at=expiry)
            target = ROOT / ".cache/live-authorization.json"
            target.write_text(permit.model_dump_json(indent=2), encoding="utf8")
            target.chmod(0o600)
            print("PASS one live run authorized; Tavily <=10 credits, LLM <=USD5. No network calls made by create.", flush=True)
            print("LIVE RUN: " + str(run_id), flush=True)
            return
        value = json.loads((ROOT / ".cache/live-authorization.json").read_text())
        run_id = UUID(value["run_id"])
        load_permit(run_id, owner)
        if args.action == "resume":
            with owner_transaction(engine, owner) as repo:
                run = repo.get(m.runs, run_id)
                if run["status"] != "partial" or run["failure_code"] != "workflow_policy_stop" or any(row["state"] == "pending" for row in repo.list(m.approval_requests, run_id)):
                    raise ValueError("only_failed_unapproved_live_node_can_resume")
                checkpoint = run["checkpoint"] or {}
                stage = "queued" if checkpoint.get("stage") == "discover" else "researching"
                repo.conn.execute(update(m.runs).where(m.runs.c.id == run_id, m.runs.c.owner_id == owner).values(status=stage, failure_code=None, version=run["version"] + 1))
                repo.conn.execute(update(m.jobs).where(m.jobs.c.run_id == run_id, m.jobs.c.owner_id == owner).values(state="queued"))
                repo.event(run_id, "live.targeted_format_resume", {"label": "LIVE", "reason": "Bounded output-format correction; original evidence, failed attempts and budgets preserved."})
            print("PASS existing live checkpoint scheduled for targeted format correction; no evidence or budget reset.")
            return
        if args.action in {"refine-discovery", "repair-discovery"}:
            from app.harness.lease import JobQueue
            from app.harness.checkpointer import OwnerPostgresSaver
            from app.workflow import build_graph
            from app.live_workflow import LiveWorkflow, LiveTavilyAdapter
            from app.adapters.live_web import LivePublicWeb
            permit = load_permit(run_id, owner)
            repair = args.action == "repair-discovery"
            if (not repair and permit.discovery_revision != 0) or (repair and (permit.discovery_revision != 1 or permit.continuation_query is not None)):
                raise ValueError("discovery_revision_already_used")
            with owner_transaction(engine, owner) as repo:
                run = repo.get(m.runs, run_id)
                checkpoint = dict(run["checkpoint"] or {})
                if run["status"] != "partial" or checkpoint.get("stage") != "clarification_required" or repo.list(m.approval_requests, run_id) or repo.list(m.research_tasks, run_id):
                    raise ValueError("only_unapproved_insufficient_discovery_can_be_refined")
                sources = repo.list(m.sources, run_id, limit=1000)
                corpus = " ".join(row["excerpt"] or "" for row in sources).casefold()
                leads = [name for name in ("Juicy Chemistry", "Vilvah", "Wild Earth") if name.casefold() in corpus]
                if len(leads) < 2:
                    raise ValueError("insufficient_source_backed_query_leads")
                query = " OR ".join('"' + name + '"' for name in leads) + " handmade soap India official shop"
                checkpoint["discovery_revisions"] = [*checkpoint.get("discovery_revisions", []), {"previous_artifact": checkpoint["artifact"], "reason": "Bounded alternative after provider-invalid result." if repair else "Need explicit primary retail/market evidence; follow named source leads."}]
                for key in ("artifact", "artifact_hash", "artifact_version", "request_id"):
                    checkpoint.pop(key, None)
                checkpoint["stage"] = "discover"
                repo.conn.execute(update(m.runs).where(m.runs.c.id == run_id, m.runs.c.owner_id == owner).values(status="queued", checkpoint=checkpoint, version=run["version"] + 1))
                repo.conn.execute(update(m.jobs).where(m.jobs.c.run_id == run_id, m.jobs.c.owner_id == owner).values(state="queued"))
                repo.event(run_id, "scout.targeted_refinement", {"label": "LIVE", "source_backed_leads": leads, "bounded_revision": 1, "previous_results_preserved": True})
            updated = permit.model_copy(update={"continuation_query": "Indian handmade soap brands official store made in India buy soaps"}) if repair else permit.model_copy(update={"supplementary_query": query, "discovery_revision": 1})
            (ROOT / ".cache/live-authorization.json").write_text(updated.model_dump_json(indent=2), encoding="utf8")
            queue = JobQueue(engine, owner)
            lease = queue.claim(uuid4(), 120, run_id)
            if lease is None:
                raise ValueError("revision_lease_not_available")
            try:
                workflow = LiveWorkflow(engine, lease, queue.deadline(run_id), LiveTavilyAdapter(updated), LivePublicWeb(updated), permit=updated)
                graph = build_graph(workflow, OwnerPostgresSaver(engine, lease))
                graph.update_state({"configurable": {"thread_id": str(run_id)}}, {"phase": "discover", "issues": []}, as_node="validate")
            finally:
                queue.release(lease, done=False)
            print("PASS one source-backed discovery refinement scheduled; original results and all budget reservations preserved.", flush=True)
            return
        if args.action in {"search-check", "scout-check"}:
            from app.harness.lease import JobQueue
            from app.harness.contracts import SearchCall, Role
            from app.adapters.live_web import LivePublicWeb
            from app.live_workflow import LiveWorkflow, LiveTavilyAdapter
            from app.services.discovery import queries
            from uuid import uuid5
            permit = load_permit(run_id, owner)
            queue = JobQueue(engine, owner)
            lease = queue.claim(uuid4(), seconds=120, run_id=run_id)
            if lease is None:
                raise ValueError("live_job_not_available")
            try:
                workflow = LiveWorkflow(engine, lease, queue.deadline(run_id), LiveTavilyAdapter(permit), LivePublicWeb(permit), permit=permit)
                context, brief = workflow.search_store.begin(run_id, owner, workflow.deadline, workflow.scout_versions())
                call = SearchCall(operation_id=uuid5(run_id, "scout:scout-1.0:0"), agent=Role.SCOUT, tool="public.search", query=queries(brief)[0], limit=10)
                result = workflow.discovery_gateway().execute(context, call)
                print(json.dumps({"label": "LIVE", "search_status": result.result.status,
                    "persisted_source_count": len(result.payload.sources) if result.payload else 0,
                    "model_calls": 0, "note": "This exact search is journaled and reused by the graph; no duplicate verification search."}), flush=True)
                if args.action == "scout-check" and result.payload:
                    discovery = workflow.ranker(brief, run_id, result.payload.sources)
                    print(json.dumps({"label": "LIVE", "validated_candidate_count": len(discovery.candidates),
                        "candidate_names": [row.name for row in discovery.candidates], "note": "Provisional model output validated against real source identities/quotes; durable model result will be reused."}), flush=True)
            finally:
                queue.release(lease, done=False)
            return
        if args.action == "status":
            with owner_transaction(engine, owner) as repo:
                run = repo.get(m.runs, run_id)
                rows = repo.list(m.tool_attempts, run_id, limit=10000)
                notes = [{"role": row["outcome"].get("provider"), "model": row["outcome"].get("model"), "error": row["outcome"].get("error")}
                    for row in rows if row["outcome"] and row["outcome"].get("schema_version") == "model-live-1.0"]
                print(json.dumps({"run_id": str(run_id), "status": run["status"], "version": run["version"], "failure_code": run["failure_code"],
                    "tavily_reserved_credits": sum(row["cost_upper_bound_usd"] == CREDIT_USD for row in rows),
                    "model_calls": len(notes), "model_status": notes}, indent=2), flush=True)
            return
        from time import sleep
        while True:
            result = run_once(engine, owner, run_id=run_id, lease_seconds=120)
            if result["state"] != "idle":
                print(json.dumps(result), flush=True)
            if args.action == "step":
                break
            sleep(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        import traceback
        locations = [{"file": Path(item.filename).name, "line": item.lineno} for item in traceback.extract_tb(error.__traceback__) if "site-packages" not in item.filename]
        print(json.dumps({"error_class": type(error).__name__, "code_locations": locations, "details": "private error/input content suppressed"}), flush=True)
        raise SystemExit(1) from None
