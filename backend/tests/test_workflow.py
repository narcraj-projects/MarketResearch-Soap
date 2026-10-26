"""Orchestration contract tests; no external or database calls."""
from hashlib import sha256
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, interrupt
from pydantic import ValidationError
import pytest

from app.event_stream import event_frame
from app.repository import digest
from app.workflow import WorkflowState, build_graph, inventory_issues, review_route


class GraphFixture:
    """DEMO node port: drives real graph branches without fabricating business results."""
    def __init__(self, failures=0):
        self.calls = []
        self.failures = failures

    def node(self, name, updates):
        self.calls.append(name)
        return updates

    def validate(self, state):
        return self.node("validate", {"phase": "discover"})

    def discover(self, state):
        return self.node("discover", {"phase": "shortlist_review"})

    def gate(self, state, gate):
        decision = interrupt({"gate": gate, "label": "DEMO"})
        return self.node(gate, {"shortlist": decision})

    def research(self, state):
        return self.node("research", {"phase": "normalize"})

    def normalize(self, state):
        return self.node("normalize", {"phase": "analyze"})

    def analyze(self, state):
        return self.node("analyze", {"phase": "review"})

    def review(self, state):
        return self.node("review", {"review_ok": state.revision >= self.failures})

    def revise(self, state):
        return self.node("revise", {"revision": state.revision + 1})

    def final_approval(self, state):
        decision = interrupt({"gate": "report", "label": "DEMO"})
        return self.node("final_approval", {"final": decision})

    def save(self, state):
        return self.node("save", {"phase": "save"})

    def stopped(self, state):
        return self.node("stopped", {"phase": "stopped"})


@pytest.mark.parametrize("failures,limit,expected", [(0, 1, "save"), (1, 1, "save"), (2, 1, "stopped"), (1, 0, "stopped")])
def test_w01_conditional_review_and_bounded_revision(failures, limit, expected, monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    fixture = GraphFixture(failures)
    graph = build_graph(fixture, InMemorySaver())
    config = {"configurable": {"thread_id": str(uuid4())}, "recursion_limit": 30}
    run = graph.invoke(WorkflowState(run_id=str(uuid4()), revision_limit=limit).model_dump(), config)
    assert run["__interrupt__"][0].value["gate"] == "shortlist"
    assert "research" not in fixture.calls
    run = graph.invoke(Command(resume="approve"), config)
    if expected == "save":
        assert run["__interrupt__"][0].value["gate"] == "report"
        assert "save" not in fixture.calls
        run = graph.invoke(Command(resume="approve"), config)
    assert run["phase"] == expected
    assert fixture.calls.count("revise") <= limit
    assert fixture.calls.count("research") == 1


@pytest.mark.parametrize("gate,decision", [("shortlist", "reject"), ("shortlist", "request_changes"), ("report", "reject"), ("report", "request_changes")])
def test_w02_rejection_never_saves(gate, decision):
    fixture = GraphFixture()
    graph = build_graph(fixture, InMemorySaver())
    config = {"configurable": {"thread_id": str(uuid4())}}
    graph.invoke({"run_id": str(uuid4())}, config)
    if gate == "report":
        graph.invoke(Command(resume="approve"), config)
    result = graph.invoke(Command(resume=decision), config)
    assert result["phase"] == "stopped" and "save" not in fixture.calls
    if gate == "shortlist":
        assert "research" not in fixture.calls


@pytest.mark.parametrize("patch", [{"schema_version": "future"}, {"revision": 3}, {"revision_limit": -1}, {"run_id": "wrong"}, {"phase": "publish"}, {"owner_id": str(uuid4())}])
def test_w03_state_denies_unversioned_or_unsafe_control(patch):
    with pytest.raises(ValidationError):
        WorkflowState.model_validate({"run_id": str(uuid4())} | patch)


def test_w04_citation_presence_and_exact_quote_do_not_certify_support():
    quote = "DEMO brand says it cures everything"
    data = {"sources": [{"id": "s", "access_status": "ok", "excerpt": quote}],
        "claims": [{"id": "c", "material": True, "review_status": "unreviewed"}],
        "claim_sources": [{"claim_id": "c", "source_id": "s", "quote": quote, "excerpt_hash": sha256(quote.encode()).hexdigest()}]}
    assert inventory_issues(data, digest(data)) == []  # mechanical check only
    data["claims"][0]["review_status"] = "supported"
    assert "semantic_support_not_adjudicated" in inventory_issues(data, digest(data))
    data["claim_sources"][0]["quote"] = "fabricated quote"
    assert "citation_invalid" in inventory_issues(data, digest(data))
    data["claim_sources"] = []
    assert "citation_missing" in inventory_issues(data, digest(data))


def test_w05_review_limit_stops_and_sse_keeps_json_in_one_data_line():
    assert review_route(WorkflowState(run_id=str(uuid4()), revision=1, revision_limit=1, review_ok=False)) == "stopped"
    from datetime import datetime, timezone
    frame = event_frame({"id": uuid4(), "owner_id": uuid4(), "run_id": uuid4(), "created_at": datetime.now(timezone.utc),
        "sequence": 17, "kind": "workflow.node", "data": {"schema_version": "1.0", "label": "DEMO\nevent: forged"}})
    assert frame.startswith("id: 17\nevent: run-event\ndata: ")
    assert frame.count("\ndata:") == 1 and frame.endswith("\n\n")


def test_w17_checkpoint_reader_denies_pickle_and_other_threads():
    from app.harness.checkpointer import OwnerPostgresSaver
    from app.harness.lease import Lease
    from app.harness.policy import PolicyDenied
    saver = OwnerPostgresSaver(None, Lease(uuid4(), uuid4(), uuid4(), 1))
    with pytest.raises(NotImplementedError):
        saver.serde.loads_typed(("pickle", b"DEMO-not-executable"))
    with pytest.raises(PolicyDenied, match="checkpoint_thread_mismatch"):
        saver.get_tuple({"configurable": {"thread_id": str(uuid4())}})
    with pytest.raises(PolicyDenied, match="checkpoint_namespace"):
        saver.get_tuple({"configurable": {"thread_id": str(saver.lease.run_id), "checkpoint_ns": "other"}})


@pytest.mark.parametrize("failure", [False, True])
def test_w18_sse_polls_committed_cursor_and_closes_on_disconnect_or_storage_failure(monkeypatch, integration_loop, failure):
    from contextlib import contextmanager
    from datetime import datetime, timezone
    from app import event_stream
    row = {"id": uuid4(), "owner_id": uuid4(), "run_id": uuid4(), "created_at": datetime.now(timezone.utc),
        "sequence": 3, "kind": "workflow.node", "data": {"schema_version": "1.0", "label": "DEMO"}}
    polls = []
    class Repo:
        def list(self, table, run_id, limit, after):
            polls.append(after)
            if failure:
                raise RuntimeError("DEMO-private-input-must-not-escape")
            return [row | {"sequence": 4}]
    @contextmanager
    def transaction(engine, owner):
        assert owner == row["owner_id"]
        yield Repo()
    class Request:
        calls = 0
        async def is_disconnected(self):
            self.calls += 1
            return self.calls > 1
    async def sleep(_):
        return None
    monkeypatch.setattr(event_stream, "owner_transaction", transaction)
    monkeypatch.setattr(event_stream.asyncio, "sleep", sleep)
    async def exercise():
        return [frame async for frame in event_stream.persisted_stream(None, row["owner_id"], row["run_id"], 2, [row], follow_seconds=25, request=Request())]
    frames = integration_loop.run_until_complete(exercise())
    assert polls == [3] and frames[0].startswith("id: 3\n")
    assert "DEMO-private-input" not in "".join(frames)
    assert frames[-1].startswith("event: stream-error" if failure else "id: 4\n")
