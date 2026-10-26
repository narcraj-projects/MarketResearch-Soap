from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import os
from uuid import UUID, uuid4

from fastapi import HTTPException
import pytest
from sqlalchemy import func, select, update

from app import models as m
from app.api_schemas import RunCreate
from app.harness.lease import JobQueue
from app.harness.policy import PolicyDenied
from app.queue_policy import QueueLimits, admission
from app.repository import owner_transaction
import tests.test_storage_integration as storage
from tests.test_workflow_storage_integration import prepared

engine, local = storage.engine, storage.local
pytestmark = [pytest.mark.integration, pytest.mark.skipif(not os.environ.get("LATHER_INTEGRATION_CONFIG"), reason="dedicated local DB required")]


def test_sec10_concurrent_admission_cap_and_idempotency(local, engine, monkeypatch):
    owner = UUID(local["users"][0]["id"])
    brief, initial = storage.seed(engine, owner)
    with owner_transaction(engine, owner) as repo:
        pending = repo.conn.execute(select(func.count()).select_from(m.runs).where(m.runs.c.owner_id == owner,
            m.runs.c.status.not_in(("complete", "cancelled", "partial", "failed")))).scalar_one()
    limits = QueueLimits(outstanding=pending + 2, active=1)
    monkeypatch.setattr("app.repository.admission", lambda repo: admission(repo, limits))
    body = RunCreate(brief_id=brief["id"], budget={"max_calls": 3, "max_tokens": 0, "max_cost_usd": "0"})
    def submit(_):
        key = str(uuid4())
        try:
            with owner_transaction(engine, owner) as repo:
                return repo.start(body, key), key
        except HTTPException as error:
            assert error.status_code == 429 and error.detail == "queue_capacity"
            return None
    accepted = []
    try:
        with ThreadPoolExecutor(8) as pool:
            values = list(pool.map(submit, range(8)))
        accepted = [row for row in values if row]
        assert len(accepted) == 2 and values.count(None) == 6
        with owner_transaction(engine, owner) as repo:
            assert repo.start(body, accepted[0][1])["id"] == accepted[0][0]["id"]
    finally:
        for run in [initial, *(row[0] for row in accepted)]:
            with owner_transaction(engine, owner) as repo:
                current = repo.get(m.runs, UUID(str(run["id"])))
                repo.control(current["id"], "cancel", current["version"], str(uuid4()))


def test_sec11_concurrent_claim_cap_expiry_fence_and_owner_isolation(local, engine):
    runs = [prepared(engine, local)[1] for _ in range(6)]
    owner, other = [UUID(row["id"]) for row in local["users"]]
    queue = JobQueue(engine, owner)
    try:
        with ThreadPoolExecutor(6) as pool:
            leases = list(pool.map(lambda run: queue.claim(uuid4(), run_id=run), runs))
        held = [lease for lease in leases if lease]
        assert len(held) == 4 and len({lease.run_id for lease in held}) == 4
        assert JobQueue(engine, other).claim(uuid4(), run_id=held[0].run_id) is None
        old = held[0]
        with owner_transaction(engine, owner) as repo:
            repo.conn.execute(update(m.jobs).where(m.jobs.c.run_id == old.run_id).values(lease_until=func.clock_timestamp() - timedelta(seconds=1)))
        replacement = queue.claim(uuid4(), run_id=old.run_id)
        assert replacement and replacement.generation == old.generation + 1
        with pytest.raises(PolicyDenied, match="lease_lost_or_cancelled"):
            old.check(engine)
    finally:
        for run in runs:
            with owner_transaction(engine, owner) as repo:
                current = repo.get(m.runs, run)
                repo.control(run, "cancel", current["version"], str(uuid4()))


def test_sec12_mocked_provider_concurrent_workers_complete_and_persist(local, engine):
    from tools.security_load import measure
    result = measure(engine, UUID(local["users"][0]["id"]), workers=2, count=2)
    assert result["completed_runs"] == 2 and result["completed_research_lanes"] == 6
    assert result["peak_active_workers"] == 2
    assert result["actual_provider_calls"] == result["actual_provider_tokens"] == 0
    assert result["recorded_tool_dispatches"] > 0 and all(result["persisted_event_counts"])
