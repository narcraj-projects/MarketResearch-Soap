# Lather Lens harness specification

## B13 evaluation boundary

`app/evaluations/` adds golden-plan-1.0, frozen dataset/case/result/measurement schemas, independent graders, explicit baseline comparison and sanitized-trace-1.0. Worker golden plans require server test/evaluation flags plus the dedicated DB; D13 termination remains a dedicated local test CLI operation. Model scripts use the same fenced harness reservation/schema-validation path; no provider is selected. Failures preserve source/task state, including explicit terminal news-search limitations. Human review is a separate authenticated, server-granted, exact-report/statement/source-bound receipt protocol. Fixture labels and citation presence cannot self-certify semantic support or owner usefulness. Remote LangSmith export is separately approved/capped; main app automatic tracing is still disabled. EVALUATION_SPEC.md/ADR 0014 define current interfaces; EVALUATION_REPORT.md gives actual evidence. No subsequent stage automatically.

## B12 current replay/chaos boundary

CHAOS_SPEC.md/ADR 0013 document implemented replay-1.0 exact request/response tapes and chaos-1.0 immutable plans. API, worker and model gateway require server test environment, explicit flag, replay-only mode and the dedicated loopback DB address. A new DEMO run alone receives an allowlisted pinned scenario; clients cannot inject arbitrary outputs or mutate existing runs. Cached attempts advance replay cursors without double dispatch/usage. Actual attempt outcomes, Pydantic parsing, independent mechanical review and fenced lane reuse produce the recovery events. Only a dedicated CLI can exit its own worker. Production and uncertain pending model attempts fail closed. Model response fixtures are synthetic frozen rule-output projections, not real model captures or quality evaluations. Paid-model token reservation/selection remains future approved work. Older design/prototype sections below are historical.

## B11 history boundary

History comparisons are read-only processing of immutable approved ReportSnapshots, with history-diff-1.0 / history-identity-1.0, exact owner/run/version/hash inputs and a deterministic as-of freshness policy. They cannot invoke the tool gateway, model, worker or external action. Optional explicit listing availability stays attributed and cannot originate in a fault/absence inference. Existing approval/save/lease policies remain unchanged. No graph/checkpoint pin or database migration change. See HISTORY_SPEC.md/ADR 0012 and HISTORY_STAGE_RESULTS.md; no next stage automatically.

## B10 report boundary

Graph version workflow-1.2 freezes report-presentation-1.0 with immutable analysis-report-1.0. Independent review receipt binds its full hash and draft/input hashes; final human decision and leased worker save remain mandatory. Reporting/export are pure local projections with no tool gateway or network capability. APIs enforce owner/RLS and export approved-save; BFF accepts only explicit resource/action paths. Incompatible older checkpoints are refused, not silently migrated. See REPORT_SPEC.md/ADR 0011. No live provider, telemetry, external action or following stage enabled.

## Current B09 evidence and review boundary

Versioned provider-neutral `EvidencePack`/`AnalysisDraft`/`ReviewResult` now separate observations, source claims, interpretations and hypotheses. Raw-source reconstruction, same-purchase-item proof and independent arithmetic precede approval; genuine-support adjudication remains unavailable. Analysis snapshots and immutable validation receipts bind input/draft/report hashes, frozen as_of/freshness policy and reviewer version. Only reviewer-named targets can be corrected, under existing lease/budget/deadline/approval boundaries; malformed/blocking/exhausted output stops unresolved. Workflow is workflow-1.1; migration 0006 gates database normalized prices on verified eligibility. ANALYSIS_SPEC.md and ADR 0010 define exact semantics; ANALYSIS_STAGE_RESULTS.md records executed checks. Older B08 inventory-only notes below are historical.

# Current graph and execution boundary

The B08 implementation now binds managed runs to `Lease(run_id, owner_id, worker_id, generation)`, actual owner-RLS Postgres LangGraph checkpoints and pending writes. Gateways check the fence before dispatch; search/research/checkpointer transactions check it under run/job locks before committing. Unfenced legacy stores refuse managed runs. Worker resume uses only a matching persisted approval decision ID. HTTP cancel/resume are owner/version-bound, transactional and idempotent. See WORKFLOW_SPEC.md and ADR 0009 for supported saver API/versioning, crash uncertainty, stream envelope and limitations; WORKFLOW_STAGE_RESULTS.md contains actual evidence. Earlier pure preflight-only statements are historical stage notes.

## Implemented public research slice

ResearchGateway/ResearchCall and ResearchState now implement the requested recorded Researcher/evidence stage. Public URL/DNS/peer/robots/access rules, shared attempt budgets, independent lanes and immutable evidence snapshots are documented in RESEARCH_SPEC.md and ADR 0008. RunContext/legacy tool contracts stay schema 1.0; new research wire/data contracts use research-1.0, tools public-research-1.0 and dataset research-demo-v1. No external transport is enabled. The full LangGraph worker/leases/fencing and later analysis/report stages remain unimplemented.

## Implemented search slice

The gateway/Scout stage now implements SearchToolGateway, SearchGateway, typed search payloads, gateway-only recorded Tavily wire transport, owner-scoped atomic attempt accounting, durable source/usage/events and pending shortlist review. RunContext/ToolResult schema 1.0 is retained; search artifacts/checkpoints use scout-1.0 and recordings scout-demo-v1. Completed results resolve to journal payload rows. See SCOUT_SPEC.md, ADR 0007 and SCOUT_STAGE_RESULTS.md. This supersedes historical search-only protocol status below. Generic retrieval/model gateway, full LangGraph checkpointer/worker/leases and live egress remain later work.

Version 1.0 proposal, 25 October 2026. Scope: PRD delivery stage 1 contract/design slice only. Original BRD targets remain authoritative; filenames are the originals authorized in the prior screenshot. No external calls or next stage. Source integrity and UI bundle readability rechecked. No change to UI design or source requirements.

## Boundaries and implementation status

| Boundary | Responsibility | This slice |
| --- | --- | --- |
| contracts.py | Typed run, budget, approval, tool call/result, checkpoint, event, replay and fault configuration | Pydantic v2 schemas and validation implemented |
| agent_schemas.py | Typed agent handoff skeletons and unreviewed evidence | Implemented skeleton; detailed domain schemas/services remain future |
| policy.py | Role/phase allowlist, artifact approval, budget/deadline preflight | Pure offline checks implemented; no atomic reservation, dispatch or authentication |
| ports.py ToolGateway | Validate/policy/reserve/execute/validate/persist | Protocol only; no dispatcher or live adapter |
| ports.py DurableState | Scope/version/fence CAS plus checkpoint/results/events transaction | Protocol only; no durable store or recovery executed |
| ports.py Replay | Ordered exact request/version matching with no live fallback | Protocol plus record validation; matching engine not implemented |
| ports.py FaultInjector | Operation/attempt-targeted deterministic failure in isolated server mode | Protocol plus FaultConfig validation; injector not implemented |
| evaluation.py | Separate citation presence and adjudicated support counts | Pure aggregation implemented; semantic adjudication not implemented |

FastAPI, LangGraph worker, Next.js, Supabase, Tavily/model/LangSmith adapters and deployment remain subsequent stages. No SDK construction, network import side effects or provider secrets in this slice. Existing local Python 3.13.5/Pydantic 2.10.3/pytest 8.3.4 are used without installation; pyproject declares ranges, not a reproducible lockfile.

## Typed context and trust

Quality-first/provider-neutral refinement: ADR 0005 and MODEL_IMPLEMENTATION_PLAN.md require a dedicated neutral ModelAdapter and explicit evaluated role profiles. Existing ToolGateway/Versions schemas are an offline skeleton, not a completed configurable provider architecture. Current scalar provider/model/prompt provenance needs a versioned manifest migration before heterogeneous routing. No schema/code change is made in this documentation stage. A budget stop cannot silently replace a selected model with a cheaper unevaluated model; report the constraint and retain partial work.

RunContext v1.0 carries UUID run/user/trace IDs, brief/run versions, graph/model/provider/prompt/tool/dataset versions, phase, timezone-aware deadline, budget, checkpoint ID, current shortlist/report hash/version and scoped approval decisions. Mode is replay-only. Models reject extra fields and unsupported schema versions. Containers use tuples; models are frozen. Positive counters reject booleans; money uses finite nonnegative Decimal. Pydantic validation is a shape boundary, not proof of authentication, evidence truth or database ownership.

Trusted services construct contexts from persisted authenticated state. Browser/model output cannot supply approved context, faults, version pins, usage or adjudicator identities. Never use model_construct/model_copy(update=...) to bypass validation at handoff. Pending approval is represented by phase plus absent valid grant; durable approval request/decision tables are still required. Historical decisions stay in the audit store; the active context projects only one current decision per gate. Ambiguity fails closed, rather than selecting a convenient prior approval.

## Gateway sequence and allowlists

1. Load authenticated owner-scoped run and lease; validate schema/version/phase.
2. Check cancellation/pause, deadline, role allowlist and current gate approval.
3. Match a completed versioned logical operation first; otherwise reserve maximum usage atomically under the run lock/CAS. Cached reads still require permission and deadline checks; count policy explicitly in future adapter tests.
4. For replay, require exact ordered transcript and pinned versions. For future approved live mode, check explicit egress/budget authorization and public destination policy before dispatch.
5. Apply timeout bounded by remaining deadline; retry only allowed transient statuses within recorded attempt limits. Inject clock/RNG for deterministic delays.
6. Validate typed result and agent output; persist completion/results/events/usage transactionally; checkpoint by durable completion IDs. Sanitize errors without logging input payloads or Pydantic ValidationError repr.

| Role | Allowed tools | Required phase |
| --- | --- | --- |
| Orchestrator | None; routing/state via trusted services | No tool dispatch |
| Scout | public.search, model.generate | discover |
| Researcher | public.search, public.retrieve, model.generate | research |
| Analyst | normalize, model.generate | analyze |
| Reviewer | normalize, model.generate | review |

Research/analyze/review require current shortlist approval. Final snapshot requires current report approval in the future transition service. The current require_approval helper validates a grant, not a full finalization transition. Publishing, contact, purchase and account tools have no schema or allowlist. Public URL schema is syntactic only: DNS/private-IP/connection/redirect/robots/access validation is mandatory in the future retrieval gateway. No claim of SSRF protection from AnyHttpUrl alone.

ToolCall is a discriminated union, not arbitrary args. ToolResult uses payload references instead of generic raw objects; failures require matching enumerated error codes and cannot masquerade as success. Payload storage must validate the concrete tool output schema and owner/source IDs; payload-reference existence is not yet enforced.

## Approval policy

Decision includes request/decision IDs, run/owner IDs, gate, artifact hash/version, decision and aware timestamp. Scope mismatch, rejection, missing decision, stale hash/version and ambiguous active decisions deny. Only authenticated owner decision service can insert human approval; agents cannot grant it. Both shortlist and report gates follow the prior architecture proposal; BRD only conditionally requires shortlist review. No external business action becomes authorized by report approval.

Future transition service must verify pending request status, actor role, expected run version, decision time and idempotency in one transaction. Same key/payload returns the same decision; changed payload conflicts. Changed artifact invalidates old approval; no zero-candidate research approval. A partial report is clearly labeled and never auto-finalized.

## Budget deadline retries

Budget tracks used/reserved/max calls, tokens and USD accounting cost. Overcommitted or negative/nonfinite values reject. Pure authorize checks one additional call, requested model output tokens, estimated cost and deadline. It does not reserve usage and is not concurrency-safe. Future gateway must include input tokens, possible repair/retry costs, rate limits and in-flight reservations atomically; prevent racing competitor lanes from overspending. Unknown live cost blocks dispatch without an approved conservative upper bound. Report actual cost separately from estimates; never refund uncertain paid calls as if unused.

At deadline equality, deny. Before every retry/resume recheck persisted deadline/cancel/usage. Timeout/429/5xx default to initial attempt plus two additional attempts; respect Retry-After only within remaining budget/time. Denial/robots blocks do not retry to bypass controls. Proposed malformed-output repair is one; targeted reviewer revision one, separately recorded under total budget. Schemas bound tool attempts to three, but no retry executor is implemented yet. Cancellation preserves results, stops new dispatch and attempts cooperative interruption; no refund or instantaneous remote cancellation promise.

## Durable checkpoints

Checkpoint contains checkpoint/run/owner IDs, graph version, run version, fencing generation, last event sequence, unique completed operation IDs and state hash. This is a pointer/manifest; the durable store must hold complete validated state, pending approval requests, payloads, usage and journal rows. Serialization roundtrip tests are not restart recovery tests.

Postgres transaction must reject owner/graph/version/fence mismatch and atomically commit operation results, event intent and updated state. Checkpoint references already committed completions; recovery reconciles journal against the last checkpoint before rescheduling. Unique operation keys include run/node/competitor/input/prompt/tool versions, with separate attempt IDs; idempotency cannot ignore changed inputs. Test crash windows before/after result persistence and before/after checkpoint persistence, lease expiry and stale writer commits. Local commits deduplicate completed work; response-before-commit can still repeat remote billing. Exactly-once remote execution is not promised.

## Replay and fault isolation

ReplayRecord is labeled DEMO and binds ordinal, dataset/versions, typed call and typed result operation/attempt. Future replay engine compares canonical validated arguments and versions against transcript order; mismatch/extra/missing operations fail, never fetch live. Include fake clock, RNG seed, UUID sequence, response payload hashes and expected event trajectory. Do not match solely on tool name. Recorded successful operations remain reusable only with matching ownership/input/version keys.

FaultConfig only permits enabled faults in trusted test/isolated_demo environments with server authorization and explicit target. Production rejects enabled or even configured fault targets. Labels are DEMO. Neither query parameters nor model output may set environment/authorization. Inject timeout/blocked/conflict/malformed/restart at operation/attempt boundaries; no random untargeted failure. Configuration tests verify fail-closed shape only, not production environment wiring or fault execution.

## Event schema and versioning

Event carries UUID event/run/trace, positive per-run sequence, aware timestamp, enumerated kind/agent/code, optional operation ID and version bundle. Tool completion requires operation ID. No arbitrary metadata, raw prompts, headers, source text or secrets field. UUIDs/strings still require trusted construction and logging allowlists; schema is not an automatic secret detector. Do not log exception inputs. Actual event uniqueness/order and payload redaction need repository/service tests later.

Schema version is literal 1.0; unknown versions reject. Persist schema/graph/prompt/model/tool/dataset versions. Future breaking schema changes require explicit migrator or quarantine; never silently deserialize into a new shape. Additive changes need reviewed readers and fixtures too. Checkpoint graph version mismatch requires migration or explicit failure. Per-run monotonically increasing sequence and event ID deduplication are database invariants; cursors resume persisted SSE/polling history.

## Scope and review

This stage tests contract validation and pure preflight/metric behavior only. Full golden trajectories, authentication, RLS, atomic budgets, storage, retries, replay consumption, fault injection, LangGraph and semantic evidence assessment remain unimplemented. See EVAL_PLAN.md and CI_GATES.md for gates without conflating them with passing validation tests. Stop for user review; do not scaffold the app automatically.
