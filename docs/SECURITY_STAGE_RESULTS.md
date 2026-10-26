# B14 actual security/load stage results

25 October 2026. Local recorded DEMO scope only; no paid model/search call, remote LangSmith transmission, external business action, cloud resource, publishing or deployment. Stop for user review before B15 or any subsequent stage. [Audit and remaining risks](SECURITY_AUDIT.md), [ADR 0015](adr/0015-bounded-ingress-queues-and-research-connections.md), [actual file manifest](SECURITY_STAGE_FILES.json).

## Requirements and actual changes

Read the authoritative original BRD, PRD v1.1 and embedded five-screen HTML using the previously authorized actual filenames. Source SHA checks, five decoded screen checks and verbatim eight-target checks passed. Originals, existing fixture expectations, previous baselines/migrations/screenshots and the separate staging website/repository are preserved. This stage changes no product layout and selects no provider/model.

Implemented bounded API/BFF ingress, non-reflecting validation/OpenAPI error schemas, transport-log redaction, origin hardening, response security headers, NAT64/sensitive-query denial, durable owner queue/lease limits, bounded database pool and shared research lane sessions. Added adversarial tests, concurrent real database/graph tests, a bounded recorded load runner, public dependency/secret-pattern audit tooling and CI wiring. Documentation records retention/deletion/restore policy gaps without inventing durations or deleting history.

## Executed checks and actual output

| Command / check | Actual result |
| --- | --- |
| `scripts/project.ps1 -Action check` | Exit 0: Ruff `All checks passed!`; ESLint zero warnings; mypy `Success: no issues found in 68 source files`; Next typegen/TypeScript pass; **313 offline pytest passed, 74 integration deselected**; **25 Vitest passed**; Python sdist/wheel built offline; Alembic `0006 (head)`; Next production build generated 15 pages. |
| Full dedicated integration pytest | **74 passed, 313 deselected in 175.84s**, exit 0. Includes real Auth/RLS/owner isolation, immutable reports/receipts, approvals, lease crash/restart, source attribution, chaos and migration downgrade/upgrade. [JUnit](security/integration.xml). |
| Final API/security selection after public error-schema update | **23 passed in 9.55s**, exit 0. Real two-user API plus all ingress/log/SSRF/origin tests. [JUnit](security/final-api.xml). |
| New focused concurrency tests | **3 passed in 6.33s**, exit 0 after the pool-starvation fix. Eight starts/two slots, four simultaneous owner claims, expiry/fence/foreign-owner denial, two concurrent fully saved recorded runs. [JUnit](security/security-focused.xml). |
| First B14 full golden run against r2, record proposed r3 | **17/17 cases passed, original failure cohort 5/5**. Exit **1** as required: the sole critical change is the expanded implementation/version fingerprint; no case membership, grades or signatures changed. Old r2 remains unchanged. [Observed result](security/golden-baseline-r3.json). |
| Independent full golden repeat against proposed r3 | **17/17 passed, fixed failure cohort 5/5**, exit 0; comparable fingerprint and **zero critical regression**. Baseline still `pending_user_review`. [Observed result](security/golden-regression.json), [sanitized local traces](security/golden-regression.traces.json). |
| Public OSV locked dependency audit | Exit 0: **557/557 distinct package versions queried**, **0 affected package versions returned**, **0 query errors**. Public package/version metadata only; lock hashes/date preserved. [Actual result](security/dependency-audit.json). This is not a vulnerability-free guarantee or OS/container/action audit. |
| Source/embedded UI/design checks | Exit 0: three original source hashes; BRD FR-01..09 readability; five decoded HTML templates; all eight exact BRD target strings; seven required design documents and catalog IDs. These are structural checks, not a visual-quality or business-acceptance score. |
| OpenAPI export | Exit 0: `Exported OpenAPI with 38 paths; no settings or credentials included`; generic 422/limit errors now describe the actual non-reflecting response. |
| Explicit-path chaos CLI rerun | Exit 0: **9/9 isolated recorded cases passed**, final approval retained; the new `--output` path is used and documented. No original fixture was edited. [Actual result](security/chaos-regression.json). |

Browser run: **35 passed, 1 intentionally skipped in 1.1 minutes**, exit 0, desktop/mobile. The existing duplicate mobile final-approval test is skipped; the desktop approval/export scenario runs. This includes real persisted sign-in/save/reload, keyboard/reduced-motion/evidence/history/chaos and new served security headers/cross-origin refusal. Current captures are in ignored `.cache/current-ui-regression`, `.cache/current-history-regression` and `.cache/current-chaos-regression`; old reference/stage PNG bytes remain unchanged. Playwright emitted only the non-failing NO_COLOR/FORCE_COLOR environment warning. No screenshot baseline was updated.

Final file-integrity check: **156 pre-existing protected files unchanged**, including original sources, old fixture/baseline/migration bytes, prior golden artifacts and old PNGs. The final source-only pattern scan is saved in [source-scan.json](security/source-scan.json); it makes no new advisory claim (`not_queried`). Local test services stopped successfully, and no listeners remained on 3140/8140/57421/57422. Ignored local DEMO data/configuration and fresh regression screenshots remain available; credentials were not printed or committed.

## Load measurements

[Machine-readable observations](security/load-results.json). Dedicated local Windows/Python 3.13.5/Postgres, four fresh recorded SC01/R21 runs per condition, three lanes/run, 10ms artificial delay per web dispatch, real owner RLS/checkpoints/leases/heartbeat/independent rule review/save, synthetic owner approvals through real gates. No human think-time, live tools or model inference.

| Worker threads | Completed / submitted | Wall seconds | Runs/second | Run p50 ms | Run p95 ms (nearest-rank max of four) | Peak active runner tasks |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 4/4 | 11.153 | 0.359 | 2814.72 | 2971.55 | 1 |
| 2 | 4/4 | 6.853 | 0.584 | 3187.27 | 3638.68 | 2 |
| 4 | 4/4 | 5.884 | 0.680 | 5176.61 | 5882.28 | 4 |

Each condition persisted 12 completed research lanes, four approved reports, 40 recorded tool dispatches and 44 events per run. Total **12/12 completed**, **36 lanes**, **120 recorded dispatches**, **zero actual provider calls/tokens/spend**. Throughput increased in this small sample while per-run latency increased under contention. No sustained-load, statistical tail-latency, fleet/tenant-fairness or million-user claim. `queue_start_wait_ms` in the JSON measures runner-thread dispatch wait after all jobs are seeded; it is not durable database queue age or human approval delay.

Proposed defaults: 65,536-byte bodies; backend 600 requests/minute/socket peer with at most 4,096 live hashed buckets; frontend 30 login attempts/minute/process; 128 outstanding nonterminal runs/owner including approval waits; four active unexpired leases/owner; three long-held lane sessions/shared engine; five pooled plus five overflow connections with ten-second pool wait. These are engineering defaults for review, not exact BRD acceptance targets or distributed service limits.

## Failures found and disposition

The initial full integration run was **73 passed / 1 failed in 207.79s**. SEC12 exhausted the test pool (size one plus five overflow): long-held advisory-lock sessions occupied the connections needed for research transactions. [Initial failing JUnit](security/integration-initial.xml) is retained. The fix bounds session-holding research lanes across runs sharing an engine and leaves transaction/heartbeat capacity; focused and full reruns passed. The successful benchmark uses explicitly bounded 5+5 connections. No assertion was weakened or real failure converted to an empty research result.

Two test retry invocations were interrupted after a working-directory mistake could run database tests concurrently. The restricted process lookup first reported access denied; an authorized local process-control retry stopped those pytest processes. Fresh dedicated DEMO identities were prepared, and the full suite was run once serially from `backend/`. The interrupted attempts are not passing runs or measured test scores; no file was written to the erroneous outside-workspace report location.

The r2 comparison failure is intentional version drift from the security changes and expanded fingerprint, not a hidden behavioral pass. Proposed r3 and its independent successful comparison are new artifacts; no previous baseline or recorded expectation was overwritten or automatically approved.

The existing `tools.chaos_demo` command refreshed `docs/CHAOS_EVAL_RESULTS.json` while seeding the browser fixtures. This is explicitly recorded as a changed B14 regression artifact, with the prior SHA in the file manifest and a measurement-stage note in the JSON; it is not presented as the original B12 execution. Prior bytes of that result file were not backed up. Its nine current actual cases all passed with final approval retained. Original sources, fixture inputs, baselines, migrations and screenshot artifacts were preserved. The CLI now has an explicit `--output` and defaults to ignored cache so future reruns preserve that artifact; CI writes a new security-stage path. A separate current execution is saved to `security/chaos-regression.json`.

## Original BRD acceptance and limits

| Gate | Exact BRD target | Current scoped evidence / remaining limitation |
| --- | --- | --- |
| A01 | Three relevant competitors identified when sufficient evidence exists | Recorded positive/empty/insufficient/irrelevant controls pass. Real-market relevance/model quality untested. |
| A02 | At least 90% of material factual claims linked to supporting sources | Source/claim links, quote integrity and independent review controls regressed. Genuine support remains unmeasured; citation presence/quote match does not prove the source entails the assertion. |
| A03 | Required comparison fields populated or explicitly marked unavailable | Recorded field/null/pack/weight/conflict tests pass. Live extraction reliability untested. |
| A04 | At least 4 out of 5 test reports rated useful by the business owner | **0/5 actual owner ratings received**; useful count unmeasured. No synthetic rating substituted. |
| A05 | At least 4 out of 5 designed failure tests handled correctly | Fixed D04/D05/D06/D10/D12 cohort **5/5** in both B14 recorded executions; critical security/recovery cases also must pass. |
| A06 | Interrupted research run resumes without losing completed results | Real process restart, preserved saved lanes/source hashes, pending approval and stale-fence negatives pass in integration and D13. Production infrastructure not tested. |
| A07 | No knowingly fabricated facts in the final report | Controlled invention/unsupported-claim negatives pass; all synthetic content labeled DEMO. Does not establish factual accuracy for live research. |
| A08 | Final report presented for review before any external business action | Durable owner/hash/version gates and gated save/export pass. No external business tools enabled or action performed. |

Release remains blocked by real-source support, five owner ratings, the provider-neutral model benchmark/selection, proposed baseline review, business retention/deletion and backup/restore objectives, shared account/edge/fleet limits, deployment trust/proxy/egress controls and production security/load validation. Dependencies: dated OSV matches only; no OS/container/browser/action supply-chain audit. Logs: future/custom/platform/database logs and arbitrary formatter extras need separate review. Browser policy restricts framing/base/object use; a nonce-based full script CSP is not implemented. Hosted CI has not been run. These gaps do not block completing this local audit, but prevent a production-readiness claim.

## Exact local commands

From `E:\HandmadeSoap-MarketResearch`, PowerShell; installed locked packages and cached Docker images are reused. The prepare command creates only disposable local DEMO Auth identities, rotates a local runtime password and stores credentials in ignored `.cache/auth-stage.json`; never print that file. Integration rollback tests must run serially before preparing browser/golden fixtures.

```powershell
powershell -NoProfile -File scripts/local-auth.ps1 -Action start
powershell -NoProfile -File scripts/local-auth.ps1 -Action prepare
powershell -NoProfile -File scripts/project.ps1 -Action check
powershell -NoProfile -File scripts/verify-sources.ps1
node scripts/verify-ui-reference.cjs
powershell -NoProfile -File scripts/verify-design.ps1

Set-Location backend
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:LATHER_INTEGRATION_CONFIG=Join-Path (Get-Location).Path '../.cache/auth-stage.json'
$env:LANGSMITH_TRACING='false'
$env:LANGCHAIN_TRACING_V2='false'
$env:LANGGRAPH_STRICT_MSGPACK='true'
.venv/Scripts/python.exe -m pytest -q -m integration -p no:cacheprovider --junitxml=../docs/security/integration.xml
.venv/Scripts/python.exe -m pytest tests/test_security_storage_integration.py -q -p no:cacheprovider --junitxml=../docs/security/security-focused.xml
.venv/Scripts/python.exe -m pytest tests/test_storage_integration.py::test_real_supabase_auth_and_cross_user_api tests/test_security.py -q -p no:cacheprovider --junitxml=../docs/security/final-api.xml
.venv/Scripts/python.exe -m tools.security_audit --online --output ../docs/security/dependency-audit.json
.venv/Scripts/python.exe -m tools.security_load --output ../docs/security/load-results.json
.venv/Scripts/python.exe -m tools.export_openapi

$env:LATHER_ENVIRONMENT='test'
$env:LATHER_CHAOS_ENABLED='true'
$env:LATHER_EVALUATIONS_ENABLED='true'
# First recording only: r3 now exists; rerunning this command refuses overwrite.
# The original execution exited 1 for the required r2 version-drift check.
.venv/Scripts/python.exe -m tools.evaluate_golden --baseline evaluations/baselines/lather-golden-v1-r2.json --record-proposed-baseline evaluations/baselines/lather-golden-v1-r3.json --output ../docs/security/golden-baseline-r3.json
.venv/Scripts/python.exe -m tools.evaluate_golden --baseline evaluations/baselines/lather-golden-v1-r3.json --output ../docs/security/golden-regression.json

.venv/Scripts/python.exe -m tools.prepare_report_ui
.venv/Scripts/python.exe -m tools.prepare_history_ui
.venv/Scripts/python.exe -m tools.chaos_demo --output ../docs/security/chaos-regression.json
Set-Location ../frontend
$env:LATHER_UI_INTEGRATION='1'
$env:LATHER_UI_CHAOS='1'
npm run test:e2e
Set-Location ..
Set-Location backend
.venv/Scripts/python.exe -m tools.security_audit --output ../docs/security/source-scan.json
Set-Location ..
powershell -NoProfile -File scripts/local-auth.ps1 -Action stop
```

The public OSV command is the only non-loopback audit operation; it sends public dependency metadata, not repository code or research. No live/paid evaluation is enabled by any command above. Baselines remain pending review. Please review this stage before sending the next prompt.

## Actual files changed

Compared with the pre-stage SHA snapshot (not a Git status claim). Hashes and before/after status are in SECURITY_STAGE_FILES.json. Ignored environments, credentials, caches/builds and current screenshots are excluded. The changed historical chaos output is explicitly identified above.

| File | Status |
| --- | --- |
| `.github/workflows/ci.yml` | modified |
| `backend/app/auth.py` | modified |
| `backend/app/config.py` | modified |
| `backend/app/db.py` | modified |
| `backend/app/evaluations/baseline.py` | modified |
| `backend/app/harness/lease.py` | modified |
| `backend/app/harness/research_store.py` | modified |
| `backend/app/harness/urls.py` | modified |
| `backend/app/harness/web_policy.py` | modified |
| `backend/app/main.py` | modified |
| `backend/app/queue_policy.py` | added |
| `backend/app/repository.py` | modified |
| `backend/app/security.py` | added |
| `backend/evaluations/baselines/lather-golden-v1-r3.json` | added |
| `backend/tests/test_security.py` | added |
| `backend/tests/test_security_audit.py` | added |
| `backend/tests/test_security_storage_integration.py` | added |
| `backend/tools/chaos_demo.py` | modified |
| `backend/tools/security_audit.py` | added |
| `backend/tools/security_load.py` | added |
| `docs/ARCHITECTURE.md` | modified |
| `docs/BACKLOG.md` | modified |
| `docs/CHAOS_EVAL_RESULTS.json` | modified |
| `docs/CI_GATES.md` | modified |
| `docs/EVALUATION_REPORT.md` | modified |
| `docs/REQUIREMENTS_TRACEABILITY.md` | modified |
| `docs/SECURITY_AUDIT.md` | added |
| `docs/SECURITY_STAGE_FILES.json` | added |
| `docs/SECURITY_STAGE_RESULTS.md` | added |
| `docs/adr/0015-bounded-ingress-queues-and-research-connections.md` | added |
| `docs/openapi.json` | modified |
| `docs/security/chaos-regression.json` | added |
| `docs/security/dependency-audit.json` | added |
| `docs/security/final-api.xml` | added |
| `docs/security/golden-baseline-r3.json` | added |
| `docs/security/golden-baseline-r3.traces.json` | added |
| `docs/security/golden-regression.json` | added |
| `docs/security/golden-regression.traces.json` | added |
| `docs/security/integration-initial.xml` | added |
| `docs/security/integration.xml` | added |
| `docs/security/load-results.json` | added |
| `docs/security/security-focused.xml` | added |
| `docs/security/source-scan.json` | added |
| `frontend/next.config.ts` | modified |
| `frontend/src/app/api/briefs/route.ts` | modified |
| `frontend/src/app/api/session/route.ts` | modified |
| `frontend/src/lib/ingress.ts` | added |
| `frontend/src/lib/proxy.ts` | modified |
| `frontend/src/lib/server-api.ts` | modified |
| `frontend/tests/e2e/chaos.spec.ts` | modified |
| `frontend/tests/e2e/security.spec.ts` | added |
| `frontend/tests/security.test.ts` | added |
