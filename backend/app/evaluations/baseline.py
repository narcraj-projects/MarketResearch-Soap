"""Baseline recording is explicit and never overwrites expectations or promotes review."""
from hashlib import sha256
import json
from pathlib import Path

from app.evaluations.contracts import CaseOutcome
from app.harness.policy import PolicyDenied


def execution_versions() -> dict:
    from app.harness.checkpointer import GRAPH_VERSION
    from app.adapters.tavily import ADAPTER_VERSION
    from app.agents.scout import SCORER_VERSION
    root = Path(__file__).resolve().parents[3]
    names = ["app/agents/analyst.py", "app/agents/reviewer.py", "app/agents/normalization.py", "app/harness/gateway.py",
        "app/harness/retrieval.py", "app/harness/model_replay.py", "app/harness/checkpointer.py", "app/harness/policy.py", "app/api.py",
        "app/evaluations/graders.py", "app/evaluations/runner.py", "app/evaluations/workflow.py", "app/evaluations/review.py",
        "app/evaluations/contracts.py", "app/evaluations/dataset.py", "app/evaluations/telemetry.py", "app/evaluations/acceptance.py", "app/evaluations/baseline.py"]
    names += ["app/auth.py", "app/config.py", "app/db.py", "app/main.py", "app/security.py", "app/queue_policy.py", "app/repository.py",
        "app/harness/lease.py", "app/harness/research_store.py", "app/harness/urls.py", "app/harness/web_policy.py"]
    code = "".join(name + "\n" + (root / "backend" / name).read_text(encoding="utf8").replace("\r\n", "\n") for name in names)
    import importlib.metadata
    return {"graph": GRAPH_VERSION, "search": ADAPTER_VERSION, "scorer": SCORER_VERSION, "public_research": "public-research-1.0", "langsmith_sdk": importlib.metadata.version("langsmith"),
        "model_tools": "model-replay-1.0", "provider": "none", "model": "none", "prompt": "DEMO-frozen-analysis-1.0", "implementation_sha256": sha256(code.encode()).hexdigest()}


def snapshot(outcomes: list[CaseOutcome], manifest_hash: str) -> dict:
    return {"schema_version": "baseline-1.0", "label": "DEMO", "dataset_version": "lather-golden-v1", "manifest_hash": manifest_hash,
        "grader_version": "graders-1.0", "execution_versions": execution_versions(), "review_status": "pending_user_review",
        "cases": {row.case_id: {"passed": row.passed, "grades": {grade.name: grade.passed for grade in row.grades},
            "signature": row.signature, "measurement": row.measurement.model_dump(mode="json")} for row in outcomes}}


def record(path: Path, value: dict):
    if path.exists():
        raise PolicyDenied("baseline_exists_create_new_version_for_review")
    if not value["cases"] or not all(row["passed"] for row in value["cases"].values()):
        raise PolicyDenied("cannot_record_failed_baseline")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf8")


def compare(path: Path, candidate: dict) -> dict:
    raw = path.read_bytes()
    base = json.loads(raw)
    comparable = all(base.get(key) == candidate.get(key) for key in ("schema_version", "dataset_version", "manifest_hash", "grader_version", "execution_versions"))
    changes, deltas = [], {}
    if not comparable:
        changes.append({"case_id": None, "field": "versions", "critical": True})
    for identifier in sorted(set(base.get("cases", {})) | set(candidate["cases"])):
        old, new = base.get("cases", {}).get(identifier), candidate["cases"].get(identifier)
        if old is None or new is None:
            changes.append({"case_id": identifier, "field": "case_membership", "critical": True})
            continue
        for field in ("passed", "grades", "signature"):
            if old[field] != new[field]:
                changes.append({"case_id": identifier, "field": field, "critical": True, "before": old[field], "after": new[field]})
        deltas[identifier] = {field: new["measurement"][field] - old["measurement"][field] if new["measurement"][field] is not None and old["measurement"][field] is not None else None for field in ("latency_ms", "completed_calls", "provider_tokens")}
        from decimal import Decimal
        old_cost, new_cost = old["measurement"]["cost_upper_bound_usd"], new["measurement"]["cost_upper_bound_usd"]
        deltas[identifier]["cost_upper_bound_usd"] = str(Decimal(new_cost) - Decimal(old_cost)) if old_cost is not None and new_cost is not None else None
    return {"baseline_sha256": sha256(raw).hexdigest(), "baseline_review": base.get("review_status", "unknown"), "comparable": comparable,
        "critical_regression": bool(changes), "changes": changes, "budget_latency_deltas": deltas,
        "latency_policy": "Measured local replay deltas are diagnostic; no invented performance threshold.", "release_baseline_reviewed": base.get("review_status") == "approved"}
