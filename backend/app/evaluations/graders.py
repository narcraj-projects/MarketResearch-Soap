"""Mechanical graders. Citation/quote validity never certifies semantic support."""
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP, localcontext
from hashlib import sha256

from pydantic import ValidationError

from app.evaluations.contracts import Grade
from app.harness.analysis_types import AnalysisDraft
from app.harness.policy import ALLOWLIST
from app.harness.contracts import Role
from app.harness.research_types import CompetitorResearch, WireOutcome
from app.harness.search import AttemptOutcome
from app.repository import digest


def result(name, passed, reason):
    return Grade(name=name, passed=bool(passed), reason=reason)


def grade_schema(reports: list[dict], tasks: list[dict]) -> Grade:
    try:
        for report in reports:
            AnalysisDraft.model_validate(report["data"]["analysis"])
            if digest(report["data"]) != report["content_hash"]:
                return result("schema", False, "Immutable report hash differs from its typed payload.")
        for row in tasks:
            CompetitorResearch.model_validate(row["data"])
    except (ValidationError, KeyError, ValueError):
        return result("schema", False, "An expected typed persisted artifact is invalid.")
    return result("schema", True, "Persisted artifacts validate; expected malformed outputs are checked separately.")


def grade_math(prices: list[dict], expected: dict) -> Grade:
    valid = True
    by_sku: dict[str, list] = {}
    for row in prices:
        value = row["unit_price_100g"]
        by_sku.setdefault(row["sku"] or "unknown", []).append(None if value is None else Decimal(value))
        if value is None:
            valid &= bool(row["unavailable_reason"])
            continue
        if not row["sku"] or row["amount"] is None or row["total_weight_g"] is None or Decimal(row["total_weight_g"]) <= 0:
            valid = False
            continue
        with localcontext() as ctx:
            ctx.prec = 60
            independent = (Decimal(row["amount"]) * 100 / Decimal(row["total_weight_g"])).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
        valid &= Decimal(value) == independent
    for sku, units in expected.items():
        actual = Counter(by_sku.get(sku, []))
        valid &= actual == Counter(None if value is None else Decimal(value) for value in units)
    return result("math", valid, "Independent Decimal arithmetic and declared SKU/pack eligibility expectations, including nulls.")


def grade_candidates(shortlist: dict | None, sources: list[dict], expected_count: int | None) -> Grade:
    if shortlist is None:
        return result("no_invented_competitors", expected_count == 0, "No shortlist exists; only a declared zero-candidate result permits this.")
    discovery = shortlist["discovery"]
    selected = discovery["candidates"]
    available = {str(source["id"]): source for source in sources if source["evidence_kind"] == "search_snippet"}
    valid = len(selected) <= 3 and (expected_count is None or len(selected) == expected_count)
    valid &= len({row["domain"] for row in selected}) == len(selected)
    valid &= len(selected) == 3 or bool(discovery["insufficiency_reason"])
    for row in selected:
        valid &= bool(row["source_ids"]) and all(str(key) in available for key in row["source_ids"])
        valid &= any(row["name"] in (available.get(str(key), {}).get("excerpt") or "") for key in row["source_ids"])
    return result("no_invented_competitors", valid, "Selected identities resolve to actual recorded search evidence, unique domains and explicit shortfalls.")


def grade_tools(events: list[dict], attempts: list[dict], call_cap: int) -> tuple[Grade, Grade]:
    permission_ok, arguments_ok = True, True
    keys = [(str(row["operation_id"]), row["attempt"]) for row in attempts]
    arguments_ok &= len(keys) == len(set(keys)) and len(attempts) <= call_cap
    for row in attempts:
        arguments_ok &= 1 <= row["attempt"] <= 3 and row["state"] == "completed" and len(row["request_hash"]) == 64
        body = row.get("outcome") or {}
        try:
            if body.get("schema_version") == "model-replay-1.0":
                from app.harness.replay import ReplayRequest
                ReplayRequest.model_validate(body["request"])
                arguments_ok &= sha256(body["raw_response"].encode()).hexdigest() == body["response_hash"]
            elif "reply" in body:
                WireOutcome.model_validate(body)
            else:
                AttemptOutcome.model_validate(body)
        except (ValidationError, KeyError, ValueError):
            arguments_ok = False
    for event in events:
        if event["kind"] == "tool.reserved":
            data = event["data"]
            try:
                permission_ok &= data["tool"] in ALLOWLIST[Role(data["agent"])]
            except (ValueError, KeyError):
                permission_ok = False
    return (result("permissions", permission_ok, "Every observed dispatched tool belongs to its agent allowlist."),
        result("tool_arguments", arguments_ok, "Exact replay transports validated wire arguments; journals have typed outcomes, hashes, unique bounded attempts and budget caps."))


def grade_trajectory(events: list[dict], status: str, requests: list[dict], decisions: list[dict]) -> Grade:
    nodes = [row["data"]["node"] for row in events if row["kind"] == "workflow.node"]
    valid = not nodes or nodes[0] == "validate"
    order = {name: index for index, name in enumerate(["validate", "discover", "research", "normalize", "analyze", "review", "revise", "save"])}
    valid &= all(node in order for node in nodes)
    for left, right in zip(nodes, nodes[1:]):
        valid &= order.get(right, -1) >= order.get(left, 999) or (left == "revise" and right == "analyze")
    valid &= nodes.count("revise") <= 1 and nodes.count("save") <= 1
    by_decision = {str(row["id"]): row for row in decisions}
    by_request = {str(row["id"]): row for row in requests}
    approved = {}
    for event in events:
        if event["kind"] != "approval.decided":
            continue
        decision = by_decision.get(event["data"].get("decision_id"))
        request = by_request.get(str(decision["request_id"])) if decision else None
        bound = decision and request and decision["artifact_hash"] == request["artifact_hash"] and decision["artifact_version"] == request["artifact_version"] and request["state"] == "decided" and request["gate"] == event["data"].get("gate")
        valid &= bool(bound)
        if bound and decision is not None and request is not None and decision["decision"] == "approve":
            approved[request["gate"]] = event["sequence"]
    shortlist_at, final_at = approved.get("shortlist"), approved.get("report")
    for event in events:
        if event["kind"] == "tool.reserved" and event["data"].get("agent") == "researcher" or event["kind"] == "model.replay_reserved":
            valid &= shortlist_at is not None and event["sequence"] > shortlist_at
        if event["kind"] == "run.completed":
            valid &= final_at is not None and event["sequence"] > final_at
    if status == "complete":
        valid &= final_at is not None and sum(e["kind"] == "run.completed" for e in events) == 1
    return result("trajectory", valid, "Observed partial order, bounded revision and both durable human gates; parallel sibling interleaving is unrestricted.")


def citation_diagnostics(analysis: dict, sources: list[dict]) -> dict:
    material = [f for f in analysis["findings"] if f["value"] is not None and f["kind"] in {"fact", "source_claim"}]
    by_id = {str(row["id"]): row for row in sources}
    present = sum(bool(row["evidence"]) for row in material)
    intact = sum(bool(row["evidence"]) and all(str(e["source_id"]) in by_id and by_id[str(e["source_id"])]["access_status"] == "ok"
        and e["quote"] in (by_id[str(e["source_id"])]["excerpt"] or "") and sha256(e["quote"].encode()).hexdigest() == e["quote_hash"] for e in row["evidence"]) for row in material)
    return {"material_claims": len(material), "cited": present, "intact_quotes": intact,
        "citation_presence": present / len(material) if material else None, "quote_integrity": intact / len(material) if material else None,
        "genuine_support_coverage": None, "semantic_support": "not_adjudicated"}


def failure_gate(outcomes) -> dict:
    from app.evaluations.contracts import FAILURE_COHORT
    indexed = {row.case_id: row for row in outcomes}
    evaluated = all(key in indexed for key in FAILURE_COHORT)
    passed = sum(key in indexed and indexed[key].passed for key in FAILURE_COHORT)
    return {"cohort": list(FAILURE_COHORT), "denominator": 5, "handled": passed if evaluated else None,
        "status": "passed_controlled" if evaluated and passed >= 4 else "failed" if evaluated else "not_evaluated",
        "scope": "predeclared recorded DEMO failure tests, not live research quality"}
