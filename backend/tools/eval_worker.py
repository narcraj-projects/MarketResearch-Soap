"""Only a dedicated local test process can execute/interrupt a pinned golden job."""
import argparse
import json
import os
from uuid import UUID

from sqlalchemy import create_engine

from app.config import Settings
from app.evaluations.dataset import require_evaluation
from app.worker import run_once
from tools.workflow_demo import local_config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", type=UUID, required=True)
    parser.add_argument("--lease-seconds", type=int, default=30)
    parser.add_argument("--interrupt", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    require_evaluation(settings)
    cfg = local_config()
    engine = create_engine(cfg["runtime_url"], hide_parameters=True)
    try:
        # Supplying termination remains confined to this explicitly launched test CLI.
        callback = (lambda: os._exit(23)) if args.interrupt else (lambda: None)
        output = run_once(engine, UUID(cfg["users"][0]["id"]), run_id=args.run_id, settings=settings,
            lease_seconds=args.lease_seconds, interrupt_worker=callback)
        print(json.dumps(output))
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit(f"Local evaluation worker failed ({type(error).__name__}); details suppressed.") from None
