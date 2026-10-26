"""Required implementation boundaries. Protocols have no network side effects."""
from typing import Protocol
from uuid import UUID

from .contracts import Checkpoint, Event, ReplayRecord, RunContext, ToolCall, ToolResult
from .contracts import SearchCall
from .search import SearchExecution


class ToolGateway(Protocol):
    def execute(self, context: RunContext, call: ToolCall) -> ToolResult: ...


class SearchToolGateway(Protocol):
    """Implemented search slice; envelope adds validated sources and a stop reason."""
    def execute(self, context: RunContext, call: SearchCall) -> SearchExecution: ...


class DurableState(Protocol):
    def load(self, run_id: UUID, owner_id: UUID) -> RunContext: ...
    def commit(self, context: RunContext, checkpoint: Checkpoint, results: tuple[ToolResult, ...], events: tuple[Event, ...], expected_version: int, fencing_generation: int) -> None:
        """Atomically CAS scope/version/fence and journal results; reject stale writers."""
        ...


class Replay(Protocol):
    def consume(self, context: RunContext, call: ToolCall, ordinal: int) -> ReplayRecord:
        """Exact version/ordered request match or fail; never fall back to live calls."""
        ...


class FaultInjector(Protocol):
    def before_operation(self, operation_id: UUID, attempt: int) -> None:
        """Configured by trusted server state only; deterministic operation/attempt target."""
        ...
