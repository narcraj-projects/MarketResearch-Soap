# Lather Lens ordered backlog

## B14 requested security/load scope implemented for review

Read SECURITY_AUDIT.md, ADR 0015 and SECURITY_STAGE_RESULTS.md for the scoped authorization/RLS/SSRF/input/rate/CORS/privacy/retention/dependency audit, concurrent pool-starvation fix, actual measurements and tests. Safety defaults are local/owner-scoped; shared fleet/edge limits, retention/deletion periods, backup restore/RPO/RTO, human acceptance and paid model benchmark remain open decisions. No B15 preparation/deployment, live provider call, remote telemetry or cloud operation starts automatically. Stop for review; older status notes below are historical.

## B13 requested evaluation scope implemented for review

The 17 original golden cases, fixed five-failure cohort, deterministic graders, recorded graph/process execution, versioned baseline comparison, typed trusted-review API, per-run measurements and sanitized offline-tested LangSmith integration are implemented. Actual human support and five business-owner usefulness ratings remain absent and are reported unmeasured, not replaced by fixture scores. Paid/live evaluation and remote telemetry remain separately approved operations outside CI. EVALUATION_REPORT.md records executed results, regressions caught and limits. No B14 security/load work, provider selection, provisioning, publishing or deployment starts automatically. Stop for this review.

## B12 requested chaos/recovery scope implemented for review

Nine allowlisted recorded scenarios now exercise real harness/graph behavior, including process exit after one committed lane and fresh-process recovery after lease expiry. Server-only test configuration gates separate DEMO runs; production cannot enable injection. Live reflects persisted failures, repairs, partial state and approvals. CHAOS_SPEC.md, CHAOS_EVAL_RESULTS.json and CHAOS_STAGE_RESULTS.md identify actual evidence/limits. The predeclared five-case A05 cohort, live semantic quality and owner usefulness remain unmeasured as complete acceptance gates. No B13/full benchmark, live APIs, telemetry, provisioning, publication or deployment started. Stop for review before any subsequent stage. Older status notes below are historical.

## B11 requested history scope implemented for review

Immutable report revisions can now be browsed by exact version/hash and compared using stable evidence identities. History has real two-run/version controls, timeline, supported observation counters, before/after cards, filters and dated evidence. Gaps/omissions stay unknown/stale; only explicit correctly scoped source-reported discontinued status supports gone. HISTORY_SPEC.md/HISTORY_STAGE_RESULTS.md document actual tests and limits. No B12 chaos/recovery work, live APIs, provider selection, publishing or deployment started. Stop for this review. Older entries remain historical.

## B10 requested report scope implemented for review

Persisted run data now feeds all five screens; immutable report presentations expose real coverage denominators, issue flags, categorical positioning, eligible/missing prices, grounded opportunities and clickable evidence. Final approval requires an exact bound independent receipt and worker save; authenticated deterministic HTML/CSV exports are gated. History is a dated metadata archive only; B11 two-run semantic differences are not started. REPORT_SPEC.md and REPORT_STAGE_RESULTS.md record evidence/limits. No live API/model selection/publishing/deployment. Stop for this review; no subsequent stage automatically. Older stage status notes below are historical.

## B09 requested scope implemented for review

Deterministic same-SKU normalization, fact/source-claim/interpretation/hypothesis handoffs, evidence-linked comparison/opportunity rules, independent Reviewer checks, bounded targeted correction and visible unresolved outcomes are now implemented for DEMO replay. ANALYSIS_SPEC.md and ANALYSIS_STAGE_RESULTS.md record actual coverage and limits. Real strategic model quality, genuine-support coverage and owner usefulness remain unmeasured; the provider-neutral benchmark is still required. Stop for this stage review. Do not start B10, UI/export/history work, live APIs or deployment automatically. Older stage status entries below are retained as history.

# B08 requested scope implemented for review

Conditional LangGraph execution, owner-protected Postgres checkpoints, leased/heartbeating worker recovery, cancellation/resume, two durable review gates and persisted-event SSE/polling are now implemented for replay. WORKFLOW_SPEC.md and WORKFLOW_STAGE_RESULTS.md identify actual tests and limits. The analyze/review/revise/final/save trajectory uses honest DEMO evidence inventories and mechanical checks to exercise orchestration; B09's strategic analysis/independent semantic support and B10's full report/export remain pending. Do not start B09, paid benchmarks, live research, UI rewiring or deployment automatically.

## B07 requested scope completed for review

Independent public research/evidence is implemented and evaluated against recorded HTTP/news/DNS and dedicated local Postgres. RESEARCH_SPEC.md and RESEARCH_STAGE_RESULTS.md document attribution/security/extraction boundaries, actual checks and limits. Live access, broader quality benchmarking, full LangGraph orchestration/leases, analysis/review/report and later items remain unapproved/unimplemented. Saved review items are listed in RESEARCH_SPEC.md; do not start B08 or any subsequent stage automatically.

## B06 requested scope completed for review

Gateway/Scout is implemented and verified offline with recorded Tavily responses and dedicated local Postgres durability. Live Tavily activation, broader quality benchmarking, Researcher/evidence retrieval, full LangGraph worker and later backlog items remain unapproved/unimplemented. See SCOUT_SPEC.md and SCOUT_STAGE_RESULTS.md. Stop for this stage review; do not start B07 or any subsequent stage automatically.

Current stage: B05 is implemented to the requested five-screen UI scope, with real Brief persistence and four DEMO previews. UI_FIDELITY.md and UI_STAGE_RESULTS.md record deviations, tests and limits. This supersedes older notes saying frontend sign-in/screens do not exist. It does not complete B06..B16, durable research, real approvals/history, accessibility certification or M-series model evaluation. Stop for review; do not start the next item automatically.

25 October 2026. Ordered by PRD v1.1 delivery sequence. B01 is this documentation stage; all later entries are planned and require a separate user prompt/review. A stage completion never authorizes the next stage. No API calls or deployment in the current task. Exact commands for future tests will be supplied when runnable implementations exist; IDs below are specifications, not results.

| Order | Stage | Smallest coherent deliverable and dependencies | Exit evidence and approval boundary |
| --- | --- | --- | --- |
| B01 | Source audit and architecture | Read originals; traceability, architecture, ADRs, contradictions, this backlog; depends on supplied sources | Source checks, actual changed-file/command record; STOP for review |
| B02 | Harness and evaluation design | Typed run/tool/evidence contracts, deny policy, offline adapters, bounded execution; depends B01 review | pytest schema/policy/math checks; first versioned DEMO fixture cohort with actual outcomes; no live calls; STOP |
| B03 | Scaffold | FastAPI/worker and Next.js TypeScript skeleton, configuration validation, health endpoints, generated client foundation; depends B02 | Local build/typecheck/health tests; runtime and dependency compatibility recorded; no hosting; STOP |
| B04 | Auth and database | Alembic schema, Supabase Auth/RLS integration, ownership, durable jobs/events/approvals; depends B03 | S01, D14/D17 DB tests locally; no cloud provisioning without approval; STOP |
| B05 | UI fidelity | Five reference screens, validated forms, responsive/accessibility and honest DEMO data; depends B03/B04 contracts | UI01–UI06 Playwright/rendered comparisons; record deviations; STOP |
| B06 | Gateway and Scout | Tavily/retrieval/model adapter interfaces and public URL policy; evidence-ranked discovery; depends B02/B04 | D01–D06, T02, S02/S03 offline; live search/model calls require explicit budget approval; STOP |
| B07 | Researcher and evidence | Full FR-03 fields, snippets, source dates/status/hash and deterministic price observations; depends B06 | D07–D11, T03/T04; no unsupported skincare facts; STOP |
| B08 | LangGraph durable execution | Conditional routing, fan-out, Postgres checkpoint reconciliation, leases and approvals; depends B04/B06/B07 | D13/D14/D16/D17, T08 crash/concurrency tests; retain completed work; STOP |
| B09 | Analyst and Reviewer | Comparison, full opportunity schema and independent review, bounded revision; depends B07/B08 | T05/T06, D11/D12, unsupported hypotheses flagged; STOP |
| B10 | Report and final approval | Full FR-07 report, exact-draft approval, immutable snapshot/export; depends B05/B09 | T07, UI04, A02/A03/A08; real-source sample only after authorized research; STOP |
| B11 | History | Two-run dated comparisons and uncertainty; depends B10 | D15/UI05; no implicit discontinuation or old-as-current data; STOP |
| B12 | Chaos and recovery | Server-isolated DEMO faults and meaningful failure demonstration; depends B08/B10 | D04/D05/D06/D10/D12 cohort plus restart/security cases; actual recorded outcomes; STOP |
| B13 | Evaluation gates | Full pinned dataset regression, coverage/adequacy, owner rubric and real report sample evidence; depends B10–B12 | All eight BRD targets measured separately; H01 five owner-rated actual reports; no synthetic live-quality claims; STOP |
| B14 | Security and load | Secret/dependency checks, isolation, SSRF/redirects, budgets, measured performance, retention/backups/rollback design; depends B13 | S01–S04/P01; actual usage/latency; unresolved operating policies decided; STOP |
| B15 | Deployment preparation and optional approved deployment | Runbook, environment matrix, migrations/rollback and concrete reviewable deploy plan; depends B14 | No provisioning/publishing/deployment until explicit approval; current pricing/limits verified only in approved scope; STOP |
| B16 | Demo and handoff | Setup/config guide, source export, real sourced sample report, test/eval results, normal and recovery recording, limitations; depends B13/B14 and B15 only if hosting approved | BRD sections 15/16 deliverables checked; owner review; no claim complete without evidence |

## Pending design review items

B04 backend Auth/storage is now implemented and tested against the dedicated local Supabase stack. See AUTH_STORAGE.md and AUTH_STORAGE_STAGE_RESULTS.md for scope and actual evidence. Frontend sign-in UX, real research, durable worker/checkpointer recovery and full business acceptance remain later work. Do not start B05 or any M-series evaluation automatically.

B03 scaffold is now implemented to the current user-requested scope: pinned frontend/backend foundations, health/configuration tests, frozen locks, local commands and CI configuration. Read SCAFFOLD_STAGE_RESULTS.md for executed evidence and limitations. This does not complete remaining B02 workflow/replay work, B04 auth/database, B05 five-screen fidelity or M01–M08 model evaluation. Stop for review before any of those changes.

The subsequent quality-first architectural decision adds MODEL_IMPLEMENTATION_PLAN.md M01–M08: review/prepare the benchmark, implement a neutral offline model interface and versioned role provenance, then an offline runner before any separately approved live experiment or final model choice. Existing B01–B16 ordering remains; B06 live integration depends on reviewed neutral adapters, and final role selection/B13 acceptance depends on quality benchmark and actual report evidence. This is a planning update only, not completion of B02 or permission to start B03. No cheapest-provider default or cost-weighted model ranking is allowed. Approved caps/deadlines remain hard limits.

Review C01–C15 in ARCHITECTURE.md, particularly mandatory shortlist approval, explicit insufficient opportunity count, retry wording, Pause/Resume/clarification API additions, fit unknown handling and model-repair/reviewer-revision limits. These are proposed implementation decisions, not edits to the BRD.

Before live work, obtain approved provider/model configuration, search/model budget and separate telemetry authorization. Credit screenshots do not authorize spending. Before hosting, decide retention/deletion periods, backup/recovery objectives and operating budget; do not invent business targets. None of these needs to be provisioned to complete B01.
