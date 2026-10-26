"""Original BRD thresholds, with explicit controlled, unknown and failed states."""
from app.evaluations.graders import failure_gate


def controlled(outcomes, identifiers):
    indexed = {row.case_id: row for row in outcomes}
    if any(key not in indexed for key in identifiers):
        return "not_evaluated"
    return "passed_controlled" if all(indexed[key].passed for key in identifiers) else "failed"


def gates(outcomes, support: dict, useful: dict) -> dict:
    support_states = [row["status"] for row in support.values()]
    source_status = "not_evaluated" if not support_states or any(state in {"not_evaluated", "incomplete"} for state in support_states) else "failed" if "failed" in support_states else "passed_controlled_human_review"
    return {
        "A01": {"status": controlled(outcomes, ("D01", "D02", "D03")), "scope": "Recorded relevance/provenance; live competitor adequacy remains unmeasured"},
        "A02": {"status": source_status, "threshold": ">=90%", "reports": support},
        "A03": {"status": controlled(outcomes, ("D06", "D08", "D09"))}, "A04": useful,
        "A05": failure_gate(outcomes), "A06": {"status": controlled(outcomes, ("D13",))},
        "A07": {"status": controlled(outcomes, ("D01", "D03", "D11", "D12")), "scope": "Controlled identity/medical negative controls, not independent live factual review"},
        "A08": {"status": controlled(outcomes, ("D01", "D13", "D14", "D17"))}}


def release_blockers(measurements: dict, regression: dict) -> list[str]:
    blockers = ["Recorded DEMO data cannot establish live-market or model-quality acceptance", "No final provider-neutral model benchmark/selection"]
    if measurements["A02"]["status"] != "passed_controlled_human_review":
        blockers.append("Material source support is not fully human-adjudicated at >=90% for each evaluated report")
    if measurements["A04"]["status"] != "passed":
        blockers.append("Five actual business-owner usefulness ratings with >=4 useful are missing or fail")
    if not regression.get("release_baseline_reviewed"):
        blockers.append("Initial baseline awaits user review")
    if regression.get("critical_regression") is not False:
        blockers.append("No passing, comparable baseline regression result")
    for key, value in measurements.items():
        if value["status"] in {"failed", "not_evaluated"} and key not in {"A02", "A04"}:
            blockers.append(key + " is failed or not evaluated")
    return blockers
