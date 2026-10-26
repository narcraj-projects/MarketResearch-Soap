"""Only the discovery slice. No researcher, model, or subsequent stage execution."""
from collections.abc import Callable
from uuid import uuid5

from app.agents.scout import rank
from app.api_schemas import BriefCreate
from app.harness.contracts import Role, RunContext, SearchCall
from app.harness.ports import SearchToolGateway
from app.harness.policy import PolicyDenied
from app.harness.search import SearchSource
from app.harness.search_store import PostgresSearchLedger


def queries(brief: BriefCreate) -> tuple[str, str]:
    base = f"{brief.category} makers {brief.geography} {brief.customer} official brand"
    return base[:2000], f"{brief.category} artisan manufacturers {brief.geography} own website"[:2000]


def search(context: RunContext, brief: BriefCreate, gateway: SearchToolGateway) -> tuple[tuple[SearchSource, ...], str | None]:
    sources: list[SearchSource] = []
    stop_reason: str | None = None
    if "soap" not in brief.category.casefold():
        return (), "unsupported_category"
    planned_queries: tuple[str, ...] = queries(brief)
    if context.mode == "live":
        planned_queries = (planned_queries[0], f"{brief.category} brands {brief.geography} buy online official shop price ingredients direct to consumer"[:2000])
        extra = getattr(gateway, "supplementary_query", None)
        if extra:
            planned_queries = (*planned_queries, extra)
        continuation = getattr(gateway, "continuation_query", None)
        if continuation:
            planned_queries = (*planned_queries, continuation)
    for ordinal, query in enumerate(planned_queries):
        call = SearchCall(operation_id=uuid5(context.run_id, f"scout:{context.versions.graph}:{ordinal}"), agent=Role.SCOUT, tool="public.search", query=query, limit=10)
        try:
            execution = gateway.execute(context, call)
        except PolicyDenied as error:
            if str(error) not in {"budget", "deadline", "unknown_cost"}:
                raise
            return tuple(sources), str(error)
        if execution.payload:
            sources.extend(execution.payload.sources)
        if execution.stop_reason in {"budget", "deadline", "uncertain_attempt"}:
            stop_reason = execution.stop_reason
            break
        if execution.result.status != "ok":
            stop_reason = "search_" + execution.result.status
            if context.mode == "live" and ordinal + 1 < len(planned_queries):
                continue
            break
        ranker = getattr(gateway, "ranker", rank)
        if len(ranker(brief, context.run_id, tuple(sources)).candidates) == 3:
            break
    return tuple(sources), stop_reason


def discover(context: RunContext, brief: BriefCreate, gateway: SearchToolGateway, ledger: PostgresSearchLedger,
             after_search: Callable[[], None] | None = None) -> dict:
    _, stop = search(context, brief, gateway)
    if after_search:
        after_search()  # Test-only crash boundary after durable result commit, before publication.
    return ledger.finish(context, brief, stop_reason=stop)
