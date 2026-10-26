"""Separate test-only worker CLI. Process termination is never in the HTTP server."""
import argparse
import json
import os
from uuid import UUID

from sqlalchemy import create_engine

from app.config import Settings
from app.harness.chaos import require_test_mode
from app.worker import run_once
from tools.workflow_demo import local_config


def main():
    parser = argparse.ArgumentParser(description="Explicit dedicated local DEMO chaos worker; no live transports")
    parser.add_argument("--run-id", type=UUID, required=True)
    parser.add_argument("--lease-seconds", type=int, default=30)
    args = parser.parse_args()
    settings = Settings()
    require_test_mode(settings)
    config = local_config()  # Dedicated loopback ports and database identity marker.
    engine = create_engine(config["runtime_url"], hide_parameters=True)
    try:
        result = run_once(engine, UUID(config["users"][0]["id"]), run_id=args.run_id, lease_seconds=args.lease_seconds,
            settings=settings, interrupt_worker=lambda: os._exit(23))
        print(json.dumps(result))
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Dedicated DEMO chaos worker failed; input/configuration details suppressed") from None
