"""Atomic separate DEMO run creation; no mutation of another research run or execution here."""
from sqlalchemy import update

from app import models as m
from app.api_schemas import BriefCreate, RunCreate
from app.config import Settings
from app.harness.chaos import ChaosCreate, plan, read_fixture, require_test_mode, require_isolated_engine


def create_demo(repo, body: ChaosCreate, key: str, settings: Settings) -> dict:
    require_test_mode(settings)
    require_isolated_engine(repo.conn.engine)
    def command():
        value = plan(body.scenario)
        fixture = read_fixture("search-clean.json")
        brief = repo.create(m.briefs, BriefCreate.model_validate(fixture["brief"]).model_dump(mode="json") | {"version": 1})
        run = repo.start(RunCreate.model_validate({"brief_id": brief["id"], "budget": {"max_calls": 40, "max_tokens": 32768, "max_cost_usd": "0"}}), "DEMO-start:" + key)
        from uuid import UUID
        run_id = UUID(str(run["id"]))
        repo.control(run_id, "resume", 1, "DEMO-resume:" + key)
        job = repo.conn.execute(m.jobs.select().where(m.jobs.c.run_id == run_id, m.jobs.c.owner_id == repo.owner).with_for_update()).mappings().one()
        repo.conn.execute(update(m.jobs).where(m.jobs.c.id == job["id"]).values(workflow=dict(job["workflow"]) | {"chaos": value.model_dump(mode="json")}))
        repo.event(run_id, "chaos.armed", value.model_dump(mode="json"))
        return {"label": "DEMO", "run_id": str(run_id), "scenario": body.scenario, "worker_required": True}
    return repo.idempotent("chaos:create", key, body.model_dump(mode="json"), command)
