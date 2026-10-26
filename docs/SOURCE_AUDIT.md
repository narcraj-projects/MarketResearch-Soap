# Lather Lens source audit

Stage 0, 25 October 2026. Status: source review complete; application implementation has not begun.

## Authority and source locations

The requested short names are aliases for the supplied files. Preserve the originals unchanged.

| Requested name | Supplied file | Authority |
| --- | --- | --- |
| docs/BRD.docx | docs/Agentic_Market_Research_Agent_BRD_Handmade_Soap.docx | Business requirements, acceptance targets, scope |
| docs/claude-ui.html | docs/Soap Market Research Agent — UI.html | Visual fidelity and interaction reference |
| docs/PRD.md | docs/Lather_Lens_PRD_v1.1.md | Proposed implementation details, subordinate to BRD |

The BRD was read from its WordprocessingML, including table content and all 16 numbered sections. The PRD was read in full. The HTML contains five gzip/base64 bundled pages: each was decoded and its inner template and interaction logic inspected as text. No reference JavaScript was executed. Visual rendering has not yet been verified; that belongs to the UI stage.

## Required interpretation

- Discover three competitors when evidence permits; fewer is valid when evidence is insufficient. Never fill a quota with invented entities.
- Offer three to five grounded opportunity hypotheses when supported; explain shortfalls rather than generate unsupported ideas.
- BRD permits shortlist review when needed; PRD and HTML strengthen this to a required shortlist approval. Implement both shortlist and final-report gates.
- UI counts, fit scores, progress, prices, source IDs, timestamps, 94% coverage and example failure logs are design examples. They are not evidence or measured results. Any retained synthetic content must visibly say DEMO.
- HTML says three retries and shows retrying a blocked site. Proposed policy: initial attempt plus at most two retries for transient timeout/429/5xx; do not retry access denial to bypass restrictions. Record inaccessible pages and use another permitted public source. UI must display actual configured attempts.
- Missing weight means null price per 100 g. Pack arithmetic must use the same purchasable SKU. Preserve conflicting dated observations.
- The history label “gone” means not found on a dated re-check, with uncertainty; it does not prove discontinuation. “Latest” does not establish freshness for fields not re-checked.
- PRD's indicative own-business price is unverified owner reference. No own price chart until price, currency and comparable weight are supplied.
- Five crew characters represent Orchestrator plus four logical agent roles; they do not require five independent model calls.

## Acceptance targets from BRD section 12

| Target | Measurement requirement | Current status |
| --- | --- | --- |
| Three relevant competitors when sufficient evidence exists | Evidence and selection rationale per candidate; explicit insufficiency | Not evaluated |
| At least 90% material factual claims source-linked | Count usable supporting evidence; measure adequacy separately | Not evaluated |
| Required comparison fields populated or unavailable | Explicit missing states, never numeric zero substitutions | Not evaluated |
| At least 4 of 5 reports useful to owner | Five actual reports and recorded owner ratings | Not evaluated |
| At least 4 of 5 designed failures handled | Predeclared five-case cohort and recorded actual behavior | Not evaluated |
| Interrupted run resumes without losing completed work | Persisted checkpoint and completed-result comparison after restart | Not evaluated |
| No knowingly fabricated final facts | Fixture provenance checks plus review of actual reports | Not evaluated |
| Human review before external business action | Final review gate; external actions remain excluded | Not evaluated |

Source coverage and data completeness must remain separate. Deterministic fixtures cannot establish live research quality or owner usefulness.

## Working constraints

Build only in this workspace. Do not modify the Petite Batch staging site or its repository. Do not spend credits, provision, publish, deploy or contact competitors without explicit approval. Never place secrets in source, fixtures, reports or logs. No live search/model/LangSmith traffic is authorized. Model and search adapters default to offline replay. Cloud SDK construction must not imply permission to transmit.

No Git repository or existing application files were found in the workspace during this audit. No dependencies were installed. Supplied credit screenshots are not authorization to spend credits.

## Review gate

Stage 0 ends with source validation and this audit. After user review, Stage 1 will implement the smallest offline Python harness slice: typed run/tool/evidence contracts, deny-by-default policy, bounded execution and deterministic fixtures. FastAPI, LangGraph, Next.js TypeScript, Supabase Postgres, Tavily, configurable model adapters and opt-in LangSmith remain the selected stack; integration follows in separately reviewed stages.
