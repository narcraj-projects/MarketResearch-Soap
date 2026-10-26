# Lather Lens — submission overview

Lather Lens helps a handmade-soap founder compare source-backed competitors in a web app, handing off to the founder at shortlist and final-report approval. It replaces repeated searching, tab switching, manual extraction and comparison with a durable research workflow. No measured time saving or owner usefulness score is claimed.

## Assignment mapping

The supplied Project 3A handout asks for Tavily-based competitor discovery, fresh web/news gathering, extraction of pricing/features/positioning/news, orchestrated structured briefings, sample output for two or three competitors, and a demo recording plus GitHub link or ZIP. A hosted deployment is not specified. Original BRD targets remain separately authoritative; the handout does not authorize fabricated evidence or relaxed approvals.

| Role | Work | Boundary |
| --- | --- | --- |
| Scout | Tavily search, model-assisted retail competitor selection, provenance and relevance checks | No invented identity/source; up to three, fewer with a reason |
| Researcher | Independent public HTTPS, robots/redirect checks, product/news searches, model-assisted evidence digests | Source URL/time/hash/excerpts retained; missing stays missing |
| Analyst | Deterministic product/price normalization plus model-assisted positioning and opportunity hypotheses | Same-SKU/pack/weight required for price per 100g; no invented figures |
| Reviewer | Independent code arithmetic/evidence checks and separate model critique | Model critique is not human truth certification; unresolved blocks final approval |
| Orchestrator | Typed LangGraph routing, parallel work, bounded corrections, interrupts and persistence | Deterministic coordination, not an additional paid LLM persona |

## Architecture

Next.js App Router/TypeScript/Tailwind presents Brief, Shortlist, Live Run, Report and History using the original forest/lime design. FastAPI/Pydantic handles owner-protected APIs. Supabase Auth/Postgres, SQLAlchemy/Alembic, owner RLS, generation-fenced worker leases and Postgres checkpoints retain completed work and approval state. The harness validates tools, inputs, budgets, deadlines, sources and versions. Domain roles use a provider-neutral model port; the explicitly approved pilot profile uses Fireworks provisionally, not as a benchmark winner.

## Honest status and limits

Recorded DEMO execution has a substantial offline/security/recovery test suite and separate historical measured results. The 26 October live pilot is a new, one-run path; read LIVE_PILOT_RESULTS.md for its actual outcome and untested areas. A successful Tavily request is not evidence that the entire model workflow has passed. No synthetic sample may be labeled live.

The model-quality benchmark is designed but final model selection is not completed. Real material-claim support and five business-owner usefulness ratings remain unmeasured. The pilot budget is separately capped at ten Tavily credits and USD5 model usage; dollar reservations are conservative upper bounds, not invoices. Full production readiness, hosting, retention/deletion policy, backup restoration and distributed abuse limits are not claimed.

Facts, source claims, interpretations and hypotheses are distinguished. Overall claim coverage remains unmeasured when model prose has not been atomized and adjudicated. An intact quotation or working link does not prove entailment. Website failures become unavailable/unknown, never invented prices or discontinued-product claims.

## Submission contents

Submit the source ZIP or your own GitHub repository link, the walkthrough recording, and the actual sourced sample output once approved. Keep private `.env`, local Auth tokens, caches and account/credit screenshots out of the submission. Demo recordings must state whether they show a current live call, persisted live results, or controlled DEMO replay. No publishing or deployment has been performed.
