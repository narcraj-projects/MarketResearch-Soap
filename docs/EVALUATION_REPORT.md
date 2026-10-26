# Lather Lens evaluation report — B13

25 October 2026. **Recorded DEMO evaluation only. Not a release acceptance pass.** This stage implements the requested golden datasets, deterministic/tool/trajectory graders, trusted claim/owner review protocol, sanitized LangSmith integration, regression comparison and per-run measurements. No subsequent stage has started.

B14 follow-up: [SECURITY_STAGE_RESULTS.md](SECURITY_STAGE_RESULTS.md) records the later security/concurrency regression run, expanded implementation fingerprint, proposed baseline and limits. This B13 report's measurements, original proposed baseline artifacts and fixture expectations are retained as historical evidence; they do not describe B14 operating capacity or establish real-source support/owner usefulness.

## Requirements and inputs

BRD section 12 remains authoritative for business acceptance, the original HTML for visual fidelity and PRD v1.1 for implementation proposals. All three originals are readable and unchanged; the authorized aliases, full BRD XML/notes/footer and five decoded HTML templates were inspected across the source audit/current work. Source hashes and all eight verbatim BRD target strings pass. No original requirements, old migration, previous fixture or existing UI screenshot was changed. This stage adds no screen redesign or database migration.

Plan and boundaries: [EVALUATION_SPEC.md](EVALUATION_SPEC.md), [ADR 0014](adr/0014-versioned-evaluations-and-trusted-review.md), [traceability](REQUIREMENTS_TRACEABILITY.md), [CI gates](CI_GATES.md). Harness contracts and recorded data precede quality claims. The provider-neutral quality-first benchmark remains required before final model selection; cost/latency are diagnostics, not a model quality score.

## Actual measured outcome

- Dataset: **lather-golden-v1**, 17 predeclared cases D01..D17; manifest SHA-256 `6f60321ef33c7faa8019b09fcc00866427e9d007282b2e38ed3bc82e40ead14a`.
- Final independent run: **17/17 passed**; fixed original failure cohort **5/5 handled**; deterministic CI result `True`.
- Baseline: proposed revision `lather-golden-v1-r2.json`, SHA-256 `40174b268c448328d3442b37e3076e0e4fae869140f75eedbaf276cf0750d668`; **pending user review**, not automatically approved.
- Comparison: compatible versions/manifest, **0 critical changes**. Actual per-case latency/call/token/cost deltas are in [golden-regression.json](evaluations/golden-regression.json). Initial and revised baseline runs are separate actual executions, not expected values relabeled as observations.
- Actual provider calls **0**, provider tokens **0**, provider spend **0 USD**. Model handoffs are labeled synthetic frozen rule-output projections, not captured provider responses or tokenizer estimates.
- LangSmith **0 remote exports**. Sanitized local traces were collected from actual persisted events; the pinned real SDK was tested through an in-memory HTTP session with sockets denied. Hosted LangSmith is untested.
- Actual business-owner ratings: **0/5 received**; useful count **unmeasured**. Trusted material-claim support: **unmeasured**; no fabricated human/golden/model judgments were substituted.

Fifteen cases use actual owner-RLS Postgres, graph/checkpoints, worker/gateway and approval execution. D05 is a gateway Retry-After/deadline component test; D15 is a dated-history component test. Component cases do not claim full workflow execution. Case inputs, recorded transcripts, arithmetic expectations and fixed cohorts were pinned before the first execution and remained unchanged through the scheduling fix.

## Per-case actual results

All names, examples, sources, prices and reports are synthetic **DEMO**. The measurements below are actual local recorded execution, not hosted/live model performance. Calls count journaled recorded tool/model handoffs. Model attempts are schema-validation replays; actual provider tokens/cost remain zero for every row.

| Case | Actual final state | Local latency ms | Completed calls | Recorded model attempts | Provider tokens | Provider USD | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| D01 | complete | 3400 | 10 | 0 | 0 | 0 | PASS |
| D02 | complete | 3229 | 8 | 0 | 0 | 0 | PASS |
| D03 | partial | 767 | 2 | 0 | 0 | 0 | PASS |
| D04 | complete | 3892 | 12 | 0 | 0 | 0 | PASS |
| D05 | component_complete | 13 | 3 | 0 | 0 | 0 | PASS |
| D06 | complete | 4446 | 10 | 0 | 0 | 0 | PASS |
| D07 | complete | 3915 | 12 | 0 | 0 | 0 | PASS |
| D08 | complete | 5411 | 10 | 0 | 0 | 0 | PASS |
| D09 | complete | 4100 | 10 | 0 | 0 | 0 | PASS |
| D10 | partial | 3023 | 12 | 2 | 0 | 0 | PASS |
| D11 | complete | 3708 | 10 | 0 | 0 | 0 | PASS |
| D12 | complete | 4961 | 11 | 1 | 0 | 0 | PASS |
| D13 | complete | 17449 | 10 | 0 | 0 | 0 | PASS |
| D14 | report_review | 3842 | 10 | 0 | 0 | 0 | PASS |
| D15 | component_complete | 249 | 0 | 0 | 0 | 0 | PASS |
| D16 | cancelled | 2454 | 3 | 0 | 0 | 0 | PASS |
| D17 | complete | 3700 | 10 | 0 | 0 | 0 | PASS |

Local replay median: **3708 ms**; range **13–17449 ms**, sample 17 heterogeneous cases. These are descriptive numbers, not an SLA or statistically representative benchmark. D13 includes actual worker startup/lease recovery; scripted fixture approvals are included, while real human deliberation is absent. D04 virtual retry delays (0.5/1 seconds) are recorded separately from measured wall latency. Complete actual versions, measurements, signatures and diagnostics: [final results](evaluations/golden-regression.json); [sanitized traces](evaluations/golden-regression.traces.json).

Versions: graph `workflow-1.2`; provider/model `none`; prompt `DEMO-frozen-analysis-1.0`; search `tavily-search-1.0`; public research `public-research-1.0`; model replay `model-replay-1.0`; graders `graders-1.0`; LangSmith SDK `0.14.12`. Baselines additionally bind scorer and normalized critical implementation hashes. The direct SDK dependency was pinned to its already installed/locked compatible version using offline resolution; no provider package or paid model was selected.

## Original BRD acceptance gates

| Gate | Exact BRD acceptance target | Actual evidence / status |
| --- | --- | --- |
| A01 | Three relevant competitors identified when sufficient evidence exists | D01..D03 controlled relevance/provenance/shortfall cases pass; real-market adequacy untested |
| A02 | At least 90% of material factual claims linked to supporting sources | **Not evaluated for genuine support**. 11 saved DEMO reports contain 521 material findings; 521/521 have links and 521/521 have intact quote provenance. Those wiring diagnostics are not supporting-source adjudication or a 90% gate pass |
| A03 | Required comparison fields populated or explicitly marked unavailable | Controlled D06..D09 field/null/scope cases pass; broader real-source completeness untested |
| A04 | At least 4 out of 5 test reports rated useful by the business owner | **Not evaluated**: 0 real ratings. Fixed cohort D01/D02/D07/D08/D11 resolves to five distinct exact saved reports; no usefulness score invented |
| A05 | At least 4 out of 5 designed failure tests handled correctly | **5/5 passed in the predeclared controlled cohort D04/D05/D06/D10/D12**; not a substituted denominator or live reliability claim |
| A06 | Interrupted research run resumes without losing completed results | Controlled D13 actual process exit 23, lease reclaim, identical saved task/source rows, only six remaining web dispatches, pending approvals preserved and stale writer denied |
| A07 | No knowingly fabricated facts in the final report | Controlled identity/medical/unsupported-fact negatives pass; injected assertion removed from immutable v2. Independent live factual adequacy remains unreviewed |
| A08 | Final report presented for review before any external business action | Controlled durable owner/hash/version gates and bypass negatives pass. External business-action tools remain absent/denied; no external business action performed |

**Release remains blocked.** Complete trusted semantic adjudication, five actual owner usefulness decisions, reviewed baseline, approved live research/model-quality evidence and the provider-neutral benchmark are missing. `--release-check` actually returned exit **2**; paid `--live` and unapproved remote trace export actually refused with exit **1**. Successful deterministic CI cannot turn these unmeasured gates into a release pass.

## Presence is not support

Material findings include all asserted non-null facts and source-attributed claims, including unsupported/uncited ones; unknown notices without asserted product facts are excluded. Factual premises of interpretations/hypotheses remain in the denominator. Zero material claims reports unavailable, never 100%.

Link presence checks wiring. Quote integrity checks exact source/excerpt/hash. Neither establishes relevance, entailment, correct date/SKU/variant/pack/currency, attribution, contradiction handling or medical efficacy. D12 deliberately attached an intact irrelevant quote to an unsupported medical assertion; the actual independent Reviewer requested correction and the final version removed it. No genuine-support percentage is inferred from the 521/521 citation diagnostic.

Typed owner-protected review packets, server-granted reviewer/owner roles, personal attestations, complete review checklists and exact immutable report/statement/source bindings are implemented. Bare self-labelled JSON, model labels and `demo_fixture` receipts cannot count as trusted human evidence. Partial adjudication is incomplete, with only a confirmed lower bound; final coverage requires complete review. Actual human expertise/independence cannot be established by schema tests. No real judgment has been submitted. The existing-report grading command reads stored receipts without regenerating/cherry-picking reports; [actual receipt results](evaluations/existing-review-results.json) remain unmeasured.

Private review material is in ignored `.cache/evaluation-review-packets.json`; it is never included in LangSmith/CI uploads. API reads/writes require actual Auth/owner isolation and explicit server human-role grants. Role grants default empty. Reports and receipts remain immutable; no support label is written back into agent output. No new frontend review screen is claimed.

## Regressions caught and corrected

The first run and proposed baseline passed 17/17. An independent repeat returned **16/17**, with D04 failing and a critical baseline difference; the recovery aggregate was 4/5, but strict CI still failed. The fault scheduler waited for the first two lanes **inside** the shared news-origin mutex, sometimes blocking those same lanes. The wait now occurs before entering the gateway's origin lock. ER06 forces the third lane to arrive first and confirms two saved tasks/three terminal timeouts without that deadlock. No case expectation/transcript/denominator was weakened or rewritten.

The earlier baseline and [failed comparison](evaluations/golden-regression-initial.json) are preserved. A new proposed baseline revision records the corrected implementation, followed by the final independent all-pass comparison. A typing-only RowMapping-to-dict adaptation and initial unused-import/style findings were corrected rather than suppressing checks. The initial all-pass evaluation, first baseline run, failing comparison, revised baseline run and final comparison are distinct executions; their counts are not added into a larger independent quality sample.

## Tests executed and actual outputs

| Check | Actual output |
| --- | --- |
| Source/design verification | 3 source hashes match; FR-01..09 readable; all 8 target strings occur verbatim; 5 original HTML templates decode |
| Backend Ruff | `All checks passed!` |
| Backend mypy | `Success: no issues found in 66 source files` |
| Final full offline pytest | `289 passed, 71 deselected in 10.00s`; [JUnit](evaluations/evaluation-unit.xml) |
| Focused graders/privacy tests | `18 passed in 1.32s`; includes actual LangSmith SDK payload privacy, baseline/version/trajectory mutations and unknown human gates; [JUnit](evaluations/evaluation-graders.xml) |
| Complete local Auth/storage regression | `70 passed, 289 deselected in 496.11s (0:08:16)`; prior 65 plus original 5 review tests; [JUnit](evaluations/evaluation-integration.xml) |
| Final review/forced-order integration file | `6 passed in 28.42s`; includes added ER06 and current read-only review metrics after typing adaptation; [JUnit](evaluations/evaluation-api-final.xml) |
| New metrics endpoint focused check | `1 passed, 4 deselected in 7.84s`; [JUnit](evaluations/evaluation-metrics-api.xml) |
| Recorded golden final comparison | 17/17 pass; fixed failure cohort 5/5; zero critical regression; zero provider calls/export |
| Frontend ESLint / TypeScript | exit 0, zero warnings; `Types generated successfully` |
| Frontend Vitest | 5 files, 21 tests passed |
| Python / Next production builds | offline sdist/wheel built; Next compiled/typechecked and generated 15 pages; Alembic `0006 (head)` |
| OpenAPI | `Exported OpenAPI with 38 paths; no settings or credentials included` |
| Live/export/release refusal | Expected exits 1/1/2 observed; no provider call/remote transmission |
| Local cleanup | `PASS local Supabase stop; credentials not displayed`; volumes retained |

The 70-case full integration run preceded ER06 and the final test-harness ordering fix; the six-case affected file then passed, covering all 71 distinct integration cases across those executions. A single final 71-case full rerun is not claimed. Full offline tests and baseline comparison use final source. No test was skipped to hide a failure. Hosted CI is configured, not executed here. No browser rerun was needed for this backend/evaluation stage; frontend builds/tests pass and previous screenshots remain intact.

## Actual files changed

<!-- FILES-BEGIN -->
76 files: 58 added, 18 modified, 0 deleted.

| Change | Actual file |
| --- | --- |
| modified | [.env.example](../.env.example) |
| added | [.gitattributes](../.gitattributes) |
| modified | [.github/workflows/ci.yml](../.github/workflows/ci.yml) |
| modified | [backend/app/api.py](../backend/app/api.py) |
| modified | [backend/app/config.py](../backend/app/config.py) |
| added | [backend/app/evaluations/__init__.py](../backend/app/evaluations/__init__.py) |
| added | [backend/app/evaluations/acceptance.py](../backend/app/evaluations/acceptance.py) |
| added | [backend/app/evaluations/baseline.py](../backend/app/evaluations/baseline.py) |
| added | [backend/app/evaluations/contracts.py](../backend/app/evaluations/contracts.py) |
| added | [backend/app/evaluations/dataset.py](../backend/app/evaluations/dataset.py) |
| added | [backend/app/evaluations/graders.py](../backend/app/evaluations/graders.py) |
| added | [backend/app/evaluations/review.py](../backend/app/evaluations/review.py) |
| added | [backend/app/evaluations/runner.py](../backend/app/evaluations/runner.py) |
| added | [backend/app/evaluations/telemetry.py](../backend/app/evaluations/telemetry.py) |
| added | [backend/app/evaluations/workflow.py](../backend/app/evaluations/workflow.py) |
| modified | [backend/app/harness/model_replay.py](../backend/app/harness/model_replay.py) |
| modified | [backend/app/harness/retrieval.py](../backend/app/harness/retrieval.py) |
| modified | [backend/app/worker.py](../backend/app/worker.py) |
| added | [backend/evaluations/baselines/lather-golden-v1-r2.json](../backend/evaluations/baselines/lather-golden-v1-r2.json) |
| added | [backend/evaluations/baselines/lather-golden-v1.json](../backend/evaluations/baselines/lather-golden-v1.json) |
| added | [backend/evaluations/fixtures/golden-v1/cases.json](../backend/evaluations/fixtures/golden-v1/cases.json) |
| added | [backend/evaluations/fixtures/golden-v1/manifest.json](../backend/evaluations/fixtures/golden-v1/manifest.json) |
| added | [backend/evaluations/fixtures/golden-v1/model-scripts.json](../backend/evaluations/fixtures/golden-v1/model-scripts.json) |
| added | [backend/evaluations/fixtures/golden-v1/search-429.json](../backend/evaluations/fixtures/golden-v1/search-429.json) |
| added | [backend/evaluations/fixtures/golden-v1/search-clean.json](../backend/evaluations/fixtures/golden-v1/search-clean.json) |
| added | [backend/evaluations/fixtures/golden-v1/search-deadline.json](../backend/evaluations/fixtures/golden-v1/search-deadline.json) |
| added | [backend/evaluations/fixtures/golden-v1/search-fewer.json](../backend/evaluations/fixtures/golden-v1/search-fewer.json) |
| added | [backend/evaluations/fixtures/golden-v1/search-irrelevant.json](../backend/evaluations/fixtures/golden-v1/search-irrelevant.json) |
| added | [backend/evaluations/fixtures/golden-v1/web-clean.json](../backend/evaluations/fixtures/golden-v1/web-clean.json) |
| added | [backend/evaluations/fixtures/golden-v1/web-denied-b.json](../backend/evaluations/fixtures/golden-v1/web-denied-b.json) |
| added | [backend/evaluations/fixtures/golden-v1/web-medical-claim.json](../backend/evaluations/fixtures/golden-v1/web-medical-claim.json) |
| added | [backend/evaluations/fixtures/golden-v1/web-missing-fields.json](../backend/evaluations/fixtures/golden-v1/web-missing-fields.json) |
| added | [backend/evaluations/fixtures/golden-v1/web-pack-mismatch.json](../backend/evaluations/fixtures/golden-v1/web-pack-mismatch.json) |
| added | [backend/evaluations/fixtures/golden-v1/web-site-marketplace-conflict.json](../backend/evaluations/fixtures/golden-v1/web-site-marketplace-conflict.json) |
| added | [backend/evaluations/fixtures/golden-v1/web-terminal-news-timeout.json](../backend/evaluations/fixtures/golden-v1/web-terminal-news-timeout.json) |
| modified | [backend/pyproject.toml](../backend/pyproject.toml) |
| added | [backend/tests/test_evaluation_storage_integration.py](../backend/tests/test_evaluation_storage_integration.py) |
| added | [backend/tests/test_evaluations.py](../backend/tests/test_evaluations.py) |
| added | [backend/tools/eval_worker.py](../backend/tools/eval_worker.py) |
| added | [backend/tools/evaluate_golden.py](../backend/tools/evaluate_golden.py) |
| added | [backend/tools/export_eval_trace.py](../backend/tools/export_eval_trace.py) |
| added | [backend/tools/grade_existing_reviews.py](../backend/tools/grade_existing_reviews.py) |
| modified | [backend/uv.lock](../backend/uv.lock) |
| modified | [docs/AGENT_CONTRACTS.md](AGENT_CONTRACTS.md) |
| modified | [docs/ARCHITECTURE.md](ARCHITECTURE.md) |
| modified | [docs/BACKLOG.md](BACKLOG.md) |
| modified | [docs/CI_GATES.md](CI_GATES.md) |
| modified | [docs/EVALUATION_PLAN.md](EVALUATION_PLAN.md) |
| added | [docs/EVALUATION_REPORT.md](EVALUATION_REPORT.md) |
| added | [docs/EVALUATION_SPEC.md](EVALUATION_SPEC.md) |
| added | [docs/EVALUATION_STAGE_FILES.json](EVALUATION_STAGE_FILES.json) |
| modified | [docs/EVAL_PLAN.md](EVAL_PLAN.md) |
| modified | [docs/HARNESS_SPEC.md](HARNESS_SPEC.md) |
| modified | [docs/REQUIREMENTS_TRACEABILITY.md](REQUIREMENTS_TRACEABILITY.md) |
| added | [docs/adr/0014-versioned-evaluations-and-trusted-review.md](adr/0014-versioned-evaluations-and-trusted-review.md) |
| added | [docs/evaluations/evaluation-api-final.xml](evaluations/evaluation-api-final.xml) |
| added | [docs/evaluations/evaluation-api-initial.xml](evaluations/evaluation-api-initial.xml) |
| added | [docs/evaluations/evaluation-graders.xml](evaluations/evaluation-graders.xml) |
| added | [docs/evaluations/evaluation-integration.xml](evaluations/evaluation-integration.xml) |
| added | [docs/evaluations/evaluation-metrics-api.xml](evaluations/evaluation-metrics-api.xml) |
| added | [docs/evaluations/evaluation-unit-initial.xml](evaluations/evaluation-unit-initial.xml) |
| added | [docs/evaluations/evaluation-unit.xml](evaluations/evaluation-unit.xml) |
| added | [docs/evaluations/existing-review-results.json](evaluations/existing-review-results.json) |
| added | [docs/evaluations/golden-baseline-r2-run.json](evaluations/golden-baseline-r2-run.json) |
| added | [docs/evaluations/golden-baseline-r2-run.traces.json](evaluations/golden-baseline-r2-run.traces.json) |
| added | [docs/evaluations/golden-baseline-run.json](evaluations/golden-baseline-run.json) |
| added | [docs/evaluations/golden-baseline-run.traces.json](evaluations/golden-baseline-run.traces.json) |
| added | [docs/evaluations/golden-initial.json](evaluations/golden-initial.json) |
| added | [docs/evaluations/golden-initial.traces.json](evaluations/golden-initial.traces.json) |
| added | [docs/evaluations/golden-regression-initial.json](evaluations/golden-regression-initial.json) |
| added | [docs/evaluations/golden-regression-initial.traces.json](evaluations/golden-regression-initial.traces.json) |
| added | [docs/evaluations/golden-regression.json](evaluations/golden-regression.json) |
| added | [docs/evaluations/golden-regression.traces.json](evaluations/golden-regression.traces.json) |
| added | [docs/evaluations/release-denied.json](evaluations/release-denied.json) |
| added | [docs/evaluations/release-denied.traces.json](evaluations/release-denied.traces.json) |
| modified | [docs/openapi.json](openapi.json) |
<!-- FILES-END -->

Complete before/after hashes: [EVALUATION_STAGE_FILES.json](EVALUATION_STAGE_FILES.json). No Git metadata exists here; this is filesystem evidence, not a claimed git diff. The inventory self hash is omitted to avoid a circular hash. Caches, local Auth secrets/tokens, private packets, environments and build outputs are excluded. Original source documents, prior fixture trees/migrations and previous UI screenshots retain their hashes. There are no deletions.

## Exact local commands

From repository root (PowerShell):

```powershell
./scripts/local-auth.ps1 -Action start
./scripts/local-auth.ps1 -Action prepare
./scripts/verify-sources.ps1
./scripts/verify-design.ps1
node scripts/verify-ui-reference.cjs
./scripts/project.ps1 -Action check
```

From `backend/` (all database traffic is guarded dedicated loopback):

```powershell
$env:UV_CACHE_DIR=Join-Path (Get-Location).Path '../.cache/uv'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:LANGSMITH_TRACING='false'
$env:LANGCHAIN_TRACING_V2='false'
$env:LANGGRAPH_STRICT_MSGPACK='true'
uv lock --offline
./.venv/Scripts/ruff.exe check app tests tools migrations
./.venv/Scripts/mypy.exe
./.venv/Scripts/python.exe -m pytest -q -m 'not integration' -p no:cacheprovider --junitxml=../docs/evaluations/evaluation-unit.xml
./.venv/Scripts/python.exe -m pytest tests/test_evaluations.py -q -p no:cacheprovider --junitxml=../docs/evaluations/evaluation-graders.xml
$env:LATHER_INTEGRATION_CONFIG=Join-Path (Get-Location).Path '../.cache/auth-stage.json'
./.venv/Scripts/python.exe -m pytest -q -m integration -p no:cacheprovider --junitxml=../docs/evaluations/evaluation-integration.xml
./.venv/Scripts/python.exe -m pytest tests/test_evaluation_storage_integration.py -q -x -p no:cacheprovider --junitxml=../docs/evaluations/evaluation-api-final.xml
uv build --offline
./.venv/Scripts/python.exe -m tools.export_openapi

$env:LATHER_ENVIRONMENT='test'
$env:LATHER_CHAOS_ENABLED='true'
$env:LATHER_EVALUATIONS_ENABLED='true'
./.venv/Scripts/python.exe -m tools.evaluate_golden --output ../docs/evaluations/golden-initial.json
# Historical initial baseline, then comparison that caught D04:
./.venv/Scripts/python.exe -m tools.evaluate_golden --output ../docs/evaluations/golden-baseline-run.json --record-proposed-baseline evaluations/baselines/lather-golden-v1.json
./.venv/Scripts/python.exe -m tools.evaluate_golden --baseline evaluations/baselines/lather-golden-v1.json --output ../docs/evaluations/golden-regression.json
# After correction: explicit NEW baseline path; no expectation or old baseline overwrite.
./.venv/Scripts/python.exe -m tools.evaluate_golden --output ../docs/evaluations/golden-baseline-r2-run.json --record-proposed-baseline evaluations/baselines/lather-golden-v1-r2.json
./.venv/Scripts/python.exe -m tools.evaluate_golden --baseline evaluations/baselines/lather-golden-v1-r2.json --output ../docs/evaluations/golden-regression.json
./.venv/Scripts/python.exe -m tools.grade_existing_reviews --evaluation ../docs/evaluations/golden-regression.json --output ../docs/evaluations/existing-review-results.json

# These were actually exercised and REFUSED, not approved live/export operations:
$env:LATHER_TRACE_ENABLED='false'
$env:LATHER_TRACE_EXPORT_APPROVED='false'
./.venv/Scripts/python.exe -m tools.evaluate_golden --live --output ../.cache/live-eval-not-run.json
./.venv/Scripts/python.exe -m tools.export_eval_trace --input ../docs/evaluations/golden-regression.traces.json
./.venv/Scripts/python.exe -m tools.evaluate_golden --case D05 --release-check --output ../docs/evaluations/release-denied.json
```

Baseline recording commands intentionally refuse to overwrite an existing file. Reproduction should compare against the checked-in proposed r2 baseline, or choose a new version path for review. The release-only component check preserves the private full-suite review packet. No paid live runner is implemented/authorized by these commands.

Frontend checks executed by project.ps1 and individually as applicable:

```powershell
npm run lint --prefix frontend
npm run typecheck --prefix frontend
npm test --prefix frontend
npm run build --prefix frontend
```

Cleanup from root:

```powershell
./scripts/local-auth.ps1 -Action stop
```

## Remaining limitations / review boundary

No required source input is missing. Actual trusted claim adjudications, business-owner judgments, real competitor adequacy, live provider/model quality, paid performance/billing and hosted LangSmith/CI behavior remain untested. The curated synthetic sample is not a statistical market/model benchmark. Exact quotes, schema/math success and rule-based Reviewer agreement cannot establish semantic truth or useful strategy. No final provider was selected. The installed wheel alone is not validated as a standalone worker distribution; these commands require the checkout/fixtures.

Remote tracing requires separately approved sanitized export, private credentials, an existing project and an explicit run cap; it was not performed. Real paid evaluation must use the independently reviewed quality-first benchmark with approved profiles and budgets outside CI. No secrets were added to code/logs; no paid APIs, cloud resources, competitor contact, external publishing or deployment occurred. The existing staging site/repository was not accessed or modified. Local services are stopped with volumes retained after verification.

Please review this stage, the proposed r2 baseline and the explicitly unmeasured gates before the next prompt. Do not start B14 or any subsequent stage automatically.
