"""Explicit replay worker with heartbeat, fenced checkpointing and DB-only resumes."""
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from threading import Event, Thread
from uuid import UUID, uuid4

from langgraph.types import Command
from langsmith import tracing_context
from sqlalchemy import select

from app import models as m
from app.adapters.public_web import RecordedWeb
from app.harness.checkpointer import GRAPH_VERSION, OwnerPostgresSaver
from app.harness.lease import JobQueue
from app.harness.policy import PolicyDenied
from app.harness.recordings import RecordedTavily
from app.repository import owner_transaction
from app.workflow import Workflow, WorkflowState, build_graph
from app.config import Settings


@contextmanager
def heartbeat(queue: JobQueue, lease, seconds: int):
    stop = Event()
    lost = Event()
    def beat():
        while not stop.wait(seconds / 3):
            try:
                queue.heartbeat(lease, seconds)
            except Exception:
                lost.set()
                return
    thread = Thread(target=beat, name="lather-lease-heartbeat", daemon=True)
    thread.start()
    try:
        yield lost
    finally:
        stop.set()
        thread.join(timeout=2)


def run_once(engine, owner_id: UUID, *, lease_seconds: int = 30, workflow_factory=Workflow, run_id: UUID | None = None,
             settings: Settings | None = None, interrupt_worker=None) -> dict:
    queue = JobQueue(engine, owner_id)
    lease = queue.claim(uuid4(), lease_seconds, run_id)
    if lease is None:
        return {"state": "idle", "actual_external_calls": 0}
    scout: Any = None
    web: Any = None
    live = False
    try:
        with heartbeat(queue, lease, lease_seconds), tracing_context(enabled=False):
            with owner_transaction(engine, owner_id) as repo:
                lease.guard(repo)
                job = repo.conn.execute(select(m.jobs).where(m.jobs.c.run_id == lease.run_id, m.jobs.c.owner_id == owner_id)).mappings().one()
            options = dict(job["workflow"])
            chaos = options.pop("chaos", None)
            evaluation = options.pop("evaluation", None)
            live = options == {"graph_version": GRAPH_VERSION, "revision_limit": 1, "mode": "live"}
            if not live and options != {"graph_version": GRAPH_VERSION, "revision_limit": 1, "scout_case": "SC01-clean", "research_case": "R21-parallel", "mode": "replay"}:
                raise PolicyDenied("workflow_version_mismatch")
            fixtures = Path(__file__).resolve().parents[1] / "evaluations/fixtures"
            workflow: Workflow
            if live:
                if chaos is not None or evaluation is not None or workflow_factory is not Workflow:
                    raise PolicyDenied("live_plan_mismatch")
                from app.harness.live_policy import load_permit
                from app.live_workflow import LiveWorkflow, LiveTavilyAdapter
                from app.adapters.live_web import LivePublicWeb
                permit = load_permit(lease.run_id, owner_id)
                scout = LiveTavilyAdapter(permit)
                web = LivePublicWeb(permit)
                workflow = LiveWorkflow(engine, lease, job["deadline"], scout, web, permit=permit)
            elif evaluation is not None:
                from app.evaluations.contracts import EvalPlan
                from app.evaluations.dataset import Dataset, FOLDER, require_evaluation
                from app.evaluations.workflow import EvaluationWorkflow
                config_settings = settings if settings is not None else Settings()
                require_evaluation(config_settings, engine)
                selected_plan = EvalPlan.model_validate(evaluation)
                selected_case = Dataset().validate_plan(selected_plan)
                if chaos is not None or workflow_factory is not Workflow or selected_case.mode != "graph" or (selected_case.id == "D13" and interrupt_worker is None):
                    raise PolicyDenied("dedicated_evaluation_worker_required")
                scout = RecordedTavily(FOLDER / selected_case.search)
                web = RecordedWeb(FOLDER / selected_case.web)
                workflow = EvaluationWorkflow(engine, lease, job["deadline"], scout, web, plan=selected_plan,
                    settings=config_settings, interrupt_worker=interrupt_worker)
                workflow.note("evaluation.plan_loaded", {"manifest_hash": selected_plan.manifest_hash})
            elif chaos is None:
                scout = RecordedTavily(fixtures / "scout-v1/SC01-clean.json")
                web = RecordedWeb(fixtures / "research-v1/R21-parallel.json")
                workflow = workflow_factory(engine, lease, job["deadline"], scout, web)
            else:
                from app.harness.chaos import ChaosPlan, FOLDER, scenario_files, require_isolated_engine
                from app.chaos_workflow import ChaosWorkflow
                config_settings = settings if settings is not None else Settings()
                plan = ChaosPlan.model_validate(chaos)
                selected = scenario_files(plan, config_settings)
                require_isolated_engine(engine)
                if workflow_factory is not Workflow or (plan.scenario == "interrupted_worker" and interrupt_worker is None):
                    raise PolicyDenied("dedicated_test_worker_required")
                scout = RecordedTavily(FOLDER / selected["search"])
                web = RecordedWeb(FOLDER / selected["web"])
                workflow = ChaosWorkflow(engine, lease, job["deadline"], scout, web, plan=plan, settings=config_settings, interrupt_worker=interrupt_worker)
                workflow.note("chaos.plan_loaded", {"manifest_hash": plan.manifest_hash, "actual_external_calls": 0})
            graph = build_graph(workflow, OwnerPostgresSaver(engine, lease))
            config = {"configurable": {"thread_id": str(lease.run_id)}, "recursion_limit": 40}
            snapshot = graph.get_state(config)
            payload: Any = None
            waiting = next((item for task in snapshot.tasks for item in task.interrupts), None)
            if waiting:
                request_id = UUID(waiting.value["request_id"])
                with owner_transaction(engine, owner_id) as repo:
                    lease.guard(repo)
                    decision = repo.conn.execute(select(m.approval_decisions.c.id).where(m.approval_decisions.c.request_id == request_id,
                        m.approval_decisions.c.owner_id == owner_id, m.approval_decisions.c.run_id == lease.run_id)).scalar_one_or_none()
                if decision:
                    payload = Command(resume=str(decision))
                else:
                    queue.release(lease, waiting_request=request_id)
                    return {"label": "LIVE" if live else "DEMO", "state": "approval_pending", "run_id": str(lease.run_id), "actual_external_calls": 0}
            elif not snapshot.values:
                payload = WorkflowState(run_id=str(lease.run_id)).model_dump(mode="json")
            if payload is not None or snapshot.next:
                # Synchronous durability waits for checkpoint commit before advancing nodes.
                graph.invoke(payload, config, durability="sync")
            snapshot = graph.get_state(config)
            waiting = next((item for task in snapshot.tasks for item in task.interrupts), None)
            queue.release(lease, waiting_request=UUID(waiting.value["request_id"]) if waiting else None)
            return {"label": "LIVE" if live else "DEMO", "run_id": str(lease.run_id), "state": "approval_pending" if waiting else "finished",
                "recorded_search_dispatches": 0 if live else scout.ordinal, "recorded_web_dispatches": 0 if live else len(web.requests),
                "actual_external_calls": None if live else 0, "live_tool_dispatches": scout.ordinal + len(web.requests) if live else 0, "mode": "live" if live else "replay"}
    except PolicyDenied as error:
        code = str(error)
        if code not in {"lease_lost_or_cancelled", "lease_owner_mismatch"}:
            try:
                queue.release(lease, failure="workflow_policy_stop")
            except PolicyDenied:
                pass
        return {"label": "LIVE" if live else "DEMO", "run_id": str(lease.run_id), "state": "stopped", "code": code if live else "workflow_policy_stop", "actual_external_calls": None if live else 0}
    except Exception:
        try:
            queue.release(lease, failure="worker_failed")
        except PolicyDenied:
            pass
        raise
