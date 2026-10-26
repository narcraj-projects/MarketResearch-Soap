"""Explicitly gated DEMO workflow. Faults alter recorded boundaries, never approval policy."""
from contextlib import contextmanager
from threading import Barrier, Event
from uuid import UUID

from sqlalchemy import select

from app import models as m
from app.harness.chaos import require_test_mode
from app.harness.model_replay import ModelReplayGateway
from app.harness.policy import PolicyDenied
from app.workflow import Workflow


class ChaosWorkflow(Workflow):
    def __init__(self, *args, plan, settings, interrupt_worker=None, **kwargs):
        require_test_mode(settings)
        super().__init__(*args, **kwargs)
        self.plan, self.settings, self.interrupt_worker = plan, settings, interrupt_worker

    def note(self, kind: str, data: dict):
        with self.transaction() as repo:
            self.lease.guard(repo)
            exists = repo.conn.execute(select(m.events.c.id).where(m.events.c.run_id == self.lease.run_id,
                m.events.c.owner_id == repo.owner, m.events.c.kind == kind)).first()
            if not exists:
                repo.event(self.lease.run_id, kind, {"label": "DEMO", "scenario": self.plan.scenario, **data})

    def discover(self, state):
        result = super().discover(state)
        if self.plan.scenario in {"timeout", "rate_limit", "empty_results"}:
            with self.transaction() as repo:
                run = self.lease.guard(repo)
                count = len(run["checkpoint"]["artifact"]["competitor_ids"])
            self.note("chaos.observed", {"selected_competitors": count, "phase": "discover"})
        return result

    def research(self, state):
        require_test_mode(self.settings)
        if self.plan.scenario != "interrupted_worker":
            result = super().research(state)
            self.note("chaos.research_observed", {"phase": "research"})
            return result
        with self.transaction() as repo:
            run = self.lease.guard(repo)
            before = repo.list(m.research_tasks, self.lease.run_id, limit=3)
            target = UUID(run["checkpoint"]["artifact"]["competitor_ids"][0])
        if before:
            result = super().research(state)
            self.note("chaos.worker_recovered", {"preserved_lanes": len(before), "preserved_task_ids": [str(row["id"]) for row in before]})
            return result
        if self.interrupt_worker is None:
            raise PolicyDenied("dedicated_test_worker_required")
        original_lane, original_save = self.research_store.lane, self.research_store.save_task
        entered, blocked = Barrier(3, timeout=10), Event()

        @contextmanager
        def lane(context, cid):
            entered.wait()
            if cid != target:
                blocked.wait(20)
                raise PolicyDenied("test_worker_interruption_missing")
            with original_lane(context, cid):
                yield

        def save(*args, **kwargs):
            original_save(*args, **kwargs)
            self.note("chaos.worker_interrupted", {"preserved_lanes": 1, "competitor_id": str(target)})
            self.interrupt_worker()  # Only the separately gated local CLI supplies process termination.
            raise PolicyDenied("test_worker_interruption_missing")

        setattr(self.research_store, "lane", lane)
        setattr(self.research_store, "save_task", save)
        return super().research(state)

    def draft(self, state):
        data = super().draft(state)
        if state.revision != 0 or self.plan.scenario not in {"malformed_json", "reviewer_rejection"}:
            return data
        from app.harness.contracts import Versions
        versions = Versions(graph="research-1.0", model="none", provider="none", prompt="attributed-extraction-1.0", tools="public-research-1.0", dataset="research-demo-v1")
        context, _ = self.research_store.begin(self.lease.run_id, self.lease.owner_id, self.deadline, versions)
        data["analysis"] = ModelReplayGateway(self.engine, self.lease, context, self.plan.scenario, self.settings).run(data["analysis"])
        return data
