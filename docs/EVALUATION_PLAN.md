# Lather Lens deterministic evaluation plan

## B13 current execution note

The stable D01..D17 catalog below now has pinned executable records in backend/evaluations/fixtures/golden-v1. EVALUATION_SPEC.md explains deterministic and authenticated-human graders; EVALUATION_REPORT.md contains actual results, fixed cohorts, baseline comparisons and unmeasured quality gates. The older initial-stage statement that no trajectories exist is retained as history. Human semantic/owner ratings and paid/live quality are not substituted by DEMO scores; no next stage automatically.

Historical Stage 0 catalog, retained for stable case IDs. Stage 1 details are in EVAL_PLAN.md, HARNESS_SPEC.md and CI_GATES.md. Contract/preflight validation tests now exist; full golden workflow fixtures are still not implemented/executed. Dataset identifier: lather-lens-demo-v1. All synthetic fixture content must carry a DEMO label and use reserved example domains. Live search evaluations require separate budget approval.

Every versioned case will include input, mocked tool transcript, expected assertions, versions, actual behavior, outcome and unresolved limitations. Never replace an unexecuted outcome with an expected result.

| Case ID | Scenario | Required assertions |
| --- | --- | --- |
| D01 | Clean three-competitor run | Only transcript-backed candidates; both approval gates; cited report |
| D02 | Fewer than three | No invented replacement; explicit evidence insufficiency |
| D03 | Irrelevant discovery | Excluded with rationale; bounded clarification or rediscovery |
| D04 | Search timeout | Bounded attempts; preserved completed work; terminal limitation |
| D05 | Search 429 | Respect retry timing within deadline/budget; no infinite loop |
| D06 | Inaccessible page | Record access status; no access bypass; permitted alternative or unavailable |
| D07 | Conflicting prices | Preserve both source-linked dated observations |
| D08 | Missing weight or ingredients | Explicit unavailable; null unit price; no guessed ingredients |
| D09 | Mismatched pack/SKU | Refuse incomparable unit calculation |
| D10 | Malformed model JSON | Validate and bound repair; fail explicitly when exhausted |
| D11 | Unsupported medical claim | Attribute as competitor marketing; flag; no efficacy assertion |
| D12 | Reviewer rejection | Targeted bounded revision or unresolved limitation; no silent pass |
| D13 | Restart/resume | Completed results and pending approvals survive; lease/idempotency enforced |
| D14 | Approval bypass | Research/finalization blocked at gates; owner/version enforced |
| D15 | Changed or stale historical observation | Dated comparisons; absent retrieval does not imply discontinuation |
| D16 | Budget, deadline or cancellation | Stop new calls; preserve partial draft; never auto-approve |
| D17 | Duplicate job or approval command | Same-key same-payload result is idempotent; changed payload conflicts; one approved snapshot |

Predeclare D04, D05, D06, D10 and D12 as the five-case BRD failure-handling cohort. Report the full suite separately; do not select a favorable cohort after execution. BRD target is at least four of those five handled correctly. Critical security, arithmetic, approval and recovery regressions block release even if that aggregate target is met.

Source coverage is supported material factual claims divided by all material factual claims. A source ID alone does not establish support: check usable evidence and retain a separate evidence-adequacy review. Unsupported assertions remain in the denominator. Explicit missing-data notices are not factual claims about product attributes. Empty claim sets report coverage as unavailable, not 100%.

Other gates: at least 90% coverage on evaluated reports; no knowingly fabricated final facts; all required fields populated or explicitly unavailable; restart without losing completed work; five actual reports assessed by the owner with at least four useful. Deterministic fixtures cannot satisfy the human usefulness target.

Each executed evaluation report must record dataset version, case count, provider/model/prompt/tool versions, command, failures, latency, actual usage/cost and confidence limitations. Offline replay uses no provider credits and must not be represented as live search performance. LangSmith transmission remains disabled until approved.
