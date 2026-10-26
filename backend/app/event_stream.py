"""SSE is a cursor projection of committed events, never a second event producer."""
import asyncio
import json
from time import monotonic

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.exc import SQLAlchemyError

from app import models as m
from app.api_schemas import EventRecord
from app.repository import owner_transaction


def event_frame(row: dict) -> str:
    event = EventRecord.model_validate(row).model_dump(mode="json")
    return f"id: {event['sequence']}\nevent: run-event\ndata: {json.dumps(event, separators=(',', ':'))}\n\n"


async def persisted_stream(engine, owner, run_id, cursor, initial, *, follow_seconds: int, request):
    deadline = monotonic() + follow_seconds
    rows = initial
    while True:
        for row in rows:
            if row["sequence"] > cursor:
                yield event_frame(row)
                cursor = row["sequence"]
        if monotonic() >= deadline or await request.is_disconnected():
            return
        yield ": heartbeat\n\n"
        await asyncio.sleep(min(1, max(0, deadline - monotonic())))
        def poll():
            with owner_transaction(engine, owner) as repo:
                return repo.list(m.events, run_id, limit=100, after=cursor)
        try:
            rows = await run_in_threadpool(poll)
        except (SQLAlchemyError, RuntimeError):
            yield 'event: stream-error\ndata: {"schema_version":"1.0","code":"storage_unavailable"}\n\n'
            return
