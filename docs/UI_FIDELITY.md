# Five-screen UI fidelity and operation

## B12 real test-only Chaos switches

Live retains the reference forest control room, lime accents, competitor-colored research lanes, terminal and dashed amber chaos column. Nine labeled native radios choose one immutable scenario for a separate DEMO run after server capabilities confirm test authorization. This is a deliberate resolution of the prototype's mutable five switches: combinations require separately pinned fixtures; no client flag or toggled fake completion is trusted. Disabled server capability hides controls, failed creation stays on the existing run with an error, and queued runs show zero recorded recoveries/completed lanes.

Persisted aggregate recovery counters use all run events, not only the terminal's latest hundred. Partial/empty/denied evidence and null weight remain visible; source quote coverage is still distinct from unavailable genuine-support quality. Recorded model responses are explicitly described as fixture projections with zero provider calls/tokens. UI-CHAOS-* and the new ui-screenshots/chaos captures verify desktop/mobile width, keyboard selection, real queue/reload/recovery and final approval waiting. CHAOS_STAGE_RESULTS.md records actual outcomes/manual inspection and limitations. Original source/screenshot assets remain unchanged. No subsequent stage automatically.

## B11 actual two-run history

History now retains the reference forest/lime cover, three primary counters, timeline, competitor color tiles and paper/white before-after cards with real run/version pickers, exact immutable links, source dialogs and uncertainty filters. Counts are field observations; New is newly observed in the sample, Gone is source-reported discontinued, and missing/denied/cached data stays unknown/stale. Both dates are historical; the source example Latest/current is deliberately qualified. Draft versions can be read but not compared/exported. No fixed sample counts or local synthetic history simulation.

Actual B11 captures: ui-screenshots/history/{supported-diff,unavailable-website}-{desktop,mobile}.png, with 390/768/1280px width checks. Earlier B10/reference/preview captures are unchanged. Generic screen-regression captures now use ignored cache. Manual inspection and exact actual checks/limits are in HISTORY_STAGE_RESULTS.md; no original-prototype pixel identity, broad accessibility certification or later stage is claimed.

## B10 current persisted screens (supersedes preview-operation notes below)

All live routes now read persisted owner results. Brief can queue an explicit recorded run; Shortlist uses saved fit/rationale and durable decisions; Live uses persisted nodes/events/lanes/usage/checkpoints; Report uses the frozen report and real approval/save/download; History uses actual dated metadata. No production route imports lib/demo.ts. Fixed preview ring/prices/map/history/approval simulation no longer run. Original preview files and screenshots are retained as historical artifacts.

Cover, forest/lime/paper, competitor colors, map/price/comparison/flags/opportunities/evidence composition remain. Insufficient axes are unplotted, missing prices hatched and source coverage is labeled intact/material, never genuine support. The reference's illustrative values cannot override evidence. History retains timeline/cards but defers real two-run semantic differences to B11. Editing a shortlist requires durable request_changes/new scope rather than a client-only selection. Details: REPORT_SPEC.md.

Actual B10 screenshots: ui-screenshots/persisted/{brief,shortlist,live,report,history}-{desktop,mobile}.png. Browser tests assert data/state/keyboard and document width at 390/768/1280px and capture full pages. These captures are not an automatic original-prototype pixel comparison; old static fixture baselines are preserved but no longer active. Manual inspection and actual results are recorded in REPORT_STAGE_RESULTS.md. No subsequent stage automatically.

The supplied `docs/Soap Market Research Agent — UI.html` is the authorized alias for `docs/claude-ui.html`. All five embedded templates, design and interactions were decoded and inspected. BRD business gates and PRD v1.1 implementation authority remain unchanged.

| Screen / route | Retained composition | Original | Desktop | Mobile |
| --- | --- | --- | --- | --- |
| Brief `/` | Forest hero, soaps/bubbles, overlapping form, goal chips, price tiles, crew and approval callout | [1](ui-screenshots/reference/1.png) | [1280px](ui-screenshots/implemented/brief-desktop.png) | [390px](ui-screenshots/implemented/brief-mobile.png) |
| Shortlist `/shortlist` | Fit map, exclusions, candidate rationale/dimensions/rings, sticky selection bar | [2](ui-screenshots/reference/2.png) | [1280px](ui-screenshots/implemented/shortlist-desktop.png) | [390px](ui-screenshots/implemented/shortlist-mobile.png) |
| Live Run `/live` | Dark control room, parallel pipeline/lanes, activity terminal, usage/checkpoint/chaos column | [3](ui-screenshots/reference/3.png) | [1280px](ui-screenshots/implemented/live-desktop.png) | [390px](ui-screenshots/implemented/live-mobile.png) |
| Report `/report` | Soap cards, section nav, quality flags, map/price chart, comparison, hypotheses, gaps/sources | [4](ui-screenshots/reference/4.png) | [1280px](ui-screenshots/implemented/report-desktop.png) | [390px](ui-screenshots/implemented/report-mobile.png) |
| History `/history` | Timeline, two-run selection, dated before/after change cards | [5](ui-screenshots/reference/5.png) | [1280px](ui-screenshots/implemented/history-desktop.png) | [390px](ui-screenshots/implemented/history-mobile.png) |

Forest #14231D, lime #C6EF6B, paper #F3F1EA, lavender #CFC6F5, turmeric #F4C95D, rose #F2B8A6, mint #9FD3C3. A/B/C colors stay consistent across screens. Bricolage Grotesque and Instrument Sans use bundled Latin assets with the original embedded license preserved. IBM Plex Mono was not bundled; technical values use the declared local monospace fallback, with no font download.

Responsive breakpoints are 1100/800/560px. Mobile stacks panels/lanes/cards and wraps navigation. Wide tables, pipeline and activity scroll within keyboard-focusable regions. Skip links focus main content; controls have visible focus, labels and semantic states. Native source dialogs contain focus and close with Escape. Errors/statuses use live semantics. Reduced motion disables animation, transitions and smooth scrolling.

Deliberate differences: Shortlist nav and persistent DEMO labels; Brief save/sign-in/loading/error/receipt and optional bar fields; validation instead of pretending to start research; report scope/methodology and hypothesis rationale/benefit/assumptions. These change page height. Report's illustrative 94% says fixture link presence only and genuine support not evaluated; it does not claim the BRD 90% gate passed. Historical not-found is not discontinuation, stopped runs say not re-checked, missing weight stays unavailable. Unresearched user-added candidates get no invented map coordinates. All four preview screens are synthetic DEMO; pause/stop/approve/search/chaos controls change local UI only. No research, durable checkpoint or business approval is claimed.

Screenshots were visually inspected against the supplied boards. Compositions and palette are retained; pixel identity is not claimed. Playwright compares the implementation with its checked-in Windows Chromium baselines, not original prototype pixels. CI never regenerates baselines. Chromium/keyboard checks are not complete accessibility or cross-browser certification.

For manual configuration, copy `frontend/.env.example` to ignored `frontend/.env.local`. Use private server LATHER_API_BASE_URL, LATHER_SUPABASE_URL and a publishable/anon key. Never put a database/admin credential there. Sign in with an existing approved account. Registration, reset, session refresh and draft autosave are outside this stage; expired sessions need sign-in again.

Same-origin server routes `/api/session`, `/api/briefs`, `/api/briefs/[id]` keep the token in an HttpOnly SameSite=Lax cookie, Secure on HTTPS. Writes compare Origin with protocol/Host without trusting forwarded headers. The upstream origin is fixed in server config. Responses are uncached and errors omit upstream details. FastAPI verifies Auth; Postgres enforces ownership/RLS. Unchanged-form retries reuse an idempotency key. Migration 0002 stores segment/own-bar preferences without rewriting 0001; old briefs receive schema defaults. Downgrade removes optional preferences.

After dedicated local Supabase start/prepare, run from the repository root:

```powershell
$env:LATHER_UI_INTEGRATION='1'
node scripts/serve-ui.cjs
# Open http://127.0.0.1:3140; Ctrl+C stops the UI/API children.
```

The launcher reads ignored local config without printing it. Only FastAPI receives the least-privilege database connection. Tests create disposable local DEMO Auth users without emails. Traces/videos/Auth screenshots are disabled; screenshots show signed-out synthetic previews. DEMO routes accept `?state=loading`, `?state=empty`, `?state=error` for deterministic review. See UI_STAGE_RESULTS.md for exact evidence. Stop for review before another stage.
