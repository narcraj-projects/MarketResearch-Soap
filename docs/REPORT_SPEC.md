# B10 persisted reports, approvals and exports

25 October 2026. Implemented locally for review. This stage covers the current report/UI task only. BRD business requirements, PRD v1.1 and the fully decoded five-screen Claude HTML remain authoritative in that order. Authorized source aliases and source hashes are unchanged. No live search/model API, paid service, cloud resource, competitor contact, deployment or external publishing is used.

## Plan and requirement boundaries

Replace route-level fixture imports with owner-authenticated persisted projections. Freeze the report presentation into the immutable report artifact before its independent review receipt. Retain the reference cover, forest/lime palette, competitor colors, source ring, flags, positioning map, price chart, comparison, opportunity cards and sources. Enforce final approval and approved-save on the server; export only the exact saved snapshot. Verify with offline unit checks, dedicated local Auth/Postgres integration, browser interactions and responsive screenshots.

FR-01 supplies the saved brief and its scope; FR-02/03 supply the saved shortlist, rationale, sources and observations; FR-04 supplies eligible same-item arithmetic; FR-05/06 supply typed comparisons and conditional opportunities; FR-07 is the structured report/export; FR-08 is the exact-artifact human gate; FR-09 supplies actual run activity, checkpoints, usage and a dated archive. Full two-run semantic change detection remains B11.

## Data and version boundaries

`report_types.py` defines immutable Pydantic `ReportSnapshot` (report-presentation-1.0), coverage/position/source/approval DTOs, `ReportView`, `RunView` (run-view-1.0) and history metadata. `reporting.py` deterministically constructs them. `services/analysis.py` saves the presentation with the analysis and shortlist inside analysis-report-1.0 JSON before computing its SHA-256 hash. It includes the brief, summary, scope, original typed findings/prices/opportunities, source excerpts/URLs/dates/status/content hashes, coverage and positioning premises. No later mutable run value becomes report evidence.

Graph/checkpoint/enrollment pin is workflow-1.2. Existing workflow-1.1 checkpoints are refused rather than reinterpreted. No migration or dependency change is needed: report JSONB is already immutable and owner protected. Valid earlier analysis reports may be projected from immutable brief/source/research inputs without modifying the old report; the API marks `legacy_immutable_inputs`. Prototype/malformed reports have no invented presentation and cannot export without a valid snapshot, exact review receipt, human decision and completed save. New reports mark `persisted`.

`GET /api/workspace?run_id=...` checks owner before assembling the selected run. Without an ID it chooses the owner's latest run; no run returns an explicit empty state. It includes latest 100 events, sequence cursor, all recorded completed-node names, checkpoint date, completed/reserved/retry calls, token/cost bounds, competitors and persisted lane counts. No simulated progress, artificial elapsed time, fabricated search results or client fault switches remain. Human-readable log entries summarize actual event kinds/fields; the keyboard-focusable log is capped at 480px and stacks date/agent/message on mobile, while raw persisted events remain available through the API. Polling uses persisted event cursors every two seconds; SSE remains an existing backend option. `GET /api/history/view` returns 20 actual owner runs per page and exact total; it does not infer product changes or disappearance.

Next BFF route allowlists accept only run UUIDs and explicit read/control/decision/export paths. HttpOnly same-origin sessions stay server-side. Writes require same origin and a request key. FastAPI validates Supabase Auth and Postgres applies owner RLS/non-bypass privileges. All private responses are uncached; errors omit upstream bodies/configuration. The UI clears prior data on fetch failure. `frontend/src/lib/demo.ts` and historical preview screenshots/baselines are preserved as unused artifacts, never imported by a live route.

The saved Brief has an explicit recorded-run queue button (40 calls, zero token/paid-cost cap). An authorized operator must run the local replay worker separately. Queuing does not fabricate progress, enable live transport or spend credits. Existing fixture matching can legitimately stop an unmatched user brief.

## Coverage denominator and genuine support

Material denominator = every non-null `fact` or `source_claim` finding ID, including unsupported/uncited assertions. Unknown rows, interpretations and hypotheses are excluded; the factual premises of those interpretations remain in the denominator. Multiple citations do not multiply numerator credit; zero material findings yields null/unknown, never 100%.

Presence counts a finding with a stored source reference. Intact-quote coverage further requires accessible evidence, the matching competitor, a safe HTTP(S) source URL, the exact excerpt and its SHA-256. The ring is explicitly **Intact source citations** = intact/material. Completeness uses a separate populated/unavailable comparison-field count. Genuine-support coverage remains null/not_adjudicated. The BRD 90% target is not declared met by links, exact quotes, tests or a green ring.

R01 includes an uncited material assertion in the denominator and replaces a true quotation with an intact but irrelevant quotation; a presence/quote score cannot distinguish its semantic support. B09's independent Reviewer checks observation/scope correspondence, but trusted human adjudication of actual sources is still required for business acceptance. Future evaluation must judge entailment, correct entity/SKU/date, attribution versus fact, contradictions and source credibility. Neither source advertising nor medical testimonials establish clinical truth.

## Charts, flags and evidence

Positioning is an interpretation of explicit captured positioning words, with premise IDs: ingredient-led/mixed/results-led and everyday/mixed/gifting. Only two known axes produce a marker at categorical 25/50/75 percent. Missing axes remain unplotted with source references. Price never supplies a missing positioning coordinate; no empty-space opportunity is inferred.

Price observations keep same-SKU/variant/offer identity and dated source evidence from B09. Missing or ambiguous price/weight/identity yields null, a hatched track and a reason, never a zero bar. A genuine zero is zero. Currency groups have separate scales; no FX, averaging conflicting listings or invented weights. Own-bar preferences lack SKU identity, so the report shows their raw saved reference and does not normalize it. This conservative UI difference preserves the same-item requirement.

Review flags are the actual independent receipt issues, including missing/conflicting/stale/medical evidence. Cards show the full conditional opportunity rationale, potential benefit, assumptions, next action, caveat and clickable premise findings; insufficiency remains explicit. Source dialogs contain stored exact excerpts, URL, retrieval date, status, locator and hashes, with keyboard Escape/focus return. External links are user initiated; browser tests block non-loopback traffic. The application makes no new competitor request while rendering or exporting a report.

## Approval, immutability and export

A report decision needs authenticated owner, pending request, matching report/run, current run version, exact artifact version/hash, digest integrity and the independent ready-for-human review receipt bound to that full report hash and analysis/input hashes. Decision and idempotency response persist transactionally. A forged matching-hash draft without its receipt fails. Rejected/request_changes decisions cannot save or export that report.

Managed approval records the decision but does not complete the run. The leased worker must resume the final gate and save after checking the same report/receipt/decision; awaiting-save remains visible after page reload. Buttons never create approval locally. Export additionally requires the selected report belongs to this run/owner, a matching approved decision/request, ready review and run complete. Old pending/stale/cancelled/unresolved artifacts cannot bypass the gate by calling the download URL.

Reports, source evidence, review receipts and decisions are immutable under runtime grants/RLS. New revisions create new rows and hashes. Rendering/export writes nothing to the report. Repeated downloads of an unchanged saved artifact produce identical bytes. No generated export timestamp, remote asset or model call changes content. The HTML/CSV carry report ID, version/hash, DEMO label, dated evidence, unknowns and review issues.

HTML is escaped self-contained markup with restrictive CSP, inline styles, no scripts/remote fonts/images, evidence anchors and original-source links. CSV has stable section rows with IDs, epistemic kinds, normalized values or explicit unavailable, source IDs and detailed JSON. Leading formula/control characters are neutralized in CSV cells; stored raw values are preserved. Download headers specify attachment, no-store and nosniff. Export is local authenticated download, not external publishing.

## Deliberate resolutions and limits

The HTML's fixed percentages, competitor coordinates, prices, issues, history changes and local approval simulation conflict with attributable persisted truth. Retain their composition and replace values with saved evidence or honest unknowns. Do not copy illustrative 94% into acceptance. History keeps its timeline/card composition with scope/status metadata until B11 implements evidence-aware two-run changes. Selecting/replacing individual shortlist candidates is not implemented; changes record a durable request_changes decision and require a new brief. This is stated in the UI.

This is a DEMO recording/rule-based application path, not validated live competitor research or a selected LLM strategist. Genuine support, relevance across real markets, business owner usefulness and release acceptance remain unmeasured. Large history/run projections use bounded queries, not a load-tested analytics service. Session refresh, broader browsers/screen-reader audit, production retention/backups, old-checkpoint migration and live-quality evaluation remain later reviewed work. No following stage starts automatically.

See REPORT_STAGE_RESULTS.md for actual commands/results and REPORT_STAGE_FILES.json for the complete before/after inventory.
