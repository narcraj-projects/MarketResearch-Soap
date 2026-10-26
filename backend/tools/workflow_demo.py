"""Drive one explicitly queued DEMO run on the dedicated local stack only."""
import argparse
import json
import os
from pathlib import Path
import sys
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.worker import run_once
from app.workflow import Workflow


def local_config() -> dict:
    root = Path(__file__).resolve().parents[2]
    cfg = json.loads(Path(os.environ.get("LATHER_INTEGRATION_CONFIG", str(root / ".cache/auth-stage.json"))).read_text())
    runtime, admin = make_url(cfg["runtime_url"]), make_url(cfg["admin_url"])
    if any(url.host != "127.0.0.1" or url.port != 57422 for url in (runtime, admin)) or cfg["supabase_url"] != "http://127.0.0.1:57421":
        raise ValueError("dedicated_loopback_required")
    control = create_engine(admin, hide_parameters=True)
    try:
        with control.connect() as conn:
            if conn.execute(text("SELECT instance FROM lather_test_control.identity WHERE id=1")).scalar_one() != cfg["test_instance"]:
                raise ValueError("dedicated_instance_required")
    finally:
        control.dispose()
    return cfg


def run_local(run_id: UUID, *, workflow_factory=Workflow, lease_seconds: int = 30) -> dict:
    cfg = local_config()
    runtime = make_url(cfg["runtime_url"])
    engine = create_engine(runtime, hide_parameters=True)
    try:
        return run_once(engine, UUID(cfg["users"][0]["id"]), run_id=run_id, workflow_factory=workflow_factory, lease_seconds=lease_seconds)
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Replay-only local LangGraph worker; never calls paid tools")
    parser.add_argument("--run-id", type=UUID, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(run_local(args.run_id)))
    except Exception:
        print("Local workflow DEMO failed; credential/input details suppressed.", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
