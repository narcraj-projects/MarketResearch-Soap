"""Dedicated local-only DEMO history fixture preparation. No production entry point."""
import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine

from tools.workflow_demo import local_config
from tests.history_storage_support import seed_history


def main():
    cfg = local_config()  # Loopback URL/ports and dedicated database identity marker.
    engine = create_engine(cfg["runtime_url"], hide_parameters=True)
    try:
        owner = UUID(cfg["users"][0]["id"])
        earlier, _ = seed_history(engine, owner, revisions=True)
        later, _ = seed_history(engine, owner, "evolution", later=True)
        unavailable, _ = seed_history(engine, owner, "unavailable", later=True)
        ids = {"before": str(earlier), "after": str(later), "unavailable": str(unavailable), "before_version": 2, "after_version": 1}
        (Path(__file__).resolve().parents[2] / ".cache/history-ui.json").write_text(json.dumps(ids), encoding="utf8")
        print("PASS persisted 3 DEMO history runs with actual mechanical reviews and fixture approval decisions; only IDs saved; no credentials emitted")
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Local history UI preparation failed; input/credential details suppressed") from None
