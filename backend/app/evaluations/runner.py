"""Actual recorded golden execution on the dedicated local owner-RLS database."""
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
import subprocess
import sys
from typing import Any
from time import perf_counter, sleep
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select, update

from app import models as m
from app.api_schemas import BriefCreate, DecisionCreate, RunCreate
from app.config import Settings
from app.evaluations.contracts import CaseOutcome, RunMeasurement
from app.evaluations.dataset import Dataset, FOLDER, require_evaluation
from app.evaluations.graders import citation_diagnostics, grade_candidates, grade_math, grade_schema, grade_tools, grade_trajectory, result
from app.harness.lease import Lease
from app.harness.policy import PolicyDenied
from app.repository import digest, owner_transaction
from app.worker import run_once


class GoldenRunner:
    def __init__(self, engine, owner: UUID, other_owner: UUID, settings: Settings):
        require_evaluation(settings, engine)
        self.engine, self.owner, self.other_owner, self.settings = engine, owner, other_owner, settings
        self.dataset = Dataset()
        self.events: dict[str, list[dict]] = {}

    def create(self, case):
        fixture = self.dataset.read(case.search)
        with owner_transaction(self.engine, self.owner) as repo:
            brief = repo.create(m.briefs, BriefCreate.model_validate(fixture["brief"]).model_dump(mode="json") | {"version": 1})
            body = RunCreate.model_validate({"brief_id": brief["id"], "budget": {"max_calls": 3 if case.id == "D16" else 60, "max_tokens": 32768, "max_cost_usd": "0"}})
            key = str(uuid4())
            run = repo.start(body, key)
            if case.id == "D17":
                assert repo.start(body, key) == run
                try:
                    repo.start(body.model_copy(update={"budget": body.budget.model_copy(update={"max_calls": 59})}), key)
                    raise AssertionError("changed_start_payload_accepted")
                except HTTPException as error:
                    assert error.status_code == 409
            run_id = UUID(str(run["id"]))
            repo.control(run_id, "resume", 1, str(uuid4()))
            job = repo.conn.execute(select(m.jobs).where(m.jobs.c.run_id == run_id, m.jobs.c.owner_id == repo.owner).with_for_update()).mappings().one()
            repo.conn.execute(update(m.jobs).where(m.jobs.c.id == job["id"]).values(workflow=dict(job["workflow"]) | {"evaluation": self.dataset.plan(case.id).model_dump(mode="json")}))
        return run_id

    def worker(self, case, run_id, *, crash=False):
        if case.id != "D13":
            return run_once(self.engine, self.owner, run_id=run_id, settings=self.settings)
        env = dict(os.environ, LATHER_ENVIRONMENT="test", LATHER_CHAOS_ENABLED="true", LATHER_EVALUATIONS_ENABLED="true", LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false")
        args = [sys.executable, "-m", "tools.eval_worker", "--run-id", str(run_id), "--lease-seconds", "2"]
        if crash:
            args.append("--interrupt")
        response = subprocess.run(args, env=env, capture_output=True, text=True, timeout=90)
        if crash:
            assert response.returncode == 23, "dedicated_worker_did_not_interrupt"
            return {"state": "interrupted", "exit_code": response.returncode, "actual_external_calls": 0}
        assert response.returncode == 0, "dedicated_worker_failed_details_suppressed"
        return json.loads(response.stdout)

    def approve(self, run_id, gate, *, idempotency_check=False):
        with owner_transaction(self.engine, self.owner) as repo:
            run = repo.get(m.runs, run_id)
            request = repo.conn.execute(select(m.approval_requests).where(m.approval_requests.c.owner_id == repo.owner,
                m.approval_requests.c.run_id == run_id, m.approval_requests.c.gate == gate, m.approval_requests.c.state == "pending")).mappings().one()
            body = DecisionCreate(request_id=request["id"], artifact_version=request["artifact_version"], artifact_hash=request["artifact_hash"],
                expected_run_version=run["version"], decision="approve")
            key = str(uuid4())
            decision = repo.decide(run_id, gate, body, key)
            if idempotency_check:
                assert repo.decide(run_id, gate, body, key) == decision
                try:
                    repo.decide(run_id, gate, body.model_copy(update={"decision": "reject"}), key)
                    raise AssertionError("changed_decision_payload_accepted")
                except HTTPException as error:
                    assert error.status_code == 409

    def deny_bad_approval(self, run_id, gate):
        with owner_transaction(self.engine, self.other_owner) as repo:
            try:
                repo.get(m.runs, run_id)
                raise AssertionError("cross_owner_run_visible")
            except HTTPException as error:
                assert error.status_code == 404
        for defect in ("request", "hash", "version"):
            with owner_transaction(self.engine, self.owner) as repo:
                run = repo.get(m.runs, run_id)
                request = repo.conn.execute(select(m.approval_requests).where(m.approval_requests.c.run_id == run_id,
                    m.approval_requests.c.owner_id == repo.owner, m.approval_requests.c.gate == gate, m.approval_requests.c.state == "pending")).mappings().one()
                body = DecisionCreate(request_id=uuid4() if defect == "request" else request["id"], artifact_version=request["artifact_version"],
                    artifact_hash="0" * 64 if defect == "hash" else request["artifact_hash"], expected_run_version=run["version"] + (defect == "version"), decision="approve")
                try:
                    repo.decide(run_id, gate, body, str(uuid4()))
                    raise AssertionError("invalid_approval_accepted")
                except HTTPException as error:
                    assert error.status_code in {404, 409}

    def capture(self, run_id):
        with owner_transaction(self.engine, self.owner) as repo:
            run = repo.get(m.runs, run_id)
            return {"run": run, "tasks": repo.list(m.research_tasks, run_id, limit=3), "reports": repo.list(m.reports, run_id, limit=5),
                "sources": repo.list(m.sources, run_id, limit=1000), "attempts": repo.list(m.tool_attempts, run_id, limit=1000),
                "events": repo.list(m.events, run_id, limit=10000), "requests": repo.list(m.approval_requests, run_id, limit=100),
                "decisions": repo.list(m.approval_decisions, run_id, limit=100), "usage": repo.list(m.usage, run_id, limit=1000),
                "job": dict(repo.conn.execute(select(m.jobs).where(m.jobs.c.run_id == run_id, m.jobs.c.owner_id == repo.owner)).mappings().one())}

    def execute(self, case):
        start, began = perf_counter(), datetime.now(timezone.utc)
        if case.mode != "graph":
            return self.component(case, start, began)
        run_id = self.create(case)
        diagnostics: dict[str, Any] = {"phase_results": [self.worker(case, run_id)]}
        if case.id == "D14":
            self.deny_bad_approval(run_id, "shortlist")
            assert not self.capture(run_id)["tasks"]
        if case.id == "D13":
            pending = self.capture(run_id)["requests"]
            diagnostics["phase_results"].append(self.worker(case, run_id))
            assert self.capture(run_id)["requests"] == pending
            diagnostics["pending_shortlist_preserved"] = True
        if case.id != "D03":
            self.approve(run_id, "shortlist", idempotency_check=case.id == "D17")
            if case.id == "D13":
                diagnostics["phase_results"].append(self.worker(case, run_id, crash=True))
                before = self.capture(run_id)
                assert len(before["tasks"]) == 1
                job = before["job"]
                stale = Lease(run_id, self.owner, job["worker_id"], job["generation"])
                sleep(2.2)
                diagnostics["phase_results"].append(self.worker(case, run_id))
                after = self.capture(run_id)
                diagnostics["preserved_task_and_sources"] = all(row in after["tasks"] for row in before["tasks"]) and all(row in after["sources"] for row in before["sources"])
                diagnostics["remaining_web_dispatches"] = diagnostics["phase_results"][-1]["recorded_web_dispatches"]
                try:
                    stale.check(self.engine)
                    raise AssertionError("stale_worker_not_fenced")
                except PolicyDenied:
                    diagnostics["stale_writer_fenced"] = True
                pending = self.capture(run_id)["requests"]
                self.worker(case, run_id)
                diagnostics["pending_report_preserved"] = self.capture(run_id)["requests"] == pending
            else:
                diagnostics["phase_results"].append(self.worker(case, run_id))
            if case.id == "D14":
                self.deny_bad_approval(run_id, "report")
                diagnostics["approval_negatives"] = 8  # Two actual owner checks and six invalid requests above.
            elif case.id == "D16":
                before = self.capture(run_id)
                with owner_transaction(self.engine, self.owner) as repo:
                    run = repo.get(m.runs, run_id)
                    repo.control(run_id, "cancel", run["version"], str(uuid4()))
                self.worker(case, run_id)
                diagnostics["partial_after_cancel_preserved"] = self.capture(run_id)["tasks"] == before["tasks"]
            elif case.id != "D10":
                assert self.capture(run_id)["run"]["status"] == "report_review"
                self.approve(run_id, "report", idempotency_check=case.id == "D17")
                diagnostics["phase_results"].append(self.worker(case, run_id))
                if case.id == "D17":
                    self.worker(case, run_id)
                    diagnostics["idempotency_checked"] = True
        snap = self.capture(run_id)
        self.events[case.id] = snap["events"]
        outcome = self.grade(case, run_id, snap, diagnostics, start, began)
        with owner_transaction(self.engine, self.owner) as repo:
            identifier = repo.create(m.evaluation_cases, {"case_id": case.id, "dataset_version": "lather-golden-v1", "data": {"label": "DEMO", "manifest_hash": self.dataset.manifest_hash}})["id"]
            repo.create(m.evaluation_results, {"run_id": run_id, "case_id": identifier, "outcome": "passed" if outcome.passed else "failed", "data": outcome.model_dump(mode="json")})
        return outcome

    def grade(self, case, run_id, snap, diagnostics, start, began):
        reports, tasks, sources, events = (snap[key] for key in ("reports", "tasks", "sources", "events"))
        latest = reports[-1]["data"]["analysis"] if reports else None
        grades = [grade_schema(reports, tasks), *grade_tools(events, snap["attempts"], snap["run"]["budget"]["max_calls"]),
            grade_trajectory(events, snap["run"]["status"], snap["requests"], snap["decisions"]),
            grade_candidates((snap["run"]["checkpoint"] or {}).get("artifact"), sources, case.expected_competitors)]
        if case.expected_units:
            grades.append(grade_math(latest["normalized_prices"] if latest else [], case.expected_units))
        special = self.specific(case, snap, diagnostics)
        grades.append(result(case.id, snap["run"]["status"] == case.expected_status and special, "Declared case outcome and its fault/negative-control assertions."))
        citations = citation_diagnostics(latest, sources) if latest else None
        usage = snap["usage"]
        delays: list[float] = next((row["data"]["virtual_delays_seconds"] for row in events if row["kind"] == "evaluation.retry_clock"), [])
        metrics = RunMeasurement(started_at=began, ended_at=datetime.now(timezone.utc), latency_ms=round((perf_counter() - start) * 1000),
            completed_calls=sum(row["calls"] for row in usage), reserved_calls=sum(row["state"] == "reserved" for row in snap["attempts"]),
            model_replay_attempts=sum((row.get("outcome") or {}).get("schema_version") == "model-replay-1.0" for row in snap["attempts"]),
            provider_cost_usd=Decimal(0), cost_upper_bound_usd=sum((row["cost_usd"] for row in usage), Decimal(0)), virtual_retry_delays_seconds=tuple(delays))
        signature = {"status": snap["run"]["status"], "competitors": len((snap["run"]["checkpoint"] or {}).get("artifact", {}).get("competitor_ids", [])),
            "nodes": [row["data"]["node"] for row in events if row["kind"] == "workflow.node"], "reports": len(reports), "tasks": len(tasks),
            "attempts_by_tool": dict(sorted(Counter(row["data"].get("tool", "model.generate") for row in events if row["kind"] in {"tool.reserved", "model.replay_reserved"}).items())),
            "model_invalid": sum(row["kind"] == "model.output_invalid" for row in events), "revisions": sum(row["kind"] == "workflow.node" and row["data"]["node"] == "revise" for row in events)}
        diagnostics["citations"] = citations
        return CaseOutcome(case_id=case.id, run_id=run_id, status=snap["run"]["status"], grades=tuple(grades), measurement=metrics, signature=signature, diagnostics=diagnostics)

    def specific(self, case, snap, diagnostics):
        tasks, events, reports = (snap[key] for key in ("tasks", "events", "reports"))
        latest: dict[str, Any] = reports[-1]["data"]["analysis"] if reports else {}
        if case.id == "D03":
            return not tasks and not reports and not snap["decisions"]
        if case.id == "D04":
            before: dict[str, Any] = next((row["data"] for row in events if row["kind"] == "evaluation.partial_before_timeout"), {})
            by_id = {str(row["id"]): digest(row["data"]) for row in tasks}
            return before.get("count") == 2 and all(by_id.get(key) == value for key, value in before.get("task_hashes", {}).items()) and any("news_search_timeout" in row["data"]["limitations"] for row in tasks) and sum(row["kind"] == "tool.retryable_failure" and row["data"]["code"] == "timeout" for row in events) == 3
        if case.id == "D06":
            return any(row["access_status"] == "denied" and "demo-b.invalid" in row["canonical_url"] for row in snap["sources"]) and any(any("access" in limit for limit in row["data"]["limitations"]) for row in tasks)
        if case.id == "D07":
            return bool(latest["conflicts"]) and len({p["source_id"] for p in latest["normalized_prices"] if p["sku"] == "DEMO-A-100"}) == 2
        if case.id == "D08":
            return any(f["field"] == "ingredients" and f["value"] is None and f["unavailable_reason"] for f in latest["findings"])
        if case.id == "D09":
            return any(p["sku"] == "DEMO-A-100" and p["unit_price_100g"] is None and p["unavailable_reason"] for p in latest["normalized_prices"])
        if case.id == "D10":
            return len(tasks) == 3 and not reports and sum(e["kind"] == "model.output_invalid" for e in events) == 2 and not any(r["gate"] == "report" for r in snap["requests"])
        if case.id == "D11":
            return any(f["field"] == "marketing_claim" and "eczema" in str(f["value"]) and f["kind"] == "source_claim" for f in latest["findings"]) and not any(f["kind"] == "fact" and "eczema" in f["text"] for f in latest["findings"])
        if case.id == "D12":
            return len(reports) == 2 and any(f["field"] == "medical_efficacy" for f in reports[0]["data"]["analysis"]["findings"]) and not any(f["field"] == "medical_efficacy" for f in latest["findings"]) and sum(e["kind"] == "workflow.node" and e["data"]["node"] == "revise" for e in events) == 1
        if case.id == "D13":
            return all(diagnostics.get(key) for key in ("preserved_task_and_sources", "stale_writer_fenced", "pending_shortlist_preserved", "pending_report_preserved")) and diagnostics["remaining_web_dispatches"] == 6
        if case.id == "D14":
            return diagnostics.get("approval_negatives") == 8 and not any(r["gate"] == "report" and r["state"] == "decided" for r in snap["requests"])
        if case.id == "D16":
            return len(snap["attempts"]) <= 3 and diagnostics.get("partial_after_cancel_preserved") and not any(d["decision"] == "approve" and any(r["id"] == d["request_id"] and r["gate"] == "report" for r in snap["requests"]) for d in snap["decisions"])
        if case.id == "D17":
            return diagnostics.get("idempotency_checked") and len(reports) == 1 and len(snap["decisions"]) == 2
        return True

    def component(self, case, start, began):
        if case.id == "D05":
            from app.adapters.tavily import TavilyAdapter
            from app.api_schemas import BriefCreate
            from app.harness.gateway import SearchGateway
            from app.harness.recordings import RecordedTavily
            from app.harness.search import SearchCost
            from app.services.discovery import search
            from tests.scout_support import Clock, MemoryLedger, context
            actual: list[dict[str, Any]] = []
            signature: dict[str, Any]
            for filename in ("search-429.json", "search-deadline.json"):
                tape, clock, ledger = RecordedTavily(FOLDER / filename), Clock(), MemoryLedger()
                gateway = SearchGateway(TavilyAdapter(tape.transport), ledger, SearchCost(per_attempt_upper_bound_usd=Decimal(0), pricing_version="DEMO"), clock.now, clock.sleep, lambda: 0)
                sources, stop = search(context(), BriefCreate.model_validate(tape.case["brief"]), gateway)
                tape.assert_finished()
                retry_after = float(tape.case["steps"][0].get("headers", {}).get("Retry-After", 0))
                actual.append({"dispatches": tape.ordinal, "stop": stop, "sources": len(sources), "delays": clock.delays, "retry_after": retry_after,
                    "completed_attempts": len(ledger.rows)})
            good = actual[0]["dispatches"] == actual[0]["completed_attempts"] == 2 and actual[0]["sources"] > 0 and actual[0]["delays"][0] >= actual[0]["retry_after"] and actual[1]["dispatches"] == actual[1]["completed_attempts"] == 1 and actual[1]["stop"] == "deadline" and not actual[1]["delays"]
            signature = {"subcases": actual}
            calls = sum(row["dispatches"] for row in actual)
        else:
            from app.history import compare
            from tests.history_support import history_document
            before, bm = history_document()
            changed, cm = history_document("price", later=True)
            missing, mm = history_document("unavailable", later=True)
            price, gap = compare(before, changed, bm, cm), compare(before, missing, bm, mm)
            rows = [row for row in price.changes if row.brand == "DEMO Maker A" and row.field == "price" and row.status == "changed"]
            old_value = rows[0].before.values[0] if rows else None
            new_value = rows[0].after.values[0] if rows else None
            good = len(rows) == 1 and isinstance(old_value, dict) and old_value.get("amount") == "120" and isinstance(new_value, dict) and new_value.get("amount") == "140" and gap.counts["gone"] == 0 and gap.counts["unknown"] >= 1
            signature = {"price_counts": price.counts, "gap_counts": gap.counts}
            calls = 0
        grades = tuple(result(name, good, "Actual deterministic component subcases; not an end-to-end workflow/semantic review.") for name in case.checks)
        measurement = RunMeasurement(started_at=began, ended_at=datetime.now(timezone.utc), latency_ms=round((perf_counter() - start) * 1000), completed_calls=calls,
            reserved_calls=0, model_replay_attempts=0, provider_cost_usd=Decimal(0), cost_upper_bound_usd=Decimal(0))
        self.events[case.id] = []
        return CaseOutcome(case_id=case.id, run_id=None, status="component_complete", grades=grades, measurement=measurement, signature=signature, diagnostics={"scope": "component"})
