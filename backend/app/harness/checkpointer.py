"""LangGraph BaseCheckpointSaver backed by owner-RLS Postgres and a worker fence.

Stores whole snapshots (no delta channels). Synchronous API intentionally: the worker
is synchronous; the HTTP process never drives the graph. No runtime DDL or deletion.
"""
from collections.abc import Iterator, Sequence
from typing import Any
from threading import Condition
from time import monotonic
from uuid import uuid5

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata, CheckpointTuple, ChannelVersions, WRITES_IDX_MAP, writes_sort_key
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app import models as m
from app.repository import owner_transaction
from .lease import Lease
from .policy import PolicyDenied

GRAPH_VERSION = "workflow-1.2"
PARENT_WAIT_SECONDS = 5.0


class OwnerPostgresSaver(BaseCheckpointSaver[int]):
    def __init__(self, engine, lease: Lease):
        super().__init__(serde=JsonPlusSerializer(pickle_fallback=False,
            allowed_msgpack_modules=[("langgraph.types", "Interrupt"), ("langgraph.types", "Send")]))
        self.engine, self.lease = engine, lease
        self._committed = Condition()

    def _config(self, config: RunnableConfig) -> tuple[str, str | None]:
        values = config.get("configurable", {})
        if values.get("thread_id") != str(self.lease.run_id):
            raise PolicyDenied("checkpoint_thread_mismatch")
        namespace = values.get("checkpoint_ns", "")
        if namespace != "":
            raise PolicyDenied("checkpoint_namespace_unsupported")
        return namespace, values.get("checkpoint_id")

    def _scope(self, table, namespace):
        return (table.c.run_id == self.lease.run_id, table.c.owner_id == self.lease.owner_id, table.c.namespace == namespace)

    def _ref(self, namespace, identifier) -> RunnableConfig:
        return {"configurable": {"thread_id": str(self.lease.run_id), "checkpoint_ns": namespace, "checkpoint_id": identifier}}

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        namespace, identifier = self._config(config)
        with owner_transaction(self.engine, self.lease.owner_id) as repo:
            self.lease.guard(repo)
            query = select(m.graph_checkpoints).where(*self._scope(m.graph_checkpoints, namespace))
            if identifier:
                query = query.where(m.graph_checkpoints.c.checkpoint_id == identifier)
            row = repo.conn.execute(query.order_by(m.graph_checkpoints.c.checkpoint_id.desc()).limit(1)).mappings().first()
            if row is None:
                return None
            if row["graph_version"] != GRAPH_VERSION:
                raise PolicyDenied("graph_version_mismatch")
            writes = repo.conn.execute(select(m.graph_writes).where(*self._scope(m.graph_writes, namespace),
                m.graph_writes.c.checkpoint_id == row["checkpoint_id"])).mappings().all()
            ordered = sorted(writes, key=lambda w: writes_sort_key(w["task_path"], w["task_id"], w["write_index"]))
            return CheckpointTuple(config=self._ref(namespace, row["checkpoint_id"]),
                checkpoint=self.serde.loads_typed((row["encoding"], bytes(row["payload"]))), metadata=row["metadata"],
                parent_config=self._ref(namespace, row["parent_id"]) if row["parent_id"] else None,
                pending_writes=[(w["task_id"], w["channel"], self.serde.loads_typed((w["encoding"], bytes(w["payload"])))) for w in ordered])

    def list(self, config: RunnableConfig | None, *, filter: dict[str, Any] | None = None,
             before: RunnableConfig | None = None, limit: int | None = None) -> Iterator[CheckpointTuple]:
        if config is None:
            raise PolicyDenied("checkpoint_thread_required")
        namespace, identifier = self._config(config)
        with owner_transaction(self.engine, self.lease.owner_id) as repo:
            self.lease.guard(repo)
            query = select(m.graph_checkpoints.c.checkpoint_id, m.graph_checkpoints.c.metadata).where(*self._scope(m.graph_checkpoints, namespace))
            if identifier:
                query = query.where(m.graph_checkpoints.c.checkpoint_id == identifier)
            if before:
                _, upper = self._config(before)
                query = query.where(m.graph_checkpoints.c.checkpoint_id < upper)
            rows = repo.conn.execute(query.order_by(m.graph_checkpoints.c.checkpoint_id.desc())).mappings().all()
        count = 0
        for row in rows:
            if filter and not all(row["metadata"].get(k) == v for k, v in filter.items()):
                continue
            if limit is not None and count >= limit:
                break
            item = self.get_tuple(self._ref(namespace, row["checkpoint_id"]))
            if item:
                yield item
                count += 1

    def put(self, config: RunnableConfig, checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: ChannelVersions) -> RunnableConfig:
        namespace, parent = self._config(config)
        encoding, payload = self.serde.dumps_typed(checkpoint)
        with owner_transaction(self.engine, self.lease.owner_id) as repo:
            self.lease.guard(repo)
            statement = insert(m.graph_checkpoints).values(id=uuid5(self.lease.run_id, f"checkpoint:{namespace}:{checkpoint['id']}"),
                owner_id=self.lease.owner_id, run_id=self.lease.run_id, namespace=namespace, checkpoint_id=checkpoint["id"], parent_id=parent,
                encoding=encoding, payload=payload, metadata={k: v for k, v in metadata.items() if k in {"source", "step", "parents"}}, graph_version=GRAPH_VERSION)
            repo.conn.execute(statement.on_conflict_do_nothing(index_elements=["run_id", "namespace", "checkpoint_id"]))
        with self._committed:
            self._committed.notify_all()  # Commit precedes notification; Postgres remains authoritative.
        return self._ref(namespace, checkpoint["id"])

    def _parent_exists(self, namespace: str, identifier: str) -> bool:
        with owner_transaction(self.engine, self.lease.owner_id) as repo:
            self.lease.guard(repo)
            return repo.conn.execute(select(m.graph_checkpoints.c.id).where(*self._scope(m.graph_checkpoints, namespace),
                m.graph_checkpoints.c.checkpoint_id == identifier)).first() is not None

    def _await_parent(self, namespace: str, identifier: str) -> None:
        # LangGraph may submit pending writes before its background checkpoint put
        # commits, even with synchronous step durability. Never hold run/job locks
        # while waiting, or the checkpoint writer and heartbeat cannot proceed.
        until = monotonic() + PARENT_WAIT_SECONDS
        while not self._parent_exists(namespace, identifier):
            remaining = until - monotonic()
            if remaining <= 0:
                raise PolicyDenied("checkpoint_parent_not_durable")
            with self._committed:
                self._committed.wait(min(0.05, remaining))

    def put_writes(self, config: RunnableConfig, writes: Sequence[tuple[str, Any]], task_id: str, task_path: str = "") -> None:
        namespace, identifier = self._config(config)
        if identifier is None:
            raise PolicyDenied("checkpoint_id_required")
        self._await_parent(namespace, identifier)
        with owner_transaction(self.engine, self.lease.owner_id) as repo:
            self.lease.guard(repo)
            for ordinal, (channel, value) in enumerate(writes):
                index = WRITES_IDX_MAP.get(channel, ordinal)
                if isinstance(value, BaseException):
                    value = "node_failed"  # Never persist arbitrary exception messages/inputs.
                encoding, payload = self.serde.dumps_typed(value)
                statement = insert(m.graph_writes).values(id=uuid5(self.lease.run_id, f"write:{namespace}:{identifier}:{task_id}:{index}"),
                    owner_id=self.lease.owner_id, run_id=self.lease.run_id, namespace=namespace, checkpoint_id=identifier,
                    task_id=task_id, write_index=index, channel=channel, encoding=encoding, payload=payload, task_path=task_path)
                keys = ["run_id", "namespace", "checkpoint_id", "task_id", "write_index"]
                # LangGraph special writes (errors/interrupts/resume) replace the earlier value;
                # successful task writes are append-once, so sibling successes survive a crash.
                repo.conn.execute(statement.on_conflict_do_update(index_elements=keys, set_={"channel": channel, "encoding": encoding,
                    "payload": payload, "task_path": task_path}) if index < 0 else statement.on_conflict_do_nothing(index_elements=keys))

    def delete_thread(self, thread_id: str) -> None:
        raise PolicyDenied("checkpoint_retention_requires_admin_migration")
