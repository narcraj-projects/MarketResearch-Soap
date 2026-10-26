"""Offline DEMO evaluation; in-memory accounting is not persistence evidence."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from app.adapters.tavily import TavilyAdapter
from app.agents.scout import rank
from app.api_schemas import BriefCreate
from app.harness.gateway import SearchGateway
from app.harness.recordings import RecordedTavily
from app.harness.search import SearchCost
from app.services.discovery import search
from tests.scout_support import Clock, MemoryLedger, context, versions


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate pinned DEMO Scout recordings with all network disabled")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    folder = Path(__file__).resolve().parents[1] / "evaluations/fixtures/scout-v1"
    rows = []
    for case in sorted(folder.glob("SC*.json")):
        recording = RecordedTavily(case)
        clock, ledger = Clock(), MemoryLedger()
        ctx, brief = context(), BriefCreate.model_validate(recording.case["brief"])
        gateway = SearchGateway(TavilyAdapter(recording.transport), ledger, SearchCost(per_attempt_upper_bound_usd=0, pricing_version="DEMO-zero-spend"),
            clock.now, clock.sleep, lambda: 0)
        sources, stop = search(ctx, brief, gateway)
        result = rank(brief, ctx.run_id, sources)
        actual = {"candidates": len(result.candidates), "dispatches": recording.ordinal, "stop_reason": stop}
        recording.assert_finished()
        checks = {"expected_outcome": actual == recording.case["expected"], "up_to_three": len(result.candidates) <= 3,
            "unique_domains": len({c.domain for c in result.candidates}) == len(result.candidates),
            "source_backed_identities": all(any(s.source_id in c.source_ids and c.name in s.excerpt for s in sources) for c in result.candidates),
            "shortfall_explicit": len(result.candidates) == 3 or bool(result.insufficiency_reason)}
        rows.append({"case_id": recording.case["case_id"], "label": "DEMO", "expected": recording.case["expected"], "actual": actual,
            "checks": checks, "outcome": "passed" if all(checks.values()) else "failed", "candidate_names": [c.name for c in result.candidates],
            "simulated_retry_delays_seconds": clock.delays})
    report = {"label": "DEMO", "dataset_version": "scout-demo-v1", "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest_sha256": sha256((folder / "manifest.json").read_bytes()).hexdigest(), "versions": versions().model_dump(mode="json"),
        "recordings": len(rows), "passed": sum(row["outcome"] == "passed" for row in rows), "actual_external_calls": 0,
        "actual_provider_credits_spent": 0, "actual_provider_cost_usd": "0", "semantic_support": "not_evaluated", "owner_usefulness": "not_evaluated",
        "limits": "Synthetic recorded wire responses, fake clock, test-only in-memory accounting. Database/process recovery is tested separately. Not live research quality or model selection.", "cases": rows}
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print(f"DEMO Scout recordings: {report['passed']}/{len(rows)} passed; 0 external calls; 0 provider credits. Support/usefulness not evaluated.")
    if report["passed"] != len(rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
