# LIVE pilot and submission results - 26 October 2026

This is a real-source local pilot, separate from synthetic DEMO evaluations. The original BRD, PRD v1.1 and Claude HTML are unchanged. Source and design checks verified the original files and all eight verbatim BRD targets. No staging-site changes, cloud provisioning, deployment or competitor contact occurred.

## Actual outcome

One owner/run-scoped pilot researched **Fika Soaps** and **Forest Essentials** for Petite Batch's handmade-soap market brief in India. Tavily discovery produced a source-backed two-brand shortlist. The user approved it. Public-page failures, source gaps and strict query/name validation initially limited extraction. Six targeted first-party product searches supplemented the same saved evidence, preserving the original task snapshots and earlier reports.

The Analyst produced attributed notes and opportunity proposals. The independent model Reviewer identified wrong price framing, incorrect promotion-date summaries and overstated opportunity premises. Automatic correction remained bounded. At the user's explicit request, an additional single extractive correction removed unsupported ranges and opportunity claims, used verbatim listing excerpts, and received fresh independent review. **Report v4 passed mechanical/model review, received explicit user approval, was saved immutably, and exported to HTML/CSV.** Earlier draft versions were retained. Model review is not human source-support adjudication.

The corrected report includes attributable evidence for both brands, listed soap/product prices in source excerpts and brand/product notes. It deliberately has **no SKU-normalized price comparison and no claimed grounded opportunities**: the purchase-item bindings and opportunity premises were insufficient. This does not satisfy every requested business outcome. Three ideas are not added merely to meet a quota.

## Spending and measurements

User authorization: initially 10 Tavily credits, then another 10 (20 total), and a separate US$5 model cap. Fireworks was explicitly selected provisionally. The model adapter remains a domain port; no model benchmark winner is claimed. The saved scope is one run, not a general new-live-run service.

At v4 review: **14 Tavily credit reservations**, **106,461 recorded model tokens**, **US$1.720391 reconciled cost upper bound** (including conservative uncertain-attempt reservations; not an invoice). The exact approval/save and final metadata are recorded in LIVE_RECEIPT.json. Replaying cached successful calls did not repeat their provider dispatch. One uncertain reserved attempt remains recorded rather than resubmitted or assumed free. No further paid runs were started for video recording. LangSmith remote exports remained off.

## Checks actually executed

From `backend/`:

```powershell
.venv/Scripts/python.exe -m ruff check app tests tools migrations
.venv/Scripts/python.exe -m mypy app
.venv/Scripts/python.exe -m pytest -m 'not integration' -q
```

Latest pre-final results: Ruff passed; mypy reported no issues in 75 app source files; 323 offline tests passed with 74 integration tests deselected. A regression run first caught a bare `revision=3` becoming valid; the state now requires an explicit manual-correction reference, with a matching durable authorization checked by the correction service. Final results are appended below after execution. The original negative state-bound test was retained.

From `frontend/`:

```powershell
npm run lint
npm run typecheck
npm test
npm run build
```

Actual results: ESLint passed; TypeScript passed; **25 tests in 6 files passed**; production build passed and generated **16 pages/routes**. The build performs no paid provider calls.

From the repository root:

```powershell
powershell -NoProfile -File scripts/verify-sources.ps1
powershell -NoProfile -File scripts/verify-design.ps1
node scripts/capture-live.cjs
node scripts/prepare-overview.cjs
```

Actual results: all three source hashes passed; FR-01 through FR-09 were readable; all eight original acceptance strings and required traceability IDs passed structural validation. Read-only screenshots used the persisted LIVE run. The illustrated HTML/PDF contains five designed pages, rendered to PNG for visual inspection. The 3.5-minute MP4 has captions and an offline-generated voiceover, with a separate narration script; it inspects persisted live results and shows the approved v4 ending.

Recorded golden evaluation, from `backend/` (explicit test settings, no provider spend):

```powershell
$env:LATHER_ENVIRONMENT='test'
$env:LATHER_EVALUATIONS_ENABLED='true'
$env:LANGSMITH_TRACING='false'
.venv/Scripts/python.exe -m tools.evaluate_golden --output ../docs/live-golden-candidate.json --record-proposed-baseline evaluations/baselines/lather-golden-v1-r4.json
.venv/Scripts/python.exe -m tools.evaluate_golden --baseline evaluations/baselines/lather-golden-v1-r4.json --output ../docs/live-golden-regression.json
```

Both executions passed **17/17 predeclared DEMO cases**, including **5/5 failure-cohort cases**; owner ratings **0/5**, real support **unmeasured**, actual provider calls/tokens/cost **zero** for these recorded evals. r4 is a proposed regression baseline, not a business acceptance approval. CI now references r4; remote CI execution has not been observed.

```powershell
.venv/Scripts/python.exe -m tools.security_audit --output ../docs/live-secret-audit.json
```

Actual result: zero source secret-pattern findings. Dependency inventory: 557 versions; **not queried** in this stage. Earlier security-stage results remain historical. A pattern scan is not a proof of no secrets. No current vulnerability rescan, hosted load test or production-scale claim is made.

## Acceptance coverage and limitations

FR-01..09 remain traced in REQUIREMENTS_TRACEABILITY.md. This pilot exercises brief persistence, discovery, human shortlist approval, public research, model-assisted extraction/analysis/review, durable events/state, final approval and immutable sourced export. Deterministic history, failure/recovery and permissions have separate recorded/offline coverage; no second real-market run was created to claim live history comparisons.

Original BRD business gates remain authoritative: >=90% material-claim source traceability; >=4/5 owner-rated useful reports; >=4/5 failure tests handled; resume without losing completed work; no knowingly fabricated facts. The current recorded failure cohort passes 5/5. Real prose-wide traceability/support and owner usefulness remain unmeasured. Working citations/quote integrity cannot establish semantic entailment. No >=90% or >=4/5 business usefulness pass is claimed.

Remaining limitations: restricted/unavailable websites, incomplete SKU/pack/weight bindings, stale promotional/news material, no grounded opportunities in the approved sample, incomplete live acceptance cohort, provisional model choice and no paid benchmark. The manually requested correction tooling is a narrow local-pilot operation, not a public self-service editing endpoint. Retention/deletion, distributed abuse control, backup restoration, production migration operations and broad hosted concurrency remain outside the verified pilot.

The clean submission preserves all original documents locally and includes selected relevant docs, application source/tests/fixtures/locks, the illustrated overview, recording and approved HTML/CSV sample. Private `.env`, session caches, account/credit screenshots, dependencies and build outputs are excluded. Review this stage before starting any subsequent work.

Final verification: Ruff passed; mypy passed (75 app source files); **323 passed, 74 deselected in 27.27s**. The independent recorded regression repeat passed **17/17**, `comparable=true`, `critical_regression=false`; proposed baseline review remains pending. All five final PDF pages and representative video frames were visually inspected. The MP4 measured **00:03:30.00**. The GitHub submission commit uses `[skip ci]` to avoid starting remote runners; no remote CI result is claimed. Source packaging also compares selected bytes against configured provider keys, local access/refresh tokens and private DB URLs without displaying them.

Follow-up display correction: the side-by-side comparison now shows persisted, approved source-claimed AI notes when structured cells are missing, with a separate attribution label and clickable evidence. It does not promote notes into verified SKU facts or alter the immutable v4 report. Every cited source must have an OK access state and belong to the displayed competitor; unknown/mixed-brand bindings are excluded. Two meaningful frontend tests cover these boundaries. **27 frontend tests across 7 files, ESLint, TypeScript and the production build passed** after the change. The stale hard-coded brief spending-cap sentence was removed. The overview was expanded to **six pages**, adding enlarged real Fika price/ingredient screenshots. The comparison video segment and spoken project-purpose explanation were refreshed. Synthetic narration was explicitly selected by the user after clarifying that a genuine human recording was unavailable. Audio/video remain local and excluded from GitHub.

Final follow-up: **28 frontend tests across 7 files passed**, with lint/typecheck/build also passing. Explicit ingredient declarations can be quoted verbatim from approved stored evidence; broad ingredient marketing is not treated as an ingredient list. The overview now has **seven pages**, including a dedicated framework/API architecture page. The user authorized a four-minute video with the same architecture explanation. All original PRD/BRD/reference input files, credit screenshots, handout images and reference screenshots remain local and are excluded from the public submission. Input-integrity/reference-fidelity scripts therefore require the privately retained originals; the public source alone cannot reproduce those private-input checks. No original document was deleted.

Final delivery: `Lather-Lens-4m-FINAL.mp4` measured **00:04:00**, with H.264 video and a loudness-normalized AAC synthetic narration track. The closing architecture section, corrected comparison segment and all seven PDF pages were visually verified. The public GitHub `main` submission excludes private input documents and all audio/video. Earlier uploaded private-input content was removed from the current single submission commit via an exact-lease guarded update; the original local files and backup commit remain preserved. GitHub public visibility was verified through an unauthenticated metadata request. No app deployment was performed.
