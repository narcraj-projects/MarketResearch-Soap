"""Explicit local DEMO command. Never consumes a queue automatically or calls Tavily."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app import models as m
from app.adapters.tavily import TavilyAdapter
from app.api_schemas import BriefCreate, RunCreate
from app.harness.contracts import Versions
from app.harness.gateway import SearchGateway
from app.harness.recordings import RecordedTavily
from app.harness.search import SearchCost
from app.harness.search_store import PostgresSearchLedger
from app.repository import owner_transaction
from app.services.discovery import discover


def main() -> None:
    folder = Path(__file__).resolve().parents[1] / "evaluations/fixtures/scout-v1"
    parser = argparse.ArgumentParser(description="Local-only DEMO Scout recording replay; no paid APIs")
    parser.add_argument("--case", choices=[p.stem for p in folder.glob("SC*.json")], default="SC01-clean")
    parser.add_argument("--run-id", type=UUID)
    parser.add_argument("--crash-after-search", action="store_true", help="DEMO test boundary before publishing the durable shortlist")
    args = parser.parse_args()
    engine = None
    try:
        root = Path(__file__).resolve().parents[2]
        data = json.loads(Path(os.environ.get("LATHER_INTEGRATION_CONFIG", str(root / ".cache/auth-stage.json"))).read_text(encoding="utf8"))
        db_url = make_url(data["runtime_url"])
        if db_url.host != "127.0.0.1" or db_url.port != 57422 or data["supabase_url"] != "http://127.0.0.1:57421":
            raise ValueError("dedicated_local_stack_required")
        engine = create_engine(db_url, hide_parameters=True)
        recording = RecordedTavily(folder / (args.case + ".json"))
        owner = UUID(data["users"][0]["id"])
        admin_url = make_url(data["admin_url"])
        if admin_url.host != "127.0.0.1" or admin_url.port != 57422:
            raise ValueError("dedicated_instance_required")
        control = create_engine(admin_url, hide_parameters=True)
        try:
            with control.connect() as connection:
                identity = connection.execute(text("SELECT instance FROM lather_test_control.identity WHERE id=1")).scalar_one()
            if identity != data["test_instance"]:
                raise ValueError("dedicated_instance_required")
        finally:
            control.dispose()
        if args.run_id:
            run_id = args.run_id
            with owner_transaction(engine, owner) as repo:
                run = repo.get(m.runs, run_id)
                if run["status"] != "queued":
                    snapshot = PostgresSearchLedger.snapshot(repo, run_id)
                    print(json.dumps({"label": "DEMO", "run_id": str(run_id), "status": snapshot["status"], "dispatches": 0}))
                    return
        else:
            brief = BriefCreate.model_validate(recording.case["brief"])
            with owner_transaction(engine, owner) as repo:
                saved = repo.create(m.briefs, brief.model_dump(mode="json") | {"version": 1})
                run_id = UUID(repo.start(RunCreate(brief_id=saved["id"], budget={"max_calls": 6, "max_tokens": 0, "max_cost_usd": "0"}), str(uuid4()))["id"])
        ledger = PostgresSearchLedger(engine)
        versions = Versions(graph="scout-1.0", model="none", provider="none", prompt="deterministic-scout-1.0", tools="tavily-search-1.0", dataset="scout-demo-v1")
        context, brief = ledger.begin(run_id, owner, datetime.now(timezone.utc) + timedelta(minutes=5), versions)
        gateway = SearchGateway(TavilyAdapter(recording.transport), ledger, SearchCost(per_attempt_upper_bound_usd=0, pricing_version="DEMO-zero-spend"))
        def crash():
            print(json.dumps({"label": "DEMO", "run_id": str(run_id), "status": "interrupted_after_search", "dispatches": recording.ordinal}))
            raise SystemExit(23)
        snapshot = discover(context, brief, gateway, ledger, crash if args.crash_after_search else None)
        print(json.dumps({"label": "DEMO", "run_id": str(run_id), "status": snapshot["status"], "dispatches": recording.ordinal,
            "candidates": len(snapshot["artifact"]["competitor_ids"]), "request_id": snapshot["request_id"]}))
    except Exception:
        print("Local Scout DEMO failed; credential/input details suppressed.", file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        if engine:
            engine.dispose()


if __name__ == "__main__":
    main()
