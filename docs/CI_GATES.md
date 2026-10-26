# Lather Lens CI and acceptance gates

## B14 security and local-load checks

The standard offline/backend/frontend checks collect SEC01..09 and SEC-BFF01..04; the existing dedicated local database job collects SEC10..12 with the full authorization/RLS/approval/restart/rollback suite. SEC12 executes two real graphs concurrently with recorded providers, real durable approvals and saves; no latency pass threshold is invented. A bounded standalone 1/2/4-worker benchmark saves observed timings separately. A new public-dependency-audit job uses Python standard library and locked package names/versions only; network failure/incomplete coverage, advisories or secret-pattern findings fail rather than report a clean result. No paid credentials are supplied. Hosted CI execution is untested here. SECURITY_STAGE_RESULTS.md records actual local outputs and open release risks. Previous screenshots remain immutable; fresh chaos browser captures now go to ignored `.cache/current-chaos-regression`.

The implementation fingerprint includes security/Auth/queue/lease/storage code. An intentional code-version change must fail comparison to the previous baseline; a new immutable proposed baseline requires a complete actual execution and independent repeat. Baseline review remains a human gate, and the original A02/A04 acceptance remains unmeasured. No B15 work follows automatically. Older entries below are historical.

## B13 current deterministic and business gates

Offline pytest adds dataset/version/path/hash checks, Decimal/null/permission/approval/trajectory mutations, fixed failure denominators, baseline drift, unknown human gates, role binding and actual LangSmith SDK HTTP-body privacy tests with sockets denied. Dedicated local integration tests exercise real Auth/RLS, owner/server grants, immutable receipts, stale hashes, idempotency, production golden-plan refusal and forced timeout ordering outside the shared origin lock. The local-auth-storage job then executes all 17 predeclared golden cases against the proposed pinned baseline. It uploads safe results/sanitized traces only; private review packets and credentials remain excluded.

All strict deterministic cases and critical baseline checks must pass. A05 at 4/5 cannot excuse a failed critical case. A02 >=90% genuine support requires complete trusted adjudication, and A04 requires five real owner ratings with >=4 useful. Unknown evidence is a release blocker, not a CI fixture score. Initial baseline awaits user review. Automatic worker LangSmith tracing remains disabled; remote export is an explicitly approved/capped command to an existing project, and paid/live evaluation is rejected from this CLI. No paid secrets are supplied to push/PR CI. Hosted CI has not run here. Exact actual results and commands: EVALUATION_REPORT.md. No B14 or deployment stage automatically.

## B12 added blocking local regression coverage

Normal check runs CP01..CP09 offline with network denied, Ruff/mypy, frontend BFF/event tests and production builds. Dedicated local Auth/Postgres integration adds CI01..CI07: all nine scenarios, real subprocess exit/recovery with preserved lane/source hashes, production planted-plan refusal, isolation/idempotency and terminal malformed/budget failures. Failure is not retried by pytest. Wire attempts <=3, schema repair <=1 and Reviewer revision <=1 remain application gates.

The existing local-auth-storage CI job now prepares all nine DEMO scenarios under explicit test-only flags, then starts the browser-test server with LATHER_UI_INTEGRATION=1/LATHER_UI_CHAOS=1. UI-CHAOS-* verifies server capability gating, real queueing with no fabricated progress, persisted recovery/partial states and final approval waiting. The offline UI job excludes these dedicated-stack tests. Screenshots use a new chaos folder; previous approved captures/baselines remain intact. Hosted CI has not executed here; local actual outputs are in CHAOS_STAGE_RESULTS.md. The full BRD acceptance cohort/live-quality/model benchmark remains pending and no B13 stage starts automatically.

## B11 history gates

Add offline history golden/negative tests, local Auth/Postgres HI01..HI04 and browser UI-HISTORY-DIFF/GAP. Block cross-owner/version leakage, mutable historical artifacts, unapproved comparison, inferred gone from retrieval failure, wrong SKU/variant/price basis, and stale-cache-as-change regressions. Existing process recovery/rollback/approval/export checks remain required. The local CI job prepares history DEMO fixtures after destructive disposable rollback checks and before browsers, and uploads actual B11 captures. Generic current-screen captures go to ignored cache so earlier stage artifacts are preserved. Offline UI checks exclude integration-only history cases explicitly. CI configuration changed; hosted CI has not run here. Actual local results: HISTORY_STAGE_RESULTS.md. BRD business gates and model quality benchmark remain separate.

## B10 local report gates

Add test_reporting.py R01..R09 (19 parameterized tests), test_reporting_storage_integration.py RI01..RI03, frontend report.test.ts UI-R01/UI-R02/BFF-R01..R03, and real persisted browser UI-PERSIST-* paths. CI's local Auth job prepares recorded DEMO review/saved runs after rollback tests and runs the complete browser suite. The offline UI job runs auth/empty/error/keyboard/save-failure tests; persisted tests explicitly require local integration. Actual responsive screenshots are artifacts, not automated pixel equivalence to the original HTML; prior static-preview baselines are preserved and no longer active.

Block on cross-owner access, final-approval/save bypass, source denominator errors, unsafe export, mutable report or missing-value regression. All business gates remain separate from unit counts. Exact executed results and limits: REPORT_STAGE_RESULTS.md. Hosted CI is configured, not executed or provisioned in this stage. No network API/paid model calls or publishing. Older stage gate descriptions below are historical.

## Current B09 gates

Existing offline and dedicated local integration jobs collect analysis unit/golden tests and actual correction/unresolved trajectories. Required critical controls include same-item proof before normalized values, no implicit FX, null missing/ambiguous values, exact rounding/zero semantics, scoped citations/attribution, retained contradictions, no medical-efficacy promotion, bounded targeted correction, unresolved schema/limit failures and exact review/report/human-approval binding. Existing restart/fence/RLS tests remain required. Hosted CI was not run in this stage; actual local checks are in ANALYSIS_STAGE_RESULTS.md.

The new Reviewer reports citation presence and quote integrity separately, with genuine_support_coverage=null and semantic_support=not_adjudicated. These mechanics do not pass the original 90% genuine support or 4/5 owner usefulness gates. The 30-day freshness default is a proposed input policy, not a new BRD threshold. Model benchmark and original eight release gates remain unchanged. Older inventory-only status below is historical.

# Current durable workflow gates

The existing local-auth-storage CI job automatically collects the new workflow integration module, including actual child-process recovery and Postgres checkpoint/RLS/migration checks. Default offline pytest also collects W01..W05/W17/W18; it still denies sockets. LANGSMITH_TRACING/LANGCHAIN_TRACING_V2 are false and strict MsgPack is enabled in CI/local commands. Worker invocation also disables tracing explicitly. No hosted CI execution is claimed; local executed results are in WORKFLOW_STAGE_RESULTS.md.

Critical gates now include no forged or stale approval resume, unchanged committed lane after lost process, stale-generation write/heartbeat rejection, cancellation before dispatch, fixed deadlines, bounded revision, stream owner isolation/cursor parity, immutable reports and rollback/reapply. A failing critical gate blocks release even if a numeric failure cohort otherwise meets 4/5. DEMO inventory mechanics cannot establish semantic support, useful strategic analysis or the full original BRD acceptance; all prior quality/model/release requirements remain.

## Public research gate addition

The existing checks/local-auth-storage jobs collect the new research unit and integration tests. Required: no unauthorized/live egress, full public-address/DNS/peer/redirect and robots/access checks, bounded recorded requests/budgets, independent lane attribution, null ambiguous packs/SKUs, retained contradictions, exact immutable quote links, owner/RLS reads and safe rollback. Explicit offline evaluation: from backend/, `uv run --frozen --extra test --no-sync python tools/evaluate_research.py --output ../docs/RESEARCH_EVAL_RESULTS.json`. It is not a live security, semantic support or usefulness score. Hosted CI execution and frontend research wiring are not claimed.

## Gateway/Scout gate addition

Existing check and local-auth-storage jobs now collect the new offline Scout and local Postgres tests automatically. Required: pinned recording hashes/versions/exact requests with no live fallback; zero invented quota fill in controlled fixtures; role/phase/schema/URL boundaries; bounded retries/deadline/call-cost reservations; owner-bound durable shortlist approval; restart without repeating committed search. The adapter has no enabled real transport/key factory. The offline evaluation command is `cd backend; uv run --frozen --extra test --no-sync python tools/evaluate_scout.py --output ../docs/SCOUT_EVAL_RESULTS.json`. That report is explicit execution evidence, not a CI baseline auto-update. No hosted CI execution or live-quality gate is claimed.

## UI stage addition

See UI_STAGE_RESULTS.md for local evidence. CI now defines a Windows Chromium visual/interaction job with ten OS-specific baselines, plus local Auth/Postgres browser persistence in the existing Linux integration job. CI never updates baselines. Traces/videos/Auth screenshots are off; uploaded screenshot artifacts contain signed-out synthetic previews. Default UI tests explicitly skip UI-API without the dedicated local integration flag; CI invokes it separately. No hosted CI execution is claimed.

UI-KEY/STATE/RESP/INTERACT/SAVE-ERROR/SAVE-LOADING and BFF-01..04 cover this stage. Existing isolation/rollback tests remain required. Visual baselines detect implementation changes, not automated pixel identity with the source. Full accessibility/browser certification and A01..A08 research acceptance remain outstanding. This appendix supersedes historical frontend-status entries below.

Version 1.0 gate design, with scaffold update below. The repository now contains .github/workflows/ci.yml for lint/typecheck/tests/build; no hosted workflow has been executed or deployment configured. Production/branch protection must not treat absent future test groups as passed. All provider access, tracing and paid integration are disabled by default.

## Scaffold update

Auth/storage stage now adds a separate local-auth-storage CI job using the pinned Supabase CLI, real local Auth/Postgres, least-privilege runtime role and explicit integration tests. Normal checks select non-integration tests and keep socket denial. Integration allows only the dedicated loopback ports and validates a local database instance marker before migration rollback. S01 owner/RLS and start/approval idempotency now have actual local evidence; hosted CI/cloud behavior and LangGraph recovery remain unverified. See AUTH_STORAGE_STAGE_RESULTS.md.

Use the pinned repository-local backend environment via scripts/project.ps1 or Makefile. Backend dependencies and the build backend now have exact pins plus uv.lock; frontend has exact pins plus package-lock.json. Current scaffold checks add HTTP health/configuration tests and frontend health-contract tests. The earlier Anaconda command below records the harness-only environment; the current reproducible commands/results are in README.md and SCAFFOLD_STAGE_RESULTS.md. CI installs frozen locks, disables Next telemetry and pytest plugin auto-loading, and supplies no service secrets. No full BRD acceptance or model benchmark result is inferred from scaffold checks.

## Local validation gate implemented now

Use the existing local environment, without installation/network:

```powershell
# From E:\HandmadeSoap-MarketResearch\backend
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
& 'C:/Users/narcr/anaconda3/python.exe' -m pytest -q
```

Pydantic 2.10.3 and pytest 8.3.4 were found in that Python 3.13.5 environment. pyproject.toml declares Python >=3.12 and dependency ranges; no lockfile or cross-platform compatibility guarantee exists. Standard PATH Python 3.15 has no Pydantic; invoking it will not run this suite as-is. Future supported CI runtime/pins must be selected and locked in the scaffold stage, not inferred from this machine.

Contract tests V01–V25 cover schema/version/extra-field rejection, counters/budgets, tool/phase allowlists, gate scope/hash/version, deadlines, attempts/results, replay/checkpoint roundtrip invariants, production fault denial, event payload restrictions, citation-versus-support aggregation and agent handoff shape. Tests block socket connection/DNS APIs via an autouse fixture and disable third-party pytest plugin auto-load. This is a test-level guard, not an OS sandbox or proof of all possible egress paths. No live SDKs or external adapters exist in the package.

From workspace root, additional local checks:

```powershell
powershell -NoProfile -File scripts/verify-sources.ps1
node scripts/verify-ui-reference.cjs
powershell -NoProfile -File scripts/verify-design.ps1
```

These verify unchanged sources, embedded screen readability, document IDs and exact BRD targets. They do not measure UI fidelity or application acceptance. Actual outputs appear in the stage results record.

## Required future merge gates

Model-selection gate added by ADR 0005: require a reviewed provider-neutral benchmark, canonical adapter conformance, per-role resolved profile provenance and MODEL_BENCHMARK.md quality eligibility before final model selection. Do not choose on credits, cost-weighted scores or citation presence. Missing/inconclusive benchmark evidence means no final selection; current 49 validation checks cannot satisfy this gate. Approved monetary caps/deadlines remain enforced. No live model evaluation or benchmark runner exists yet.

| Gate | Required outcome | Status now |
| --- | --- | --- |
| Contract validation | All schema/preflight tests pass offline; no weakened baseline without review | Implemented local gate |
| Provenance and math | No invented controlled candidates; correct same-SKU Decimal arithmetic; no hidden missing data | Full T02–T07/D01–D12 not implemented |
| Policy/security | Zero approval bypass or unauthorized action; ownership/RLS; SSRF/redirect/access rules; no secret leakage; production chaos denied | Pure policy/config tests only; integration S01–S04 not implemented |
| Durable recovery | All state/schema/security/recovery deterministic checks pass; committed work and pending gates survive crash | D13/D17/T08 database execution not implemented |
| Deterministic replay | Exact ordered/versioned transcript match, no live fallback; full golden suite recorded | Record schema only; D01–D17 workflow suite not implemented |
| Budget/deadline | Concurrent reservation limits; no post-deadline/retry/cancel dispatch | Pure preflight only; D16 integration not implemented |
| Model/prompt/tool regression | Pinned dataset/baseline; trajectory/support/budget diff; fail critical regression | No workflow baseline yet |
| UI | Build/type checks and UI01–UI06 interaction/fidelity/accessibility | No frontend implementation |
| Performance/cost | Record actual latency/usage/cost and configured caps; never invent numeric SLO | P01 not executed |

Future CI uses outbound-network denial, pinned dependencies, fake credentials, deterministic clocks/RNG/IDs and isolated local Postgres. Database fixtures test transactions, fences and restart, not in-memory stand-ins. Record every failing test and its report impact; do not skip missing groups and still label the app release-ready. No hosted CI service is provisioned here.

## Original BRD release acceptance

EVAL_PLAN.md retains all eight exact target strings and operational measurements, aligned with REQUIREMENTS_TRACEABILITY.md A01–A08. Release evidence requires three relevant competitors when supported; >=90% genuine supported factual claims; required fields populated/unavailable; >=4 of 5 owner-useful reports; >=4 of the predeclared five failure cases handled; restart without lost completed work; no knowingly fabricated final facts; final human review before external business action. These application gates remain unevaluated.

The >=4/5 failure target never permits bypassing a critical math/schema/security/recovery gate. Citation presence is diagnostic; only source-resolved, scope-correct, trusted-adjudicated support counts for A02. Human usefulness requires the business owner; LLM-as-judge is supplemental only. A06 needs real durable restart evidence. Missing/nonexecuted acceptance evidence blocks release rather than becoming a zero-denominator pass.

Live search/model evals, LangSmith transmissions, cloud resources and deployment require separate explicit approvals/budgets. Successful local validation does not authorize them or the next implementation stage. Stop for review after this stage.
