# Lather Lens

Lather Lens is a local competitor research application for a handmade-soap founder. It combines Tavily discovery and public evidence with model-assisted Scout, Researcher, Analyst and Reviewer roles, coordinated by deterministic LangGraph state. Next.js presents five reference-based screens; FastAPI, Supabase Auth/Postgres, owner RLS and a harness retain evidence, approvals and recovery state.

The 26 October 2026 live pilot researched Fika Soaps and Forest Essentials. Corrected report v4 passed mechanical/model review, was explicitly approved by the user, saved immutably, and exported as HTML/CSV. This is a sourced sample with limits, not a claim that all BRD business gates passed. Unsupported opportunities were removed; SKU-normalized price comparisons remain unavailable. See [live results](LIVE_PILOT_RESULTS.md).

## Use the running project on this computer

From PowerShell in `E:\HandmadeSoap-MarketResearch`:

```powershell
node scripts/open-local.cjs --live --report
```

This opens a separate signed-in Chromium window using the existing local owner session. A link opened in a different browser may request sign-in. Never copy a session token into chat or a URL. If the disposable local session expires:

```powershell
cd backend
.venv/Scripts/python.exe -m tools.refresh_local_session
cd ..
node scripts/open-local.cjs --live --report
```

1. **Shortlist:** inspect both candidates, relevance rationale and original source excerpts. Their approval is already persisted; do not approve again or start another paid run for the recording.
2. **Live Run:** inspect completed nodes, competitor lanes, actual events, limits and durable checkpoints. It shows this same saved live run, not a fresh search.
3. **Report:** inspect the summary, AI research briefing, attributed notes, missing fields, independent review and sources. The v4 approval binds the exact report hash.
4. **Download HTML / CSV:** available after approved save. Files are also supplied under `submission/`.
5. **History:** select the live report. Any controlled recorded cases are labeled DEMO; they are separate from the live sample.

The New brief form saves through the API. Arbitrary new live runs are not enabled by placing a key in `.env`: this submission pilot uses one explicitly authorized owner/run permit and spending caps. Do not represent the pilot as an unrestricted hosted service.

## Reproduce the source locally

Prerequisites: Node 24.11.x, Python 3.13, uv 0.7.20, Docker Desktop for the dedicated local Supabase stack. Dependency versions are pinned in the committed locks. Installation uses public package downloads, not paid APIs.

```powershell
powershell -NoProfile -File scripts/project.ps1 -Action install -Python 3.13
powershell -NoProfile -File scripts/project.ps1 -Action check
powershell -NoProfile -File scripts/local-auth.ps1 -Action start
powershell -NoProfile -File scripts/local-auth.ps1 -Action prepare
```

`prepare` creates disposable local test identities and applies local migrations. It is a fresh-machine setup command; do not rerun it over the active submission session. Configuration generated under `.cache/` stays private and is excluded from GitHub. See [Auth/storage](AUTH_STORAGE.md) for role and RLS details.

Build the frontend, then launch the integrated loopback services:

```powershell
cd frontend
npm run build
cd ..
$env:LATHER_UI_INTEGRATION='1'
$env:LATHER_UI_CHAOS='0'
node scripts/serve-ui.cjs
```

Frontend: `http://127.0.0.1:3140`. API health: `http://127.0.0.1:8140/health/live` and `/health/ready`. The launcher keeps DB credentials out of the frontend process. A fresh clone has no saved live data, credentials or authorization permit; use the supplied approved HTML/CSV sample without any API access. Paid live reproduction requires separate explicit authorization, keys in ignored root `.env`, a scoped permit and a worker.

Never overwrite an existing `.env` with the example. On a fresh checkout only, copy `.env.example` to `.env`; provider keys belong only in the ignored root file. No service-role key belongs in frontend configuration.

## Verify without provider spend

```powershell
cd backend
.venv/Scripts/python.exe -m ruff check app tests tools migrations
.venv/Scripts/python.exe -m mypy app
.venv/Scripts/python.exe -m pytest -m 'not integration' -q
cd ../frontend
npm run lint
npm run typecheck
npm test
npm run build
```

Recorded golden evaluation uses the guarded local database, not live providers:

```powershell
cd ../backend
$env:LATHER_ENVIRONMENT='test'
$env:LATHER_EVALUATIONS_ENABLED='true'
$env:LANGSMITH_TRACING='false'
.venv/Scripts/python.exe -m tools.evaluate_golden --baseline evaluations/baselines/lather-golden-v1-r4.json --output ../docs/live-golden-regression.json
```

Do not run migration rollback tests against the active live session: those explicit integration tests reset the dedicated local schema. Current live checks intentionally preserved its data. Remote CI, paid model benchmarks and new production load tests were not executed in the live stage.

## Submission

Submit the GitHub source link or clean ZIP, the illustrated overview, 3.5-minute walkthrough, and approved sourced HTML/CSV sample. The supplied handout does not require hosting. The walkthrough has captions and an offline-generated voiceover; a separate script is supplied for your own narration. It shows persisted live results, not another paid run. No deployment or competitor contact has occurred.

Start with [illustrated overview](../submission/Lather-Lens-Overview.pdf), [3.5-minute script](VIDEO_SCRIPT_3M30.md), [live results and exact checks](LIVE_PILOT_RESULTS.md), [requirements traceability](REQUIREMENTS_TRACEABILITY.md), [architecture](ARCHITECTURE.md) and [provider-neutral benchmark](MODEL_BENCHMARK.md). Historical stage documents remain locally preserved; the submission includes only selected relevant documentation.
