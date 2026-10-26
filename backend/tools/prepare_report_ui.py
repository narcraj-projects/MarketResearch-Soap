"""Explicit local-only DEMO browser fixtures. No credentials in output/artifacts."""
import json
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import create_engine, select

from app import models as m
from app.api_schemas import BriefCreate, DecisionCreate, RunCreate
from app.harness.recordings import RecordedTavily
from app.repository import owner_transaction
from tools.workflow_demo import local_config, run_local


def main():
    cfg = local_config()  # Exact dedicated loopback ports plus database identity marker.
    owner = UUID(cfg["users"][0]["id"])
    engine = create_engine(cfg["runtime_url"], hide_parameters=True)
    def create():
        recording = RecordedTavily(Path("evaluations/fixtures/scout-v1/SC01-clean.json"))
        with owner_transaction(engine, owner) as repo:
            brief = repo.create(m.briefs, BriefCreate.model_validate(recording.case["brief"]).model_dump(mode="json") | {"version": 1})
            run = repo.start(RunCreate(brief_id=brief["id"], budget={"max_calls": 40, "max_tokens": 0, "max_cost_usd": "0"}), str(uuid4()))
            run_id = UUID(str(run["id"]))
            repo.control(run_id, "resume", run["version"], str(uuid4()))
        run_local(run_id)
        return run_id
    def approve(run_id, gate):
        with owner_transaction(engine, owner) as repo:
            run = repo.get(m.runs, run_id)
            pending = repo.conn.execute(select(m.approval_requests).where(m.approval_requests.c.run_id == run_id,
                m.approval_requests.c.owner_id == owner, m.approval_requests.c.gate == gate, m.approval_requests.c.state == "pending")).mappings().one()
            repo.decide(run_id, gate, DecisionCreate(request_id=pending["id"], artifact_version=pending["artifact_version"],
                artifact_hash=pending["artifact_hash"], expected_run_version=run["version"], decision="approve"), str(uuid4()))
        run_local(run_id)
    try:
        shortlist = create()
        review = create()
        approve(review, "shortlist")
        saved = create()
        approve(saved, "shortlist")
        approve(saved, "report")
        ids = {"shortlist": str(shortlist), "review": str(review), "saved": str(saved)}
        (Path(__file__).resolve().parents[2] / ".cache/report-ui.json").write_text(json.dumps(ids), encoding="utf8")
        print("PASS prepared 3 persisted DEMO UI runs (shortlist review, report review, approved saved); credentials suppressed")
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Local report UI preparation failed; input/credential details suppressed") from None
