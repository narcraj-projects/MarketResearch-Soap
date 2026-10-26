# Gateway and Scout discovery slice

This stage implements PRD delivery item 5 / backlog B06, without starting Researcher or the full LangGraph worker. Original BRD, Claude HTML and PRD v1.1 were read using the previously authorized original filenames; their hashes remain unchanged. All execution here is DEMO recording replay. No real competitors or sources were researched, provider selected, credit spent or resource deployed.

## Boundaries

| Module | Responsibility |
| --- | --- |
| harness/contracts.py, search.py, ports.py | Existing RunContext/SearchCall plus concrete search sources, outcomes, accounting policy and SearchToolGateway port |
| harness/policy.py, gateway.py | Scout/discover allowlist, version pin, argument validation, persisted reservations, retry/deadline/timeout and typed result |
| adapters/tavily.py | Fixed Tavily Search wire request, bounded response parser and sanitized failure classification; no retry loop or agent decisions |
| harness/urls.py | Offline URL canonicalization and registrable-domain identity using pinned tldextract/bundled suffix list |
| harness/recordings.py | Manifest/hash/version checked, ordered exact HTTP request matching; no live fallback |
| agents/scout.py | Deterministic relevance interpretation, source-backed identity, full pool/exclusions and up-to-three selection |
| harness/search_store.py | Owner/RLS transactions, shared-run budget locks, attempt/source/usage/event journal, checkpoint and pending approval |
| services/discovery.py | At most two discovery queries, sufficiency/shortfall decision and durable pause; no next-stage execution |

The generic ToolGateway protocol remains a future multi-tool boundary; SearchToolGateway is the implemented typed search envelope. Scout depends on stored evidence and that port, not a provider SDK. No LLM call or vendor/model default is introduced. Final model selection still requires the separate quality-first benchmark.

## Dispatch, authorization and accounting

SearchCall forbids extras and bounds query length (2000), results (1..10), attempt (1..3) and timeout (1..60 seconds). The concrete gateway accepts only the initial Scout/discover call; it owns subsequent attempts. Unknown tool version, role/phase, deadline or unknown cost blocks dispatch. The adapter additionally requires the gateway's internal capability; Python module privacy is an architectural boundary, not a hostile-code sandbox.

There is deliberately **no enabled real transport or real-key factory**. TavilyAdapter only accepts httpx.MockTransport; no transport fails `live_not_approved`, even if a key exists in the environment. Existing Settings still prohibits live service enablement. No key is read or needed. Enabling real search requires a separately approved implementation/configuration review, credentials and conservative monetary bounds; no free credits are used automatically.

The wire contract follows [Tavily Search documentation](https://docs.tavily.com/documentation/api-reference/endpoint/search): fixed HTTPS POST endpoint, explicit basic/general parameters, answer/raw-content/images/automatic parameter selection disabled and usage requested. This stage pins one search configuration for deterministic conformance; it does not claim basic is the final quality-optimal setting. Future approved depth evaluation should prioritize relevance/grounding. [Tavily credits documentation](https://docs.tavily.com/documentation/api-credits) is distinct from a run-specific approved USD price bound; no dollar price is inferred from credits or hardcoded here.

Before EACH dispatch, a short Postgres transaction locks the owned run and checks current status/version, persisted deadline/version pins and all reservations/other usage. Reservations include every attempt, including failed/uncertain attempts, without double-counting completed search usage. The transaction ends before HTTP work. Context is an immutable initial snapshot; resume restores used/reserved values from the journal, and each reservation rechecks the database rather than trusting stale counters. An unchanged completed attempt is reused without a new charge. Changed arguments/versions/accounting under the same operation conflict. An uncommitted/uncertain reservation is never silently retried or refunded.

Replay uses zero actual provider cost. usage_records.cost_usd and ToolResult.usage.cost represent conservative **DEMO accounting** for these cases, not measured bills. Positive bounds in tests are explicitly synthetic budget examples. Every success/error attempt counts; live billing reconciliation is not implemented.

Default: initial attempt plus two retries. Only timeout/network error/429/selected 5xx retry. Backoff is exponential plus injected bounded jitter; numeric and HTTP-date Retry-After are respected when time permits. Recheck budget/deadline before each attempt, including cached replay; stop when retry delay reaches the deadline. 401/403/432/433 and malformed/oversized output do not retry. HTTP I/O timeouts are bounded by remaining time and body reads have an elapsed guard/256KB cap. These are not hard process preemption or instant remote-cancellation guarantees. Responses/headers/raw exception inputs are never emitted as failure telemetry.

## Source and relevance integrity

Normalize scheme/IDNA hostname/default ports, remove fragment/tracking parameters, retain meaningful query order and case-sensitive paths. Reject credentials, non-HTTP(S), IP literals/numeric hosts, local/internal names, control characters, nonstandard ports and unknown public suffixes. Reserved .invalid URLs are allowed only in this DEMO mode. Domain deduplication uses the bundled public/private suffix rules, including multi-label suffixes and hosted-site tenants; no suffix-list download occurs.

Search result URLs are **not fetched**. This is not the later DNS/redirect/connection/robots-aware page retrieval boundary. Every retained hit creates an owner/run-scoped source with canonical URL, hostname publisher, title, search-observation time, exact snippet, SHA-256 of that snippet and `evidence_kind=search_snippet`. `access_status=ok` means the snippet was returned, not that the underlying site was fetched or its claim verified. The new column/API distinguish this from page_excerpt. Provider-generated answers/extra competitor suggestions are ignored.

Identity is an exact leading title string also present in the snippet; eligibility requires explicit handmade/cold-process soap, maker wording and literal target-market evidence, and excludes obvious resellers/directories/marketplaces. Identity, geography mention and maker wording can still be misleading on the live web: these are candidates for review, not independently verified businesses. Unsupported categories stop; this is a conservative English/soap/online-first baseline.

Five equal-weight fit dimensions: product, customer, geography, price segment, channel. Literal matches score 1, partial audience overlap 0.5, unknown/no-match 0. Unknown remains a separate status and known-dimension count, not evidence of mismatch. Segment labels must occur explicitly; no prices or delivery promises are inferred. Each non-unknown fit records an exact snippet quote. The score/rationale is an interpretation, never market truth. Ties are deterministic by score/domain/name. One candidate per registrable domain, up to three selected, full eligible pool/exclusions retained. Fewer candidates requires insufficiency; zero produces clarification/partial and no approvable empty shortlist. User-known competitor names never become candidates without search evidence.

Publication rebuilds selection from the persisted brief and completed journal, rather than accepting a caller/model candidate pool. Typed artifact IDs must match selected candidates; generated identity/source IDs are stable and run scoped. Sources, usage, completion/event/checkpoint commit together. A response-before-local-commit crash remains uncertain and cannot promise exactly-once remote billing.

## Durable approval interrupt

Nonempty discovery commits candidates, rationale/fit/source references, immutable artifact hash/version, run checkpoint, pending approval and approval.pending event in one transaction. Run becomes shortlist_review and Scout returns. New processes reload the same request/artifact with no dispatch. No Researcher work executes. The existing authenticated owner decision API checks request/run/owner/version/hash, artifact integrity and candidate existence/count; idempotent retries reuse one decision. Wrong owner/stale/tampered artifacts fail. Approval records researching readiness only; there is no later-stage worker here. Rejection/change request remains partial pending later routing work.

This is a **database-backed application interrupt**, not a LangGraph interrupt/checkpointer implementation. Full LangGraph routing, leases/fencing, cancellation, Researcher fan-out and final-report workflow remain B08/later stages. This preserves the PRD delivery order without claiming those components exist. No new approval can authorize external business actions.

`GET /api/runs/{id}/shortlist` exposes the typed owner-scoped snapshot. Existing `/events`, `/sources`, `/competitors`, `/approvals`, `/usage` and shortlist-decision routes expose persisted evidence/decisions. No public endpoint can supply fixture responses, tool arguments or approval context. The explicit local DEMO command is a one-shot replay, not an automatic queue consumer. Frontend Shortlist remains the prior labeled DEMO preview; this stage does not silently wire it to real research.

## Verification and limits

Fourteen pinned synthetic recordings SC01..SC14 cover clean/fewer/empty/irrelevant/duplicate-domain, 429/timeout/denial, malformed/unsafe URLs, unknown fit, injected quota suggestion, 5xx and deadline. These are recorded protocol fixtures authored as DEMO, not live captures. Deterministic CI denies network. Additional tests cover arguments/allowlists, exact replay/hash/version mismatches, budgets/cache/uncertain reservations and response limits. Dedicated local Postgres tests exercise real RLS, concurrent reservation caps, pending approvals, stale/tampered decisions and fresh OS-process restart after result commit before publication.

Citation presence, ID/hash/quote provenance and genuine support are different. The Scout verifies wiring/provenance and interprets relevance; it does not adjudicate whether every factual component is entailed, current, independent or SKU/scope-correct. Sources stay unreviewed. No 90% support, owner usefulness or final BRD release acceptance score is claimed. See SCOUT_STAGE_RESULTS.md and SCOUT_EVAL_RESULTS.json for actual results/commands and unresolved limitations. Stop for user review before continuing.
