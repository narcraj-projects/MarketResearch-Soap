# Analyst, normalization and independent Reviewer

Stage B09 only, 25 October 2026. Original BRD business requirements/targets, PRD v1.1 and decoded five-screen UI remain authoritative and unchanged. This stage does not start full report/export/UI wiring, history, a paid model benchmark or deployment.

## Plan and requirements

Implement deterministic same-purchase-item normalization, four explicit epistemic kinds, evidence-linked comparison and conditional hypotheses. Review the resulting draft independently against raw evidence, including arithmetic, citations, medical/certification attribution, dates, missing data and contradictions. Correct only named targets within the existing revision limit; otherwise retain a flagged unresolved draft. Verify unit/adversarial/golden cases and actual Postgres/LangGraph trajectories with no live research/model calls.

Scope maps to FR-04, FR-05, FR-06 and review portions of FR-07/FR-09; D07..D12, T04..T07, A02/A03/A07 controls. Existing shortlist/final gates, budgets, fencing, cancellation and process recovery remain. Results and exact commands: [ANALYSIS_STAGE_RESULTS.md](ANALYSIS_STAGE_RESULTS.md). Architectural rationale: [ADR 0010](adr/0010-grounded-analysis-and-independent-review.md).

## Typed boundaries and versions

`harness/analysis_types.py` defines frozen, extra-forbidding, provider-neutral EvidencePack, NormalizedPrice, Finding, Comparison, PriceComparison, Opportunity, AnalysisDraft and ReviewResult models. Each handoff has `schema_version=analysis-1.0`, run identity and DEMO label where applicable. EvidencePack binds one to three unique approved competitors to unique scoped research/source records and an aware as_of time. Drafts bind the complete evidence/policy input hash. Opportunities require factual premise IDs, rationale, potential benefit, assumptions and next step; fewer than three requires an insufficiency reason, and the schema caps five.

Workflow/checkpointer version is now `workflow-1.1`; report data is `analysis-report-1.0`. New fresh workflow enrollment pins this version. Existing workflow-1.0 checkpoints are not silently replayed under new analysis semantics; migration/re-enrollment is a separate review decision. No existing reports, approvals, source snapshots or frozen migrations 0001..0005 are rewritten. No provider/model was selected; runtime provenance says provider/model=none. The quality-first benchmark in MODEL_BENCHMARK.md is still required before final model selection.

## Normalization

`agents/normalization.py` verifies the SKU, variant, offer price/currency, weight/basis and pack quantity against the same retrieved source purchase item. JSON-LD pointers and hashed quotes resolve to that product/offer; the raw body is parsed again to check the stored excerpt/structured snapshot. Visible-label extraction must match its independently reconstructed source product. Different itemOffered identity/weight/quantity, aggregate offers and unsupported quantity scope cannot establish eligibility.

An absent SKU, missing price/currency/weight, unknown basis, missing quantity for a per-bar weight, cross-source input, mismatched extracted value/offer/pack total, or out-of-storage-range result produces null plus a reason. Missing is never zero. Zero listed price is valid when the full basis is valid. No cross-page price/weight joins, variant mixing, implicit currency conversion or inferred pack count occur.

For an eligible item: total pack grams are explicit total_pack weight, or per_bar grams times the explicit pack quantity. Require the extracted total to match. Decimal arithmetic uses precision 60 and rounds positive normalized values to eight decimal places with ROUND_HALF_UP, matching Postgres Numeric(24,8). Units outside the existing extractor's disclosed-unit support remain unavailable; this stage does not guess them.

Migration 0006 adds immutable `price_observations.normalization_data` with a versioned eligible flag/proof payload. The generated database value is populated only when eligible=true. Existing legacy rows keep raw amount/weight/source/date, but their unverified generated value becomes null; no migration certifies old evidence. New ResearchStore writes carry the verified basis. Browser/API clients cannot insert price rows. SQL constraints validate the proof envelope; the trusted harness validates evidence identity. A privileged direct SQL writer is not a substitute for that harness.

0006 downgrade refuses any non-null raw total lacking eligibility, because reverting would expose an unverified normalized value. Production migration never deletes evidence to force rollback. The existing destructive local rollback test explicitly cleans only disposable DEMO fixtures, including retained test cohorts matching the exact prepare_local_auth.py email pattern, after verifying the dedicated test-instance marker. Successful rollback/reapply evidence is separate from the refusal test.

## Epistemic kinds and comparisons

| Kind | Meaning and constraints |
| --- | --- |
| fact | Atomic observation in a listing, e.g. listed SKU/price/weight. Narrative says Listed; it does not establish independent product performance or ingredient completeness. |
| source_claim | Source-reported marketing, positioning, audience, review/launch or medically/certification sensitive wording. Explicit attribution/caveat; never promoted to proven efficacy or representative demand. |
| interpretation | A bounded comparison with collected premise IDs. Current baseline includes sampled price ranges and an explicit different-products/no-market-wide-ranking/no-FX caveat. |
| hypothesis | Conditional test proposal, not a proven need, market gap or commercial result. Requires grounded premises and assumptions. |

`agents/evidence_catalog.py` reconstructs observations from raw immutable source bodies and rejects mismatches with saved extraction. `agents/analyst.py` builds side-by-side products, ingredients, prices, positioning/messaging, audience, channels, packaging, public feedback and launches. Every field resolves to finding IDs or an explicit unavailable reason. Disclosed ingredients remain disclosed lists; public reviews remain attributed individual comments, not fabricated sentiment statistics or testimonials.

Price comparisons use eligible observations for at least two competitors within one currency and the configured freshness window. They compare sampled listed per-100g values, not identical formulations or the whole market. Contradictory SKU/variant/pack/currency observations are retained together with source IDs; dated normalized observations and source endpoints retain timestamps. No silent winner is chosen. Missing retrieval never proves a competitor lacks a product or feature.

## Grounded opportunity rules

This is an explicit deterministic strategy baseline, not an evaluated LLM strategist. `analysis_policy.py` versions five allowed proposal templates and narrow trigger conditions. Those templates contain no invented market facts, clinical claims, customer counts or guaranteed gains.

| Rule | Evidence needed | Proposed test |
| --- | --- | --- |
| price_testing | A fresh eligible per-100g range differs across at least two competitors in one currency | Plan a limited offer/message test after validating unit economics and willingness to pay. |
| pack_clarity | Known and missing/different pack/weight observations across at least two sampled competitors | Test an explicit total-weight/pack-count label for comprehension. |
| disclosure | Disclosed ingredient lists differ or some retrieved listings lack usable disclosure, across at least two competitors | Test a clearer disclosure prototype against actual formulation information. |
| positioning_test | Different source-reported positioning wording for at least two competitors | Plan a blinded non-medical message/comprehension test. |
| feedback_test | Fresh, attributable public feedback for at least two competitors | Plan an experience test based on those comments, with bias/representativeness assumptions. |

Only triggered rules produce opportunities, up to five. With insufficient evidence, return fewer and explain why; do not pad the quota. Missing-data premises describe only retrieved evidence. Tests are suggestions: no customers/competitors are contacted, purchases made or content published. Broad strategy quality and owner usefulness remain unmeasured.

## Independent review and genuine support

`agents/reviewer.py` has no call to Analyst.analyze. It reconstructs the source catalog separately and validates draft identity/hash/time, atomic values, narrative/attribution, all collected unknowns, exact quotes/hashes/source/competitor scope, normalized provenance and independently recomputed Decimal arithmetic. It checks range currency/observation scope, required comparison fields, preserved contradictions and rule-specific hypothesis premises. Fixed baseline proposal narratives cannot smuggle unreviewed factual promises through a hypothesis label.

Review preserves inaccessible, missing, stale, future-dated and conflicting evidence as warnings; source medical/organic/certification wording remains attributed and flagged for human review. The pattern-based safety classifier is conservative and English-focused; it is not exhaustive medical/certification verification. Publication dates are checked separately from retrieval dates, so newly retrieved old news is not automatically recent.

Freshness is a proposed configurable input policy (default 30 days), not a BRD acceptance threshold. The service freezes the as_of time/window on first normalization; replay, human waiting and correction cannot make evidence newer. Eligibility for current sample comparisons/opportunities excludes stale/future-dated sources. Historical observations remain visible with dates.

`citation_presence` reports links on non-null material fact/source_claim observations. `quote_integrity` reports accessible exact scoped hashed excerpts. A real quote can still be irrelevant, narrower than an assertion, contradictory, out of date, or merely advertising. Golden case AN14 and test_an04 demonstrate intact citations with rejected assertions. `genuine_support_coverage` is explicitly null and `semantic_support=not_adjudicated`; no mechanical percentage establishes A02. Independent human semantic adjudication and the provider-neutral benchmark remain required for real quality acceptance.

## Targeted correction, unresolved output and durability

The default bound remains one revision, with a typed maximum of two. Review returns ready_for_human, revise or unresolved. Only repairable issues route to revision; malformed schema/input-binding blockers or exhausted corrections route directly to a partial stop. Missing/stale/conflicting/attributed-medical warnings remain visible without pretending they were repaired.

`agents/correction.py` verifies the assessment's input/draft hashes, restores only reviewer-named rows/sections from the same frozen evidence, removes unsupported assertions where no valid record exists, and records correction targets. It never retrieves new pages, changes source data/time, refunds budgets or generates replacement facts to satisfy a count. Valid unaffected sections remain equal. Corrected drafts and prior drafts are separate immutable report versions; Reviewer evaluates each independently. Repeated failures remain unresolved, and no final approval request is created for them.

`services/analysis.py` checks source/document consistency under the active owner/worker lease, freezes normalization hashes and persists immutable Reviewer receipts in existing evaluation_cases/results. These are validator receipts, not invented benchmark samples. A receipt binds report ID/hash, input hash, draft hash, reviewer version, actual decision and issues. Re-entry reuses the same receipt. The protected report API exposes it through typed `ReportRecord.review`. New managed final approval/save require a ready receipt for the exact report, in addition to existing human artifact/version/hash checks.

## Tests, limitations and review boundary

`tests/test_analysis.py` has 18 manifest-pinned synthetic golden cases plus adversarial/identity/schema/targeted-correction tests. Fixtures identify their origin as DEMO mutations of the existing verified R01 recording; they contain no claimed real prices/sources or live model outputs. `tests/test_analysis_storage_integration.py` covers actual graph correction/unresolved/malformed trajectories, immutable versions/receipts, owner API isolation, unsafe rollback protection and no extra retrieval. Existing process-restart, RLS, budgets, approval, retrieval and frontend checks are regressed. Executed commands/results are in ANALYSIS_STAGE_RESULTS.md; JUnit output is in evaluations/analysis-unit-results.xml.

Limitations: only recorded DEMO evidence is enabled; rule-based synthesis is narrower than general strategic analysis; safety patterns and mechanical evidence checks are not independent truth certification; real-source A02/A03/A04/A05/A07 acceptance and owner usefulness are unmeasured. Full report/export/UI/history, model benchmark/external retrieval, production retention/supervision and deployment remain separate stages. Stop for review before continuing.
