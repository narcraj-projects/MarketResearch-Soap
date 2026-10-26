"""Read-only public pilot metadata; no credentials, prompts or private auth data."""

from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import json
from uuid import UUID
from sqlalchemy import create_engine
from app import models as m
from app.harness.live_policy import ROOT, CREDIT_USD
from app.repository import owner_transaction
from app.reporting import report_view
from tools.workflow_demo import local_config


def main():
    cfg = local_config()
    owner = UUID(cfg["users"][0]["id"])
    permit = json.loads((ROOT / ".cache/live-authorization.json").read_text())
    run_id = UUID(permit["run_id"])
    engine = create_engine(cfg["runtime_url"], hide_parameters=True)
    try:
        with owner_transaction(engine, owner) as repo:
            run = repo.get(m.runs, run_id)
            report = repo.report(run_id)
            view = report_view(repo, run, report)
            rows = repo.list(m.tool_attempts, run_id, limit=10000)
            model = [
                row
                for row in rows
                if (row["outcome"] or {}).get("schema_version") == "model-live-1.0"
            ]
            usage = repo.list(m.usage, run_id, limit=10000)
            receipt = {
                "measured_at": datetime.now(timezone.utc).isoformat(),
                "label": "LIVE",
                "run_id": str(run_id),
                "run_state": run["status"],
                "report_version": report["version"],
                "report_hash": report["content_hash"],
                "approval_state": view.approval.state,
                "export_allowed": view.export_allowed,
                "competitors": [
                    row["name"] for row in repo.list(m.competitors, run_id, limit=3)
                ],
                "tavily_credit_reservations": sum(
                    row["cost_upper_bound_usd"] == CREDIT_USD and row not in model
                    for row in rows
                ),
                "tavily_credit_cap": permit["max_tavily_credits"],
                "model_usd_cap": permit["max_model_usd"],
                "model_receipts": len(model),
                "model_roles": dict(Counter(row["outcome"]["role"] for row in model)),
                "model_receipt_errors": dict(
                    Counter(
                        row["outcome"]["error"]
                        for row in model
                        if row["outcome"].get("error")
                    )
                ),
                "recorded_tokens": sum(row["tokens"] for row in usage),
                "reserved_attempts": sum(row["state"] == "reserved" for row in rows),
                "reconciled_cost_upper_bound_usd": str(
                    sum((row["cost_upper_bound_usd"] for row in rows), Decimal(0))
                ),
                "price_invoice_verified": False,
                "full_material_support": "unmeasured",
                "owner_usefulness": "unmeasured",
                "benchmark_winner": None,
                "remote_trace_exports": 0,
                "deployment": False,
            }
        (ROOT / "docs/LIVE_RECEIPT.json").write_text(
            json.dumps(receipt, indent=2) + "\n", encoding="utf8"
        )
        print(json.dumps(receipt, indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit(
            "Receipt failed (" + type(error).__name__ + "); private details suppressed"
        ) from None
