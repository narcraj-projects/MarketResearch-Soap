"""Fenced recorded model-output handoff. Synthetic fixtures; no LLM SDK/transport."""
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from uuid import uuid5

from pydantic import ValidationError
from sqlalchemy import select, update

from app import models as m
from app.harness.analysis_types import AnalysisDraft
from app.repository import digest, owner_transaction
from .contracts import Budget, ModelCall, Phase, Role, RunContext, Versions
from .chaos import read_fixture, require_test_mode, require_isolated_engine
from .policy import PolicyDenied, authorize, authorize_access
from .replay import ReplayRequest, ReplayStep, ReplayTape


class ModelReplayGateway:
    """Recorded response projection from frozen DEMO rule output, not a selected model."""
    def __init__(self, engine, lease, context, scenario, settings):
        if scenario in {"D10", "D12"}:
            from app.evaluations.dataset import require_evaluation
            require_evaluation(settings, engine)
        else:
            require_test_mode(settings)
        require_isolated_engine(engine)
        context = RunContext.model_validate(context.model_dump())
        if context.run_id != lease.run_id or context.user_id != lease.owner_id:
            raise PolicyDenied("model_context_scope_mismatch")
        self.engine, self.lease, self.context, self.scenario = engine, lease, context, scenario

    def run(self, baseline: dict) -> dict:
        golden = self.scenario in {"D10", "D12"}
        if golden:
            from app.evaluations.dataset import Dataset
            recording = Dataset().read("model-scripts.json")
        else:
            recording = read_fixture("model-templates.json")
        if recording.get("schema_version") != "model-fixtures-1.0":
            raise PolicyDenied("model_recording_version_mismatch")
        templates = recording[self.scenario]
        if not 1 <= len(templates) <= 2:
            raise PolicyDenied("model_recording_attempt_limit")
        versions = Versions(graph="workflow-1.2", provider="none", model="none", prompt="DEMO-frozen-analysis-1.0", tools="model-replay-1.0", dataset="lather-golden-v1" if golden else "chaos-demo-v1")
        context = self.context.model_copy(update={"phase": Phase.ANALYZE, "versions": versions})
        operation = uuid5(context.run_id, "chaos:model:" + self.scenario)
        projected = json.loads(json.dumps(baseline))
        steps = []
        for attempt, template in enumerate(templates, 1):
            if set(template) not in ({"raw"}, {"template"}) or ("template" in template and template["template"] not in {"frozen_analysis", "wrong_unit_price", "unsupported_material_claim"}):
                raise PolicyDenied("model_recording_template_mismatch")
            output = json.loads(json.dumps(projected))
            if template.get("template") == "wrong_unit_price":
                target = next(row for row in output["normalized_prices"] if row["unit_price_100g"] is not None)
                target["unit_price_100g"] = "999"
            if template.get("template") == "unsupported_material_claim":
                from .analysis_types import Finding
                original = next(row for row in output["findings"] if row["evidence"] and row["kind"] == "fact")
                injected = Finding(finding_id=uuid5(context.run_id, "DEMO-unsupported-material"), competitor_id=original["competitor_id"],
                    source_id=original["source_id"], field="medical_efficacy", value="DEMO soap cures eczema", kind="fact", text="DEMO soap cures eczema.", evidence=original["evidence"])
                output["findings"].append(injected.model_dump(mode="json"))
            raw = template.get("raw", json.dumps(output, sort_keys=True))
            request = ReplayRequest(kind="model", operation=str(operation), attempt=attempt, versions=versions,
                arguments={"input_hash": digest(baseline), "prompt_id": "DEMO-frozen-analysis-1.0", "max_output_tokens": 16384})
            steps.append(ReplayStep(request=request, raw_response=raw, response_hash=sha256(raw.encode()).hexdigest()))
        tape = ReplayTape(tuple(steps))
        for step in steps:
            call = ModelCall(operation_id=operation, agent=Role.ANALYST, attempt=step.request.attempt, tool="model.generate",
                prompt_id="DEMO-frozen-analysis-1.0", input_hash=digest(baseline), max_output_tokens=16384)
            authorize_access(context, call, datetime.now(timezone.utc))
            fingerprint = digest(step.request.model_dump(mode="json"))
            identifier = uuid5(context.run_id, f"model:{operation}:{call.attempt}")
            with owner_transaction(self.engine, context.user_id) as repo:
                run = self.lease.guard(repo)
                if run["status"] != "researching" or run["version"] != context.run_version:
                    raise PolicyDenied("stale_model_context")
                from .research_store import ResearchStore
                pending, decision = ResearchStore(self.engine, self.lease)._approved(repo, run)
                if context.shortlist_hash != pending["artifact_hash"] or len(context.approvals) != 1 or context.approvals[0].decision_id != decision["id"]:
                    raise PolicyDenied("shortlist_approval_required")
                prior = repo.conn.execute(select(m.tool_attempts).where(m.tool_attempts.c.id == identifier, m.tool_attempts.c.owner_id == repo.owner)).mappings().first()
                if prior:
                    if prior["request_hash"] != fingerprint or prior["state"] != "completed":
                        raise PolicyDenied("uncertain_or_changed_model_replay")
                    cached = prior["outcome"]
                else:
                    usage = repo.list(m.usage, context.run_id, limit=10000)
                    reservations = repo.list(m.tool_attempts, context.run_id, limit=10000)
                    budget = Budget(max_calls=run["budget"]["max_calls"], max_tokens=run["budget"]["max_tokens"], max_cost=run["budget"]["max_cost_usd"],
                        used_calls=len([row for row in reservations if row["state"] == "completed"]), reserved_calls=len([row for row in reservations if row["state"] == "reserved"]),
                        used_tokens=sum(row["tokens"] for row in usage), used_cost=sum((row["cost_usd"] for row in usage), Decimal(0)))
                    authorize(context.model_copy(update={"budget": budget}), call, datetime.now(timezone.utc))
                    repo.conn.execute(m.tool_attempts.insert().values(id=identifier, owner_id=repo.owner, run_id=context.run_id, operation_id=operation,
                        attempt=call.attempt, request_hash=fingerprint, cost_upper_bound_usd=0, state="reserved", outcome=None))
                    repo.event(context.run_id, "model.replay_reserved", {"label": "DEMO", "attempt": call.attempt, "input_hash": call.input_hash,
                        "operation_id": str(operation), "versions": versions.model_dump(mode="json"), "origin": "synthetic_frozen_rule_projection"})
                    cached = None
            raw = tape.consume(step.request)
            if cached is not None:
                if cached["response_hash"] != sha256(raw.encode()).hexdigest() or cached["raw_response"] != raw:
                    raise PolicyDenied("model_replay_payload_mismatch")
            else:
                # No provider call. The only permitted response is the pinned projected fixture.
                with owner_transaction(self.engine, context.user_id) as repo:
                    self.lease.guard(repo)
                    repo.conn.execute(update(m.tool_attempts).where(m.tool_attempts.c.id == identifier).values(state="completed", outcome={"schema_version": "model-replay-1.0",
                        "label": "DEMO", "request": step.request.model_dump(mode="json"), "raw_response": raw, "response_hash": sha256(raw.encode()).hexdigest(), "actual_model_calls": 0}))
                    repo.create(m.usage, {"run_id": context.run_id, "operation_id": operation, "attempt": call.attempt, "calls": 1, "tokens": 0, "cost_usd": "0"})
            try:
                parsed = AnalysisDraft.model_validate_json(raw)
            except (ValidationError, ValueError):
                with owner_transaction(self.engine, context.user_id) as repo:
                    self.lease.guard(repo)
                    if cached is None:
                        repo.event(context.run_id, "model.output_invalid", {"label": "DEMO", "attempt": call.attempt, "operation_id": str(operation), "code": "schema_invalid", "repair_limit": 1})
                continue
            with owner_transaction(self.engine, context.user_id) as repo:
                self.lease.guard(repo)
                if cached is None:
                    repo.event(context.run_id, "model.replay_validated", {"label": "DEMO", "attempt": call.attempt, "operation_id": str(operation), "repaired": call.attempt > 1,
                        "response_hash": sha256(raw.encode()).hexdigest(), "actual_model_calls": 0})
            tape.assert_finished()
            return parsed.model_dump(mode="json")
        raise PolicyDenied("model_repair_exhausted")
