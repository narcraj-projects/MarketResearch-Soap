"""Explicit recorded research for an already approved local DEMO run. No next agent."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.adapters.public_web import RecordedWeb
from app.agents.researcher import research_parallel
from app.harness.contracts import Versions
from app.harness.research_store import ResearchStore
from app.harness.retrieval import ResearchGateway


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Local recorded DEMO research; requires an already approved shortlist")
    parser.add_argument("--run-id", type=UUID, required=True)
    parser.add_argument("--case", choices=["R21-parallel", "R23-parallel-blocked"], default="R21-parallel")
    args = parser.parse_args()
    engine = None
    try:
        cfg = json.loads(Path(os.environ.get("LATHER_INTEGRATION_CONFIG", str(root / ".cache/auth-stage.json"))).read_text())
        runtime, admin = make_url(cfg["runtime_url"]), make_url(cfg["admin_url"])
        if any(url.host != "127.0.0.1" or url.port != 57422 for url in (runtime, admin)) or cfg["supabase_url"] != "http://127.0.0.1:57421":
            raise ValueError("dedicated_loopback_required")
        control = create_engine(admin, hide_parameters=True)
        try:
            with control.connect() as connection:
                if connection.execute(text("SELECT instance FROM lather_test_control.identity WHERE id=1")).scalar_one() != cfg["test_instance"]:
                    raise ValueError("dedicated_identity_required")
        finally:
            control.dispose()
        engine = create_engine(runtime, hide_parameters=True)
        store = ResearchStore(engine)
        versions = Versions(graph="research-1.0", model="none", provider="none", prompt="attributed-extraction-1.0", tools="public-research-1.0", dataset="research-demo-v1")
        context, competitors = store.begin(args.run_id, UUID(cfg["users"][0]["id"]), datetime.now(timezone.utc) + timedelta(minutes=5), versions)
        recording = RecordedWeb(root / "backend/evaluations/fixtures/research-v1" / (args.case + ".json"))
        results = research_parallel(context, competitors, ResearchGateway(recording, store), store)
        print(json.dumps({"label": "DEMO", "run_id": str(args.run_id), "state": "research_complete", "competitors": len(results),
            "recorded_http_dispatches": len(recording.requests), "actual_external_calls": 0,
            "products": sum(len(page.products) for result in results for page in result.pages), "partial_lanes": sum(result.state == "partial" for result in results)}))
    except Exception:
        print("Local research DEMO failed; credential/input details suppressed.", file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        if engine:
            engine.dispose()


if __name__ == "__main__":
    main()
