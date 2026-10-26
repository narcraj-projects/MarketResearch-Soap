"""One targeted model correction after the evidence supplement, never approval."""

import json
from uuid import UUID, uuid4
from sqlalchemy import create_engine, update
from app import models as m
from app.repository import owner_transaction
from app.harness.lease import JobQueue
from app.harness.live_policy import ROOT, load_permit
from app.harness.checkpointer import OwnerPostgresSaver
from app.adapters.live_web import LivePublicWeb
from app.live_workflow import LiveWorkflow, LiveTavilyAdapter
from app.workflow import build_graph
from tools.workflow_demo import local_config


def main():
    cfg = local_config()
    owner = UUID(cfg["users"][0]["id"])
    run_id = UUID(
        json.loads((ROOT / ".cache/live-authorization.json").read_text())["run_id"]
    )
    permit = load_permit(run_id, owner)
    engine = create_engine(cfg["runtime_url"], hide_parameters=True)
    with owner_transaction(engine, owner) as repo:
        run = repo.get(m.runs, run_id)
        cp = dict(run["checkpoint"])
        report = repo.report(run_id)
        critique = report["data"]["live_narrative"]["critique"]
        if (
            run["status"] != "partial"
            or report["version"] != 2
            or cp.get("live_narrative_correction")
            or critique["decision"] != "unresolved"
        ):
            raise ValueError("only_one_targeted_correction_of_supplemented_v2")
        cp["live_narrative_correction"] = {
            "prior_report_id": str(report["id"]),
            "targets": critique["issues"],
            "bounded_corrections": 1,
        }
        repo.conn.execute(
            update(m.runs)
            .where(m.runs.c.id == run_id, m.runs.c.owner_id == owner)
            .values(status="researching", checkpoint=cp, version=run["version"] + 1)
        )
        repo.conn.execute(
            update(m.jobs)
            .where(m.jobs.c.run_id == run_id, m.jobs.c.owner_id == owner)
            .values(state="queued")
        )
        repo.event(
            run_id,
            "analysis.targeted_correction",
            {
                "label": "LIVE",
                "prior_version": 2,
                "issue_count": len(critique["issues"]),
                "correction_limit": 1,
            },
        )
    queue = JobQueue(engine, owner)
    lease = queue.claim(uuid4(), 120, run_id)
    if lease is None:
        raise ValueError("lease_unavailable")
    try:
        workflow = LiveWorkflow(
            engine,
            lease,
            queue.deadline(run_id),
            LiveTavilyAdapter(permit),
            LivePublicWeb(permit),
            permit=permit,
        )
        graph = build_graph(workflow, OwnerPostgresSaver(engine, lease))
        graph.update_state(
            {"configurable": {"thread_id": str(run_id)}},
            {
                "phase": "analyze",
                "revision": 2,
                "revision_limit": 2,
                "prior_report_id": None,
                "report_id": None,
                "request_id": None,
                "final": None,
                "review_ok": False,
                "review_decision": None,
                "issues": critique["issues"],
            },
            as_node="normalize",
        )
        print(
            "PASS one targeted correction scheduled. Prior reports retained; final approval remains mandatory."
        )
    finally:
        queue.release(lease, done=False)
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit(
            "Targeted correction stopped ("
            + type(error).__name__
            + "); private details suppressed"
        ) from None
