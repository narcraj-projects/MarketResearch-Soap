"""DEMO validation examples, not full D01–D17 workflow evaluations."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import TypeAdapter, ValidationError

from app.harness.agent_schemas import AgentClaim, AnalystOutput, Candidate, FieldObservation, ScoutOutput, Source
from app.harness.contracts import Approval, Budget, Checkpoint, Claim, Event, EvidenceLink, FaultConfig, ReplayRecord, RunContext, ToolCall, ToolResult, Usage, Versions
from app.harness.evaluation import claim_metrics
from app.harness.policy import PolicyDenied, authorize, require_approval

NOW = datetime(2026, 10, 25, tzinfo=timezone.utc)
HASH = "a" * 64


def uid(number=1):
    return UUID(int=number)


def versions():
    return Versions(graph="DEMO-graph-1", model="DEMO-model-1", provider="offline", prompt="DEMO-prompt-1", tools="DEMO-tools-1", dataset="lather-lens-demo-v1")


def budget(**changes):
    return Budget(**({"max_calls": 3, "max_tokens": 100, "max_cost": Decimal("1")} | changes))


def approval(**changes):
    data = dict(request_id=uid(5), decision_id=uid(6), run_id=uid(), owner_id=uid(2), artifact_hash=HASH, artifact_version=1, gate="shortlist", decision="approve", decided_at=NOW)
    return Approval(**(data | changes))


def context(**changes):
    data = dict(run_id=uid(), user_id=uid(2), trace_id=uid(3), brief_version=1, run_version=1, versions=versions(), phase="discover", deadline=NOW + timedelta(minutes=1), budget=budget())
    return RunContext(**(data | changes))


def call(**changes):
    return TypeAdapter(ToolCall).validate_python(dict(operation_id=uid(4), agent="scout", tool="public.search", query="DEMO soap category") | changes)


def result(**changes):
    return ToolResult(**(dict(operation_id=uid(4), attempt=1, status="ok", payload_ref=uid(7), usage=Usage(calls=1, tokens=0, cost=Decimal("0"))) | changes))


def link(**changes):
    return EvidenceLink(**(dict(source_id=uid(8), excerpt_hash=HASH, quote="DEMO brand discloses olive oil.") | changes))


def test_V01_context_roundtrip_and_unknown_version_rejection():
    original = context()
    assert RunContext.model_validate_json(original.model_dump_json()) == original
    with pytest.raises(ValidationError):
        context(schema_version="2.0")


@pytest.mark.parametrize("changes", [{"api_key": "DEMO-not-a-secret"}, {"mode": "live"}, {"deadline": NOW.replace(tzinfo=None)}, {"brief_version": True}, {"shortlist_hash": HASH}])
def test_V02_context_rejects_unknown_fields_live_and_invalid_values(changes):
    with pytest.raises(ValidationError):
        context(**changes)


@pytest.mark.parametrize("changes", [{"used_calls": -1}, {"used_calls": 3, "reserved_calls": 1}, {"used_tokens": 101}, {"reserved_cost": "1.01"}, {"max_cost": "NaN"}])
def test_V03_budget_rejects_negative_nonfinite_and_overcommit(changes):
    with pytest.raises(ValidationError):
        budget(**changes)


@pytest.mark.parametrize("tool", ["publish", "contact", "purchase", "account.create"])
def test_V04_external_business_tools_have_no_schema(tool):
    with pytest.raises(ValidationError):
        call(tool=tool)


@pytest.mark.parametrize("agent", ["researcher", "analyst", "reviewer", "orchestrator"])
def test_V05_wrong_phase_or_role_cannot_dispatch(agent):
    with pytest.raises(PolicyDenied):
        authorize(context(), call(agent=agent), NOW)


def test_V06_scout_offline_preflight_and_deadline_boundary():
    authorize(context(), call(), NOW)
    with pytest.raises(PolicyDenied, match="deadline"):
        authorize(context(deadline=NOW), call(), NOW)


def test_V07_research_requires_current_approval():
    research = call(agent="researcher")
    with pytest.raises(PolicyDenied, match="approval"):
        authorize(context(phase="research"), research, NOW)
    approved = context(phase="research", shortlist_hash=HASH, shortlist_version=1, approvals=(approval(),))
    authorize(approved, research, NOW)


@pytest.mark.parametrize("changes", [{"artifact_hash": "b" * 64}, {"artifact_version": 2}, {"decision": "reject"}, {"gate": "report"}])
def test_V08_stale_rejected_or_wrong_gate_cannot_approve(changes):
    ctx = context(shortlist_hash=HASH, shortlist_version=1, approvals=(approval(**changes),))
    with pytest.raises(PolicyDenied):
        require_approval(ctx, "shortlist")


@pytest.mark.parametrize("changes", [{"owner_id": uid(9)}, {"run_id": uid(9)}])
def test_V09_approval_scope_is_validated(changes):
    with pytest.raises(ValidationError):
        context(approvals=(approval(**changes),))


def test_V10_budget_and_token_preflight():
    with pytest.raises(PolicyDenied, match="budget"):
        authorize(context(budget=budget(used_calls=3)), call(), NOW)
    with pytest.raises(PolicyDenied, match="budget"):
        authorize(context(), call(), NOW, Decimal("1.01"))
    model = TypeAdapter(ToolCall).validate_python(dict(operation_id=uid(4), agent="scout", tool="model.generate", prompt_id="DEMO-prompt", input_hash=HASH, max_output_tokens=101))
    with pytest.raises(PolicyDenied, match="budget"):
        authorize(context(), model, NOW)


@pytest.mark.parametrize("attempt", [0, 4, True])
def test_V11_retry_attempt_bounds(attempt):
    with pytest.raises(ValidationError):
        call(attempt=attempt)


@pytest.mark.parametrize("changes", [{"status": "timeout"}, {"status": "ok", "payload_ref": None}, {"status": "denied", "payload_ref": None, "error_code": "timeout"}])
def test_V12_result_cannot_mix_success_and_failure(changes):
    with pytest.raises(ValidationError):
        result(**changes)


def test_V13_replay_requires_demo_versions_and_exact_operation():
    record = ReplayRecord(label="DEMO", dataset_version=versions().dataset, ordinal=1, versions=versions(), call=call(), result=result())
    assert ReplayRecord.model_validate_json(record.model_dump_json()) == record
    for changes in ({"label": "REAL"}, {"dataset_version": "other"}, {"result": result(operation_id=uid(99))}, {"result": result(attempt=2)}):
        with pytest.raises(ValidationError):
            ReplayRecord.model_validate(record.model_dump() | changes)


def test_V14_checkpoint_roundtrip_and_duplicate_operation_rejection():
    cp = Checkpoint(checkpoint_id=uid(10), run_id=uid(), owner_id=uid(2), graph_version="DEMO-graph-1", run_version=1, fencing_generation=1, event_sequence=2, completed_operations=(uid(4),), state_hash=HASH)
    assert Checkpoint.model_validate_json(cp.model_dump_json()) == cp
    with pytest.raises(ValidationError):
        Checkpoint.model_validate(cp.model_dump() | {"completed_operations": (uid(4), uid(4))})


@pytest.mark.parametrize("changes", [{"environment": "production", "enabled": True, "authorized": True, "fault": "timeout"}, {"environment": "test", "enabled": True, "fault": "timeout"}, {"environment": "isolated_demo", "fault": "restart"}])
def test_V15_faults_fail_closed(changes):
    with pytest.raises(ValidationError):
        FaultConfig(**changes)


def test_V16_authorized_test_fault_and_disabled_production():
    assert FaultConfig(environment="test", enabled=True, authorized=True, fault="restart").label == "DEMO"
    assert FaultConfig(environment="production").enabled is False


def test_V17_events_reject_raw_payload_and_unknown_versions():
    event = Event(event_id=uid(11), run_id=uid(), trace_id=uid(3), sequence=1, occurred_at=NOW, kind="tool.completed", agent="scout", operation_id=uid(4), code="ok", versions=versions())
    for changes in ({"raw_prompt": "DEMO private text"}, {"schema_version": "2.0"}, {"sequence": 0}, {"operation_id": None}):
        with pytest.raises(ValidationError):
            Event.model_validate(event.model_dump() | changes)


def test_V18_citation_presence_is_not_support():
    claim = Claim(claim_id=uid(12), text="DEMO soap contains olive oil.", kind="fact", material=True, evidence=(link(),))
    metrics = claim_metrics((claim,))
    assert metrics["citation_presence"] == 1
    assert metrics["support_coverage"] == 0


def test_V19_unreviewed_and_contradicted_links_do_not_pass_support():
    with pytest.raises(ValidationError):
        link(support="supported")
    yes = link(support="supported", adjudicator="golden_human", rationale="DEMO exact ingredient statement")
    no = link(support="contradicted", adjudicator="human", rationale="DEMO conflicting observation")
    base = dict(text="DEMO attributed observation", kind="fact", material=True)
    claims = (Claim(claim_id=uid(12), evidence=(yes,), **base), Claim(claim_id=uid(13), evidence=(yes, no), **base), Claim(claim_id=uid(14), **base))
    assert claim_metrics(claims)["support_coverage"] == pytest.approx(1 / 3)


def test_V20_empty_claims_not_a_perfect_score_and_duplicates_rejected():
    assert claim_metrics(())["support_coverage"] is None
    claim = Claim(claim_id=uid(12), text="DEMO unsupported fact", kind="fact", material=True)
    with pytest.raises(ValueError, match="duplicate_claim_id"):
        claim_metrics((claim, claim))


def test_V21_marketing_attribution_counts_but_does_not_prove_efficacy():
    claim = Claim(claim_id=uid(12), text="DEMO brand makes a skincare claim", kind="competitor_marketing_claim", material=True, evidence=(link(),))
    assert claim_metrics((claim,))["material_facts"] == 1
    assert claim_metrics((claim,))["supported"] == 0


def test_V22_shortlist_and_opportunity_shortfall_must_be_explicit():
    with pytest.raises(ValidationError):
        ScoutOutput(candidates=())
    assert ScoutOutput(candidates=(), insufficiency_reason="DEMO no credible candidates").candidates == ()
    with pytest.raises(ValidationError):
        AnalystOutput(claims=(), opportunities=())
    candidate = Candidate(candidate_id=uid(20), name="DEMO candidate", evidence=(link().model_dump(),), rationale="DEMO evidence")
    with pytest.raises(ValidationError):
        ScoutOutput(candidates=(candidate, candidate, candidate))


def test_V23_missing_fields_are_not_observed_values():
    assert FieldObservation(field="weight", unavailable_reason="DEMO not disclosed").value is None
    for data in ({"field": "weight"}, {"field": "weight", "value": "100 g"}, {"field": "weight", "value": "100 g", "unavailable_reason": "DEMO missing"}):
        with pytest.raises(ValidationError):
            FieldObservation(**data)


def test_V24_successful_source_requires_hash_and_aware_date():
    data = dict(source_id=uid(8), canonical_url="https://example.invalid/demo", title="DEMO source", publisher="DEMO publisher", retrieved_at=NOW, content_hash=HASH, access_status="ok")
    assert Source(**data).content_hash == HASH
    with pytest.raises(ValidationError):
        Source(**(data | {"content_hash": None}))
    with pytest.raises(ValidationError):
        Source(**(data | {"retrieved_at": NOW.replace(tzinfo=None)}))


def test_V25_agents_cannot_self_adjudicate_support():
    claimed_support = link(support="supported", adjudicator="human", rationale="DEMO forged adjudication")
    with pytest.raises(ValidationError):
        AgentClaim(claim_id=uid(12), text="DEMO claim", kind="fact", material=True, evidence=(claimed_support.model_dump(),))
