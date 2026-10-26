"""Isolated, manifest-pinned golden execution. Never selected by HTTP input."""
from datetime import datetime, timedelta, timezone
from threading import Event, Lock

from app import models as m
from app.chaos_workflow import ChaosWorkflow
from app.evaluations.dataset import Dataset, require_evaluation
from app.harness.chaos import plan as chaos_plan
from app.harness.contracts import Versions
from app.harness.model_replay import ModelReplayGateway
from app.harness.policy import PolicyDenied
from app.harness.retrieval import ResearchGateway
from app.agents.researcher import research_parallel
from app.repository import digest
from app.workflow import Workflow


class RetryClock:
    """Virtual retry delay only; wall latency is measured separately by the runner."""
    def __init__(self):
        self.time = datetime.now(timezone.utc) - timedelta(seconds=30)
        self.delays: list[float] = []
        self.lock = Lock()

    def now(self):
        with self.lock:
            return self.time

    def sleep(self, delay):
        with self.lock:
            self.delays.append(delay)
            self.time += timedelta(seconds=delay)


class EvaluationWorkflow(Workflow):
    def __init__(self, *args, plan, settings, interrupt_worker=None, **kwargs):
        require_evaluation(settings, args[0])
        Dataset().validate_plan(plan)
        super().__init__(*args, **kwargs)
        self.plan, self.settings, self.interrupt_worker = plan, settings, interrupt_worker

    def note(self, kind, data):
        with self.transaction() as repo:
            self.lease.guard(repo)
            repo.event(self.lease.run_id, kind, {"label": "DEMO", "case_id": self.plan.case_id, **data})

    def research(self, state):
        if self.plan.case_id == "D13":
            # Reuse the already fenced real process-interruption boundary.
            helper = ChaosWorkflow(self.engine, self.lease, self.deadline, self.scout, self.web,
                plan=chaos_plan("interrupted_worker"), settings=self.settings, interrupt_worker=self.interrupt_worker)
            return helper.research(state)
        if self.plan.case_id != "D04":
            return super().research(state)
        self.check(state, tools=True)
        versions = Versions(graph="research-1.0", model="none", provider="none", prompt="attributed-extraction-1.0", tools="public-research-1.0", dataset="research-demo-v1")
        context, competitors = self.research_store.begin(self.lease.run_id, self.lease.owner_id, self.deadline, versions)
        third = next(row["id"] for row in competitors if row["name"] == "DEMO Maker C")
        saved, gate, lock = set(), Event(), Lock()
        original_save = self.research_store.save_task

        def save(ctx, cid, sources, limitations):
            result = original_save(ctx, cid, sources, limitations)
            if cid != third:
                with lock:
                    saved.add(cid)
                    if len(saved) == 2:
                        gate.set()
            return result

        workflow = self
        class OrderedGateway(ResearchGateway):
            def news(inner, ctx, cid, name):
                # Wait BEFORE entering _wire's per-origin lock. Waiting inside a
                # transport callback would prevent the other lanes' news calls.
                if cid != third:
                    return super().news(ctx, cid, name)
                if not gate.wait(10):
                    raise PolicyDenied("golden_prior_lanes_not_saved")
                with workflow.transaction() as repo:
                    workflow.lease.guard(repo)
                    tasks = repo.list(m.research_tasks, workflow.lease.run_id, limit=3)
                    repo.event(workflow.lease.run_id, "evaluation.partial_before_timeout", {"label": "DEMO", "count": len(tasks),
                        "task_hashes": {str(row["id"]): digest(row["data"]) for row in tasks}})
                return super().news(ctx, cid, name)
        setattr(self.research_store, "save_task", save)
        clock = RetryClock()
        research_parallel(context, competitors, OrderedGateway(self.web, self.research_store, clock=clock.now, sleep=clock.sleep,
            guard=lambda: self.lease.check(self.engine)), self.research_store)
        self.note("evaluation.retry_clock", {"virtual_delays_seconds": clock.delays})
        self.event(state, "research")
        return {"phase": "normalize"}

    def draft(self, state):
        data = super().draft(state)
        if state.revision == 0 and self.plan.case_id in {"D10", "D12"}:
            versions = Versions(graph="research-1.0", model="none", provider="none", prompt="attributed-extraction-1.0", tools="public-research-1.0", dataset="research-demo-v1")
            context, _ = self.research_store.begin(self.lease.run_id, self.lease.owner_id, self.deadline, versions)
            data["analysis"] = ModelReplayGateway(self.engine, self.lease, context, self.plan.case_id, self.settings).run(data["analysis"])
        return data
