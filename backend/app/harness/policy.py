"""Pure offline preflight checks. No authorization storage or atomic reservation."""
from datetime import datetime
from decimal import Decimal

from .contracts import ModelCall, Phase, Role, RunContext, ToolCall

ALLOWLIST = {
    Role.ORCHESTRATOR: frozenset(),
    Role.SCOUT: frozenset({"public.search", "model.generate"}),
    Role.RESEARCHER: frozenset({"public.search", "public.retrieve", "public.news", "model.generate"}),
    Role.ANALYST: frozenset({"normalize", "model.generate"}),
    Role.REVIEWER: frozenset({"normalize", "model.generate"}),
}
PHASES = {Role.SCOUT: Phase.DISCOVER, Role.RESEARCHER: Phase.RESEARCH, Role.ANALYST: Phase.ANALYZE, Role.REVIEWER: Phase.REVIEW}


class PolicyDenied(ValueError):
    """Stable non-sensitive error code only."""


def require_approval(context: RunContext, gate: str) -> None:
    if gate not in {"shortlist", "report"}:
        raise PolicyDenied("unknown_gate")
    expected_hash = getattr(context, gate + "_hash")
    expected_version = getattr(context, gate + "_version")
    grants = [a for a in context.approvals if a.gate == gate]
    # Append-only history may have superseded decisions; any ambiguity fails closed.
    if len(grants) != 1 or not expected_hash:
        raise PolicyDenied("approval_required")
    grant = grants[0]
    if grant.decision != "approve" or grant.artifact_hash != expected_hash or grant.artifact_version != expected_version:
        raise PolicyDenied("stale_or_rejected_approval")


def authorize_access(context: RunContext, call: ToolCall, now: datetime) -> None:
    if now.utcoffset() is None or now >= context.deadline:
        raise PolicyDenied("deadline")
    if call.tool not in ALLOWLIST[call.agent] or context.phase != PHASES.get(call.agent):
        raise PolicyDenied("tool_or_phase_denied")
    if context.phase in {Phase.RESEARCH, Phase.ANALYZE, Phase.REVIEW}:
        require_approval(context, "shortlist")


def authorize(context: RunContext, call: ToolCall, now: datetime, estimated_cost: Decimal = Decimal("0")) -> None:
    authorize_access(context, call, now)
    if not estimated_cost.is_finite() or estimated_cost < 0:
        raise PolicyDenied("invalid_cost")
    b = context.budget
    tokens = call.max_output_tokens if isinstance(call, ModelCall) else 0
    if b.used_calls + b.reserved_calls + 1 > b.max_calls or b.used_tokens + b.reserved_tokens + tokens > b.max_tokens or b.used_cost + b.reserved_cost + estimated_cost > b.max_cost:
        raise PolicyDenied("budget")
    # Does not dispatch, reserve, resolve URLs or grant live egress.
