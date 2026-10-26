# Lather Lens requirements traceability

## Current B14 security/load evidence

| Requirement / gate | Scoped coverage | Test IDs / evidence |
| --- | --- | --- |
| FR-01 / S01 / S04 | Auth owner binding, strict private inputs, bounded streamed bodies, no raw validation echo, HTTPS origin restrictions | SEC01/02/07, SEC-BFF01/02/04; existing real Auth/RLS suite |
| FR-02/03 / S02 / A07 | Public destination/DNS/peer/redirect/access controls; sensitive URL key and NAT64 denial | SEC05/06; existing search/research negative fixtures |
| FR-08 / A08 / S01/S03 | Same-origin BFF, closed direct CORS, immutable owner/hash/version approvals/exports, no production chaos/eval injection | SEC01; existing BFF/report/evaluation/workflow suites and browser approval cases |
| FR-09 / A06 / T08 / P01 | Durable bounded admission/claim, idempotency at capacity, lease expiry/fences, concurrent real graph/checkpoint saves | SEC10/11/12; security/load-results.json; golden D13/D14/D17 |
| PRD section 12 / S04 | Log canaries, pattern-only source scan, exact lock metadata and incomplete advisory rejection | SEC03/04/08/09, SEC-BFF03; security/dependency-audit.json |
| A01..A08 | Original target strings remain unchanged below. Recorded regression, owner/usefulness and genuine-support evidence remain separately reported. | SECURITY_STAGE_RESULTS.md; EVALUATION_REPORT.md |

SECURITY_AUDIT.md/ADR 0015 identify fixes and remaining retention/shared-limit/hosting risks. B14 does not establish semantic support, owner usefulness, provider quality or production capacity. No subsequent stage is started. Older stage entries below are historical.

## Current B13 evaluation evidence

| Requirement / target | Implemented measurement boundary | Cases / tests |
| --- | --- | --- |
| FR-01/02 / relevance, no invention | Versioned brief/search fixtures, typed discovery, source-backed identities and explicit shortfall | D01..D03; EG01/EG04 |
| FR-03/04 / availability and arithmetic | Restricted source, two dated prices, missing weight/ingredients, variant/pack mismatch, independent Decimal expectations | D06..D09; EG03 |
| FR-05/06/07 / evidence review | Typed reports, premise-linked hypotheses, attributed medical claims, actual unsupported assertion rejection/correction | D01/D10..D12; existing analysis suite |
| FR-08 / human gates and trust | Durable request/decision bindings, foreign/stale approval refusal; server-granted hash-bound review/rating receipts | D14/D17; EG04/EG09..EG12; ER01..ER05 |
| FR-09 / recovery and history | Terminal timeout preserves two lanes; real process exit/resume/pending approvals/stale fence; budget/cancel; dated gap comparison | D04/D13/D15/D16; ER06 |
| A02/A04 / unmeasured human quality | Separate provenance/presence and trusted support; fixed five-owner-report cohort; no invented judgments | EG09..EG12, ER01..ER04; EVALUATION_REPORT.md |
| A05/A06/A07/A08 / controlled gates | Fixed original failure cohort, strict critical regression checks, recovery, no known injected final fact and approval enforcement | D04/D05/D06/D10/D12, D13/D14/D17 |

EVALUATION_SPEC.md/ADR 0014 describe contracts, scope and source-requirement resolutions. EVALUATION_REPORT.md records actual outputs, baseline defects caught and remaining untested areas. Initial proposed baselines await user review; semantic/owner/live-model acceptance remains unmeasured. The exact A01..A08 BRD targets below are unchanged. No B14 or subsequent stage has started. Older stage notes below are historical.

## Current B12 recorded chaos/recovery evidence

| Requirement / scenario | Scoped implementation | Test IDs |
| --- | --- | --- |
| FR-02 / D04/D05 | Exact recorded search retries, cached-failure resume, no candidate invention on bounded empty discovery | CP01/CP02/CP05, CI01, existing Scout retry/deadline/budget cases |
| FR-03/04 / D06/D08/D09 | Inaccessible source status, preserved contradictory prices, raw price with null missing weight | CI01, UI-CHAOS-LIMITS, existing retrieval/normalization cases |
| FR-05/07 / D10/D12 | Model fixture JSON validation/one repair, independent arithmetic rejection and one immutable targeted revision; terminal invalid/budget stop | CI01/CI05, UI-C01/UI-CHAOS-RECOVERY |
| FR-08 / A08 / S01/S03 | Both real review gates retained; test API owner/same-origin/key and production config/API/worker/model denial | CP03/CP06/CP07, CI03/CI04, BFF-C01/C02, UI-CHAOS-GATE |
| FR-09 / A06 / D13/T08 | Actual dedicated process exit after committed lane, lease reclaim, exact saved task/source hashes reused, remaining lanes only | CI02, CHAOS_EVAL_RESULTS.json, UI-CHAOS-RECOVERY |
| FR-09 / A06 / D13 | Pending writes wait outside locks for their durable parent; missing parent stops without placeholder/orphan | CI06/CI07 |
| UI03 / FR-09 | Reference chaos column, server capabilities, separate DEMO plans, persisted aggregates/reload, honest queued/partial/error states | UI-CHAOS-GATE/QUEUE/RECOVERY/LIMITS |

CHAOS_SPEC.md/ADR 0013 explain immutable single-scenario versus prototype toggle behavior and event/version boundaries. CHAOS_STAGE_RESULTS.md records actual commands/outputs. The nine B12 scenarios do not replace the predeclared D04/D05/D06/D10/D12 A05 cohort. Genuine semantic support/owner usefulness remain unmeasured; synthetic model projections select no provider or model. All exact BRD acceptance strings below are unchanged. B13 and later stages have not started. Older stage notes below are historical.

## Current B11 historical-version evidence

| Requirement / scenario | Implemented scoped coverage | Tests |
| --- | --- | --- |
| FR-09 / D15 / UI05 | Unique immutable report revisions, exact hash/version reads, two approved chronological run snapshots and stable identities | HV01/HV14..HV18, HI01/HI04, UI-HISTORY-DIFF |
| FR-03/04 / T03/T04 | Dated source excerpts/status/hash, matched SKU/variant/currency/pack/weight for price changes; raw conflicts retained | HV02/HV04..HV06/HV18/HV19, HI01, BFF-H01..HV03 |
| FR-07 / A03/A07 | New-to-sample versus launch, explicit source-reported discontinued versus out-of-stock, missing/denied website and stale evidence | HV03/HV07..HV13/HV20..HV22, HI02/HI03, UI-HISTORY-GAP |
| FR-08 / A08 / S01 | Approved saved versions only; owner isolation; no draft/export bypass; runtime update/delete denial; invalid presentation cleared | HV16, HI01/HI04, UI-HISTORY-DIFF; prior approval/export suite |
| FR-09 / A06 | Reading a new run/diff does not alter previous snapshots, hashes or sources; existing process recovery regressed separately | HV17, HI01/HI03, full local integration suite |

New code: backend/app/history.py/history_types.py; exact-version API/workspace and source availability extraction; frontend history/version picker/BFF and exact report-version links. HISTORY_STAGE_RESULTS.md gives actual outputs and commands; HISTORY_SPEC.md/ADR 0012 explain conservative source-requirement resolutions and identity limits. All exact BRD targets below remain unchanged. No 90% genuine-support, owner usefulness, live-market or five-failure acceptance result is implied by history counts/tests. Older stage entries below are historical.

## Current B10 persisted screen/report evidence

| Requirement | Implemented scope | Actual test IDs |
| --- | --- | --- |
| FR-01 | Existing brief persistence plus explicit zero-paid-cost recorded-run queue | existing UI-API; UI-SAVE-ERROR |
| FR-02/03 | Persisted shortlist/rationale/source excerpts and dated comparison evidence | UI-PERSIST-VIS-shortlist; UI-PERSIST-EVIDENCE; RI01 |
| FR-04 | Eligible per-100g observations, separate currency scales, explicit null/hatch/zero | R02/R04/R08; UI-R01; UI-PERSIST-VIS-report; existing B09 math suite |
| FR-05/06 | Persisted comparisons, issue flags, premise-based hypotheses/assumptions/next steps | R06/R08; UI-PERSIST-VIS-report; B09 suite |
| FR-07 / T07 / UI04 | Frozen cover/scope, source ring, comparison, categorical 2x2, price chart, opportunities/evidence, structured HTML/CSV | R01..R09; UI-PERSIST-VIS-report; UI-PERSIST-EVIDENCE |
| FR-08 / A08 / D14 / S01 | Owner/hash/version/receipt-bound final approval and completed-save export; immutable runtime reports | RI01..RI03; BFF-R01..R03; UI-PERSIST-APPROVAL |
| FR-09 / UI03/UI05 | Real event/checkpoint/usage/lane projections and dated owner history metadata; semantic change detection remains B11 | RI01; UI-PERSIST-VIS-live/history; existing recovery/RLS/rollback suite |

A02: denominator includes all non-null fact/source_claim findings, including uncited assertions; quote integrity is diagnostic, genuine support stays null. A03: required comparison fields populated or explicitly unavailable; no invented chart inputs. A07: attribution and warnings retained, not proof of real-world factual truth. All eight exact BRD metrics below remain unchanged and are restated with current scoped status in REPORT_STAGE_RESULTS.md. No owner ratings/model benchmark/full business release claimed. Older stage notes below are historical snapshots.

## Current B09 normalization, analysis and review evidence

FR-04 now requires same-SKU/variant/offer/weight evidence before deterministic per-100g arithmetic; database generated values also require a verified eligibility record (0006). FR-05 compares products/ingredients/prices/positioning/audience/channels/packaging/feedback/launches through scoped findings and explicit unavailable fields. FR-06 conditionally emits up to five grounded rule-based hypotheses with rationale, benefit, assumptions and next steps; fewer than three has an explicit shortfall reason. Facts, attributed source claims, interpretations and hypotheses are separate typed kinds. No final model was selected.

Independent Reviewer reconstructs raw source observations, recomputes arithmetic, rejects wrong-scope/intact-but-irrelevant citations, checks medical/certification attribution, source/publication freshness, missing fields and conflicts. Targeted bounded correction preserves unaffected rows/sections and immutable versions; blockers or exhausted revisions stop unresolved before final approval. Review receipts are persisted and exposed on the protected report endpoint. Actual evidence/commands: ANALYSIS_STAGE_RESULTS.md; boundaries: ANALYSIS_SPEC.md.

| Requirement / scenario | Tests and scoped coverage |
| --- | --- |
| FR-04, T04, D08/D09 | test_analysis.py golden AN01..AN06/AN17/AN18; same SKU, per-bar pack, missing/ambiguous identity/weight, no FX, exact rounding and zero versus missing; test_an05 scope/tamper controls; AI02 and existing DB arithmetic/retrieval tests |
| FR-05, T05, D07 | Typed side-by-side observations, known/unavailable fields, preserved contradictory values; golden AN07; test_an06 omissions; existing contradictory-source DB tests |
| FR-06, T06 | Golden AN11 produces five grounded conditional hypotheses; AN08/AN09 return zero/insufficiency when unavailable; test_an08 hypothesis/assumption/next-step shape |
| FR-07/FR-09 review, D10..D12 | AN10/AN12..AN16 medical attribution, malformed output, genuine-versus-present citation control, input binding and bounded failure; AI01 targeted revision/exhaustion and AI04 schema-unresolved trajectory |
| FR-08/09, T08, S01 | AI01/AI03 exact report/review binding, immutable/idempotent receipts, owner API isolation, no extra retrieval; existing process/lease/approval suite regressed |
| A02/A03/A07 controls | Citation presence and quote integrity are diagnostics only; genuine support stays null/not_adjudicated. Required fields have known/unavailable records; clinical claims stay attributed/flagged. No full real-report acceptance result is claimed. |

All eight exact BRD targets below are unchanged. The rule baseline is not a model benchmark, the designed five-failure cohort is not replaced by unit counts, and five real owner ratings remain absent.

# Current durable workflow evidence

B08 adds typed conditional LangGraph, actual owner-RLS Postgres checkpoint/pending-write storage, worker lease/heartbeat/generation fencing, cancellation/idempotent resume, both durable review interrupts, conditional bounded revision and immutable approved-save reconciliation. JSON polling and SSE replay the same persisted sequence. Actual evidence and exact commands: [WORKFLOW_STAGE_RESULTS.md](WORKFLOW_STAGE_RESULTS.md); design/limitations: [WORKFLOW_SPEC.md](WORKFLOW_SPEC.md).

| Requirement / scenario | Current scoped evidence | Tests |
| --- | --- | --- |
| FR-08, D14/D17, A08 | Exact persisted approval required; managed report approval cannot itself complete/save; rejected/request_changes decisions stop; duplicates idempotent | W01/W02, W06, W08/W10/W12/W16; existing owner/hash/version integration tests |
| FR-09, D13, T08, A06 | Real worker process lost during parallel research; committed lane unchanged; fresh process reclaims expired generation and fetches only unfinished lanes; both pending gates preserved | W06/W07/W14 |
| FR-09, D16/D17 | Cancellation invalidates lease/generation and pending requests; no post-cancel transport dispatch; resume keeps deadline/context; shared existing harness budgets | W07/W08/W15 and prior budget tests |
| FR-09, S01 | New checkpoint tables FORCE RLS/owner FKs; stream/control cross-owner denial; migration rollback/reapply | W09/W13/W17, expanded all-table RLS/spoofing tests |
| FR-04/05/07, D12 | Normalization check and bounded mechanical review/rebuild with immutable versions; orchestration only | W01/W04/W11 |
| UI03 transport boundary | Persisted cursor projection, Last-Event-ID, heartbeat/disconnect/storage-error behavior | W05/W09/W18; real Live Run UI remains DEMO |

A06 has controlled local DEMO process-restart evidence. A08 has controlled local final-gate evidence with business-action tools absent. A01/A02/A03/A04/A05/A07 and real research/report acceptance remain unmeasured as complete application gates; the selected five-case failure cohort is not replaced by workflow test counts. Citation presence/quote checks do not count as semantic support. All eight exact BRD targets below remain unchanged.

## Current Researcher/evidence stage

FR-03 now has independent recorded public page/news retrieval and attributable product/SKU/variant/price/weight/pack/ingredients/marketing/channels/reviews/news extraction. FR-04 has explicit same-item pack basis and null ambiguous totals; FR-05 preserves source-level contradictions without analysis; FR-08 checks actual durable shortlist approval; FR-09 persists source documents, typed lane artifacts, claims/quote relationships and restart reuse. New tests: test_research.py and test_research_storage_integration.py; R01..R24 outcomes and exact commands are in RESEARCH_STAGE_RESULTS.md. A02 provenance, A03 null/unknown handling and A05/A06 retrieval/reload conditions have scoped evidence only. No actual report, independent support adjudication, owner-usefulness rating or final approval gate outcome is claimed; all exact A01..A08 targets below remain unchanged.

## Current gateway/Scout stage evidence

FR-02 discovery now has a harness-only Tavily wire adapter with recorded transport, deterministic five-dimension relevance, candidate rationale/provenance, deduplication and up-to-three/fewer/zero decisions. FR-03 is covered only for search-snippet source records; FR-08 has a real owner/version/hash-bound durable shortlist pause; FR-09 has durable discovery attempts, results, usage/events/checkpoint and tested process restart. Tests: test_scout.py (SC01..SC14 plus policy/replay/URL/budget negatives), test_scout_storage_integration.py (local RLS, atomic budgets, durable decisions/restart), and existing storage rollback/isolation tests. See SCOUT_STAGE_RESULTS.md for actual outputs and SCOUT_SPEC.md for limits. A01/A07 have controlled discovery-only evidence, A05/A06 partial search/restart evidence and A08 shortlist-only evidence; A02/A03/A04/full final-report gates remain unmeasured. The eight exact target strings below are unchanged.

## Current UI stage evidence

Five reference compositions now exist at `/`, `/shortlist`, `/live`, `/report`, `/history`. See UI_FIDELITY.md and UI_STAGE_RESULTS.md. Only Brief uses authenticated API persistence; other data/actions are DEMO. Earlier planned mappings remain requirements, not completed business workflows.

| Requirement / UI ID | Stage coverage | Actual test IDs |
| --- | --- | --- |
| FR-01 / UI01 | Required intake, clarification, goal/segment, own-bar preferences, authenticated save/read/retry | UI-API, UI-KEY, UI-SAVE-ERROR, UI-SAVE-LOADING; backend preference validation |
| FR-02, FR-08 / UI02 | DEMO rationale/fit/evidence, selection limit and illustrative approval | UI-INTERACT, UI-KEY, UI-VIS-shortlist |
| FR-03, FR-09 / UI03 | DEMO parallel activity, blocked/missing labels, local controls; no recovery claim | UI-INTERACT, UI-VIS-live |
| FR-04..08 / UI04 | DEMO comparison, weights/conflicts, marketing flag, hypotheses/limits/sources and support distinction | UI-INTERACT, UI-VIS-report |
| FR-09 / UI05 | DEMO timeline/before-after, not-rechecked/discontinuation uncertainty | UI-INTERACT, UI-VIS-history |
| UI06 | Responsive, keyboard, skip/focus/Escape, reduced motion, loading/empty/error and private server boundary | UI-VIS in two projects, UI-RESP, UI-KEY, UI-STATE, BFF-01..04 |

All eight exact A01..A08 gates below remain unchanged and unevaluated as research acceptance. Brief persistence is not agent recovery, DEMO coverage is not source support, and synthetic reports are not owner-usefulness samples.

Requirements baseline, 25 October 2026. Planned module mappings below are supplemented by stage status appendices identifying actual harness, scaffold and Auth/storage implementations and tests. Full research workflows and business acceptance remain unevaluated. Paths are relative to the repository root. The user's screenshot identifies the longer-named original BRD, HTML and PRD as inputs; the short paths in the request are aliases, not additional files. Original sources remain unchanged.

| BRD requirement | Planned modules | Planned API | Planned verification |
| --- | --- | --- | --- |
| FR-01 Brief and clarification | backend/app/domain/briefs.py; frontend/app/brief | POST/GET /api/briefs | Missing essentials request clarification before search; validated form and ownership |
| FR-02 Evidence-backed discovery | backend/app/agents/scout.py; harness/gateway.py; adapters/tavily.py | POST /api/runs; POST /api/runs/{id}/shortlist-decision | Clean three; fewer than three; irrelevant results; no invented IDs; approval gate |
| FR-03 Public data collection | agents/researcher.py; domain/evidence.py; adapters/retrieval.py | GET /api/runs/{id}; GET /api/runs/{id}/events | Source URL/date/hash/excerpt; inaccessible pages; missing ingredients; access restrictions |
| FR-04 Normalization | domain/normalization.py; harness/contracts.py | GET /api/runs/{id}/report | Decimal arithmetic; missing weight; mismatched SKU/pack; facts versus interpretations |
| FR-05 Comparison | agents/analyst.py; domain/comparison.py | GET /api/runs/{id}/report | Contradictions preserved; evidence support; comparison fields explicit |
| FR-06 Opportunities | agents/analyst.py; agents/reviewer.py | GET /api/runs/{id}/report | Supported hypotheses with rationale, benefit, assumptions and next step; insufficiency flagged |
| FR-07 Structured report | domain/reports.py; frontend/app/reports | GET /api/runs/{id}/report; GET /api/runs/{id}/export | Required sections; citations; stale/missing/conflicting labels; measured coverage |
| FR-08 Human review | harness/policy.py; workflow/graph.py; services/approvals.py | POST /api/runs/{id}/shortlist-decision; POST /api/runs/{id}/report-decision | Reject bypass, wrong owner and stale version; pending approval survives restart; external writes denied |
| FR-09 State and history | harness/state.py; worker.py; persistence/; supabase/migrations/; frontend/app/history | GET /api/history; GET /api/history/diff; POST /api/runs/{id}/cancel | Checkpoint recovery; leases/idempotency; completed work retained; historical uncertainty |

## Cross-cutting requirements

| Requirement | Planned ownership | Verification evidence required |
| --- | --- | --- |
| Conditional multi-agent control | workflow/graph.py, LangGraph worker | Executed trajectory with sufficiency, retries, rejection and approval branches |
| Security and public access | harness/policy.py, gateway.py, auth and RLS | Owner isolation; SSRF/redirect protections; log redaction; no access bypass |
| Cost and observability | RunContext, usage records, opt-in LangSmith adapter | Limits enforced before calls; sanitized telemetry; versions and actual usage |
| Durable storage | Supabase Postgres, Alembic, Postgres checkpointer | Migration checks; ownership/RLS; restart and lease recovery |
| UI fidelity and usability | Next.js TypeScript, Tailwind, five reference screens | Rendered comparisons; keyboard/mobile/reduced-motion checks; real empty/error states |
| Model configurability | adapters/models.py | Provider-independent validated outputs; offline default; bounded malformed-output repair |
| Failure handling | harness execution and isolated fault injector | Tests and actual outcomes defined in EVALUATION_PLAN.md |

## Evidence policy

Replace planned paths with implemented links as stages complete. Each test result must include the exact command, dataset/version, actual outcome and unresolved limitation. Screenshots, traces and sample reports must be labeled as real or DEMO. No application acceptance target has been measured in Stage 0.

## Functional test and demonstration mapping

The D/T/S/UI IDs below specify future workflow/integration tests. Stage 1 V-series validation tests are distinct and do not establish these application outcomes. Source authority: BRD sections 5 and 9–16, five decoded HTML screens and interaction logic, PRD v1.1 sections 1–13. Proposed demonstrations DEMO-01 (normal run), DEMO-02 (failure/recovery) and DEMO-03 (history) do not yet exist.

| Requirement | Required details beyond module mapping | Test IDs | Planned demonstration |
| --- | --- | --- | --- |
| FR-01 | Category, geography, customer, objective, known competitors; structured brief; material missing essentials trigger clarification | T01, UI01, S01 | DEMO-01 intake and clarification |
| FR-02 | Rank product/customer/geography/price/channel; three when evidence permits; rationale and supporting evidence; no invented quota fill | D01–D03, T02, UI02 | DEMO-01 shortlist; DEMO-02 insufficiency |
| FR-03 | Brand/product names, types/variants, prices/weights, ingredients, claims, positioning/audience, channels/packaging, public feedback, launches/news; dated sources; unavailable explicit | D06, D08, D11, T03, S02 | DEMO-01 evidence; DEMO-02 access failure |
| FR-04 | Currency, weight and pack quantity; comparable price/100 g; facts/interpretations/hypotheses distinct | D07–D10, T04 | DEMO-01 normalization |
| FR-05 | Assortment/ingredients, price, identity/messaging, segments, claims, channels, feedback, strengths/weaknesses/gaps; insufficient/contradictory evidence | D07, D11, T05 | DEMO-01 comparison |
| FR-06 | Three to five hypotheses with evidence, rationale, potential benefit, assumptions and next step; fewer is flagged insufficiency, not count-target success | T06, D12 | DEMO-01 opportunities |
| FR-07 | Executive summary, scope/methodology, shortlist/rationale, comparison table, prices/products, positioning/messaging, feedback where available, opportunities, gaps/limits, dated sources; stale/missing/conflicts | T07, D07, D08, D15, UI04 | DEMO-01 report |
| FR-08 | Shortlist review when needed; final review; no autonomous publishing/contact/accounts/purchases/commitments; proposed always-on shortlist gate | D14, S01, S03, UI02, UI04 | DEMO-01 gates; DEMO-02 bypass denial |
| FR-09 | Persist tasks, tool results, sources, failures, validations, pending approvals and past reports; historical/current distinction | D13, D15, T08, UI03, UI05 | DEMO-02 restart; DEMO-03 history |

## Exact BRD acceptance targets

Target wording below is transcribed from BRD section 12. Measurement rules are proposed operational definitions; no target is changed or achieved.

| ID | Metric | Exact acceptance target | Planned verification |
| --- | --- | --- | --- |
| A01 | Competitor discovery | Three relevant competitors identified when sufficient evidence exists | D01–D03, T02: IDs, evidence and five-dimension relevance rationale |
| A02 | Source traceability | At least 90% of material factual claims linked to supporting sources | T03, T07, D11: supported material factual claims / all material factual claims |
| A03 | Data completeness | Required comparison fields populated or explicitly marked unavailable | T03, T07, D08: value or reason-coded unavailable for every required field |
| A04 | Report quality | At least 4 out of 5 test reports rated useful by the business owner | H01: five actual reports and recorded owner usefulness decisions |
| A05 | Failure recovery | At least 4 out of 5 designed failure tests handled correctly | Predeclared D04, D05, D06, D10, D12 cohort; full suite reported separately |
| A06 | State recovery | Interrupted research run resumes without losing completed results | D13, T08: persisted result/approval/event comparison before/after restart |
| A07 | Unsupported claims | No knowingly fabricated facts in the final report | T02, T03, T07, D11, D12: controlled provenance and actual evidence review |
| A08 | Human approval | Final report presented for review before any external business action | D14, S03, UI04: owner/version-bound review; external business tools excluded |

BRD states these are initial thresholds, not guaranteed performance. Traceability and completeness remain separate. A source ID alone does not prove support; assess snippet adequacy separately. Unsupported asserted facts stay in the denominator. Zero material claims means coverage unavailable, not 100%. Report sourced versus unavailable field counts separately even when both satisfy completeness. Proposed H01 rubric covers relevance, evidence clarity, comparability, actionable hypotheses and understandable limitations; the owner explicitly answers useful/not useful. This does not replace four of five useful reports with a new rating threshold.

## UI screen test IDs

| ID | Reference screen and board | Fidelity and behavior checks | FR links |
| --- | --- | --- | --- |
| UI01 | Brief, 1280 x 1240 | Forest/lime hero; floating soaps/bubbles; four goal chips; segment tiles; validated fields; five crew badges; clarification; actual budget display | FR-01 |
| UI02 | Shortlist, 1280 x 1320 | Dashed YOU marker; five fit dimensions/rings; interpretation label; evidence; select/reject/replace; fewer allowed with insufficiency; unknown axes explicit | FR-02, FR-08 |
| UI03 | Live, 1280 x 1300 | Dark control room; real nodes/parallel lanes/rings; persisted tool log; usage/checkpoints; pause/stop; five server-gated DEMO chaos switches | FR-03, FR-09 |
| UI04 | Report, 1280 x 2600 | Soap cards; actual coverage/completeness; skin/conflict/missing flags; 2x2 landscape; numeric comparable price chart; own weight prerequisite; numbered hypotheses/citations; changes and approval | FR-04–FR-08 |
| UI05 | History, 1280 x 1240 | Timeline; select two runs; dated before/after; new/changed/not-found uncertainty; not-rechecked label | FR-09 |
| UI06 | All screens | Mobile reflow, keyboard/focus, labels/contrast, reduced motion, loading/empty/error; DEMO labels on synthetic views/exports; proposed 390-width mobile check | FR-01–FR-09 |

UI_REFERENCE.md contains palette, fonts and dimensions. ARCHITECTURE.md records proposed deviations from example values and absent business fields.

## Error scenarios and deterministic fixture IDs

Each future fixture under evaluations/fixtures/lather-lens-demo-v1/ must contain input, mocked tool transcript, expected assertions, actual behavior, outcome and limitation. Synthetic cases use visible DEMO labels and reserved example domains. D01–D15 retain EVALUATION_PLAN.md identifiers; D16/D17 extend that catalog.

| ID | Scenario and origin | Expected assertion |
| --- | --- | --- |
| D01 | Normal run, BRD section 13 | Three evidence-backed candidates, both gates, cited report; no fabricated entities |
| D02 | Insufficient discovery, sections 9/13 | Fewer than three or clarification; explanation; no quota fill |
| D03 | Empty/irrelevant results, section 9 | Record exclusion; bounded rediscovery/clarification or stop |
| D04 | Timeout/5xx, sections 9/13 | At most two additional attempts; preserve successes; terminal limitation |
| D05 | Rate limit 429, section 9 | Respect retry timing within deadline/budget; no infinite loop |
| D06 | Inaccessible site, section 9 | Access status; no bypass; permitted alternative or unavailable |
| D07 | Conflicting prices/details, sections 9/13 | Preserve both dated source-linked observations; no silent winner |
| D08 | Missing weight/ingredients, sections 9/13 | Explicit unavailable; null unit price; no guessed ingredients |
| D09 | Mismatched pack/variant, PRD section 11 | Reject incomparable arithmetic; same purchase item only |
| D10 | Malformed JSON, BRD section 9 | Validate, bounded repair, explicit terminal failure |
| D11 | Unsupported skincare claim, sections 11/13 | Marketing attribution/flag; no medical efficacy, certification or testimonial invention |
| D12 | Failed quality validation, sections 9/13 | Targeted bounded revision or visible unresolved limitation |
| D13 | Interrupt/restart, sections 9/13 | Completed work/pending gates survive; lease fencing prevents stale commit |
| D14 | Approval bypass, FR-08/PRD section 11 | Deny absent/wrong-owner/stale-version approval |
| D15 | Repeat/stale observation, BRD section 13 | Dated history; not found and not rechecked distinct; no discontinuation inference |
| D16 | Budget/deadline/cancellation, PRD sections 6/9 | Stop new calls; retain partial draft; never auto-approve |
| D17 | Duplicate job/decision, PRD sections 5/8 | Idempotent same-payload result; changed payload conflicts; one approved snapshot |

## Additional verification IDs

| ID | Planned checks | Requirement |
| --- | --- | --- |
| T01 | Brief schema and clarification before search; own price/weight optional | FR-01 |
| T02 | Five-dimension ranking, provenance and bounded discovery | FR-02, A01, A07 |
| T03 | Source URL/title/publisher/date/hash/status; claim snippets/links; complete collected-field schema | FR-03, A02, A03 |
| T04 | Decimal arithmetic, currency/weight/pack validation; missing versus zero; no implicit FX | FR-04 |
| T05 | Fact/interpretation/hypothesis separation; contradictions and evidence gaps | FR-05 |
| T06 | Opportunity count and evidence/rationale/benefit/assumptions/next step | FR-06 |
| T07 | Every report section; coverage denominator; completeness; citations; versioned export | FR-07, A02, A03 |
| T08 | Completion journal/checkpoint reconciliation; concurrent lanes; crash boundaries | FR-09, A06 |
| S01 | Authentication, owner isolation, RLS, input limits, explicit errors | BRD section 10; PRD sections 8/10 |
| S02 | SSRF/DNS/redirect/robots/access restrictions; source prompt injection cannot change policy | BRD section 10; PRD section 10; injection defense is design addition |
| S03 | Agent allowlists; no external business writes; no key/log leakage; opt-in egress/traces | FR-08; BRD section 10; user constraints |
| S04 | Production denies chaos; atomic usage reservations; sanitized telemetry | PRD sections 6/10 |
| P01 | Measure latency/usage/cost; bounded concurrency; no invented SLO or cost result | BRD cost awareness; PRD sections 10/11 |
| H01 | Owner rates five actual reports; at least four useful | A04 |

BRD section 15 deliverables map to BACKLOG.md B02–B16: working app/source, architecture/roles, real sample report, normal/failure results, state/retry/approval docs, demo recording and setup/configuration. Section 16 requires end-to-end normal execution AND meaningful failure/recovery; documentation/source checks cannot satisfy completion.

## Stage 1 harness status

Subsequent user architectural decision: see REQUIREMENTS_QUALITY_AUDIT.md Q01–Q10, ADR 0005, MODEL_BENCHMARK.md and MODEL_IMPLEMENTATION_PLAN.md. Provider neutrality and quality-first benchmark-before-selection now constrain FR-02–FR-07 implementation. Existing budgets remain authorization limits. All eight original BRD targets and source files are unchanged; no candidate model selected or live benchmark executed.

Implemented: backend/app/harness/contracts.py, agent_schemas.py, policy.py, ports.py and evaluation.py. Tests: backend/tests/test_harness_validation.py V01–V25, with parameterized cases. Maps partially to FR-02/03 (candidate/evidence shape), FR-04/05/06 (typed claims/shortfall shape), FR-08 (pure gate/allowlist checks), FR-09 (checkpoint/event schema only), A02 (presence/support aggregation only), A03 (unavailable shape), A07 (unreviewed agent evidence), A08 (preflight). It does not fulfill these requirements end-to-end. No domain price arithmetic, durable store, auth, graph execution, replay runner or live tools implemented. Read HARNESS_STAGE_RESULTS.md for actual commands/results; all eight original application acceptance targets remain unevaluated.

## Scaffold status

B03 adds frontend App Router/TypeScript/Tailwind and FastAPI/Pydantic/SQLAlchemy/Alembic package foundations, exact dependency pins/locks, local/CI commands and /health/live plus /health/ready. Backend tests/test_health.py covers lifecycle, disabled external services, redacted configuration errors and the actual .env.example. Frontend tests/health.test.ts covers typed health-response validation. Existing harness tests/source documents are preserved. Health readiness explicitly reports database not_checked; no auth/RLS/domain migrations or DB recovery is claimed. UI is a labeled DEMO placeholder, not completion of UI01–UI06. All eight business acceptance targets, golden workflow trajectories and model-quality benchmark remain unevaluated. Actual check outputs and changed files are in SCAFFOLD_STAGE_RESULTS.md. No subsequent stage has begun.

## Auth and storage stage status

B04 now implements app/auth.py Supabase token verification, app/models.py owner/run-scoped storage, frozen Alembic 0001 RLS migration, app/repository.py and typed protected app/api.py routes. docs/openapi.json exports 21 paths. Local tests use real Supabase Auth and PostgreSQL; no service-role key enters frontend. tests/test_auth_api.py adds unit auth/OpenAPI/key restrictions; tests/test_storage_integration.py adds actual owner/RLS, same-run FK, browser write denial, concurrent idempotency, report immutability and guarded rollback/reapply tests. Details and actual outcomes: AUTH_STORAGE_STAGE_RESULTS.md.

FR-01 now has validated brief persistence; FR-02–07 have owner-protected read/storage schemas but no research agents or final quality results; FR-08 now has authenticated artifact-bound approval endpoints; FR-09 now has real Postgres run/event/report/approval/job persistence. S01 and D14/D17 boundary behavior have local integration evidence. Full D01–D17 workflows, A01–A08 business acceptance, actual owner-usefulness and T08 LangGraph restart recovery remain unevaluated. This does not advance to UI, research, worker or deployment stages.
