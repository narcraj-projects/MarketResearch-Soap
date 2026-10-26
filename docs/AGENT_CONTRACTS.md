# Lather Lens agent contracts

## B13 independent grading and human adjudication

Agents continue to emit unreviewed evidence only. Mechanical graders inspect actual owner-scoped snapshots, typed attempt outcomes, exact-replay enforcement, request/decision hash bindings, arithmetic and workflow partial orders. The fixed D04/D05/D06/D10/D12 cohort cannot be replaced by convenient passing cases. Only authenticated report owners explicitly granted trusted reviewer/business-owner roles can submit hash-bound human receipts; demo_fixture receipts are never real judgments. Human support requires atomic-component/relevance/attribution/date/item/contradiction/medical review, independent of the original agent labels. None is manufactured in this stage. Sanitized traces exclude raw inputs/source text/credentials/identities and require separate approved export. See EVALUATION_SPEC.md and actual results in EVALUATION_REPORT.md.

## B12 recorded handoff and recovery

Agents cannot authorize chaos: the server queues a pinned separate DEMO plan, and every execution boundary verifies test policy. Search/retrieval retries retain the same logical operation and advance attempts; completed results reload from the owner journal without double charging. Analyst fixture output is bound to a frozen evidence input hash and all versions, validated as AnalysisDraft, with one schema repair. The real independent rule Reviewer sees the arithmetic defect and uses the existing one-revision correction path. These synthetic fixtures do not supply model-quality evidence or a semantic support adjudication. Final approval remains an exact owner/version/hash decision. Process recovery reuses identical completed lane/source records. See CHAOS_SPEC.md and actual CP/CI/UI-CHAOS results; no live model/role selection or next stage.

## B11 history handoff

The historical comparator is deterministic processing, not another autonomous agent. It consumes exact approved frozen report versions, matches explicit stable host/name and SKU/variant identities, preserves both source observation sets and emits reasoned new/changed/source-reported gone/unknown/stale/unchanged rows. It never infers a launch/retirement from a missing source, selects a provider or retrieves new data. Optional extracted offer availability is an attributed claim; wrong item/aggregate offers are excluded. No hypothesis is promoted to a changed market fact. HISTORY_SPEC.md defines version/time/approval contracts; no following stage enabled.

## B10 report handoff

The Analyst service freezes typed ReportSnapshot (report-presentation-1.0) beside AnalysisDraft before report hashing. Existing independent Reviewer still assesses raw evidence and binds its receipt to the complete report hash. Presentation adds citation diagnostics, immutable source/brief/shortlist metadata and premise-based categorical positioning; it cannot claim semantic support or human approval. Human decision binds owner/run/request/version/hash; worker save verifies again. UI/export consume this saved artifact through report/workspace DTOs; exports cannot trigger an agent or retrieval. See REPORT_SPEC.md and ADR 0011. No model/provider chosen and no subsequent stage started.

## Current B09 Analyst/Reviewer handoffs

`harness/analysis_types.py` is the implemented analysis-1.0 handoff: owner-scoped EvidencePack from immutable research, source-backed findings, normalized prices, comparison fields, conditional hypotheses and independently persisted ReviewResult. Analyst uses a declared deterministic rule baseline; no vendor/model is selected. Reviewer rebuilds source observations independently, never calls Analyst.analyze, and recomputes arithmetic rather than accepting its values. Four epistemic kinds are fact/source_claim/interpretation/hypothesis; legacy storage's competitor_marketing_claim maps to attributed source_claim in analysis. No agent can grant human approval or mark semantic support as adjudicated. Correction consumes a hash-bound review and edits named rows/sections only. See ANALYSIS_SPEC.md and actual results in ANALYSIS_STAGE_RESULTS.md. Older skeleton/inventory notes below are historical.

# Current workflow adapter boundary

B08 compiles typed `WorkflowState` through validate/discover/shortlist-review/research/normalize/analyze/review/revise/final-approval/save with conditional terminal paths. Trusted identity and lease live outside client/agent state. Existing Scout and independent Researcher use their prior version-pinned gateways/journals. Analyze/review presently emit and check a clearly labeled DEMO evidence inventory, not a selected LLM or semantic-support certification. Revision rebuilds only from authoritative evidence and has an enforced bound; it cannot fabricate missing opportunities. Human request_changes stops partial pending a separately implemented edit flow. See WORKFLOW_SPEC.md for exact node/resume contracts and deferred B09 quality responsibilities.

## Implemented independent Researcher

Up to three approved competitors now run independently through ResearchGateway; the agent does not access a provider or SQL adapter directly. Products/offers and observed fields retain source/quote/hash/locator attribution; unknowns are null, marketing claims flagged, contradictory observations preserved. ResearchState provides scoped lane/cache/save/finish boundaries; ResearchStore resolves actual owner-bound approval and stored sources before publication. Source/claim semantic support remains unreviewed. See RESEARCH_SPEC.md and RESEARCH_STAGE_RESULTS.md; Analyst/Reviewer remain later work.

## Implemented Scout contract

The deterministic Scout now ranks a source-backed pool using five fit dimensions with explicit unknowns/quotes, selects up to three and records insufficiency/exclusions. Discovery and DiscoveryArtifact validate selected identity/IDs; publication rebuilds from the persisted brief and search journal. No LLM/vendor is selected and no model output grants evidence support or human approval. SCOUT_SPEC.md documents the conservative English/soap baseline, durable review boundary and actual limitations; SCOUT_STAGE_RESULTS.md records execution. Other agent handoffs below remain skeletons.

Version 1.0 proposal. Typed skeletons live in backend/app/harness/agent_schemas.py. No agents, prompts or model calls are implemented. Input/output always passes schema validation and then provenance/ownership/domain validation before persistence or handoff.

## Common envelope

AgentInput = RunContext + role + input artifact UUIDs. Context is trusted server-loaded state; role must match worker node, allowlist and phase. References must exist under the same owner/run and pinned schema/prompt/tool/model versions. Current skeleton validates shape only; reference resolution and role-node binding remain future service checks. Outputs inherit schema_version=1.0 and forbid extra fields. No agent output can grant human approval or trusted evidence adjudication.

| Role | Input artifacts | Output | Mandatory semantic/service checks |
| --- | --- | --- | --- |
| Scout | Validated brief, discovery tool results | ScoutOutput selected candidates (up to three), evidence/rationale, insufficiency reason when fewer | Search-backed candidate identity; five fit dimensions; full candidate pool stored separately; no invented quota fill; zero candidates routes to clarify/stop |
| Researcher | Approved shortlist version, competitor task, prior completions | ResearcherOutput competitor ID, sources, field observations and limitations | Same approved competitor; cover brand/product/variant/price/weight/ingredients/claims/positioning/audience/channels/packaging/feedback/news; source refs/date/hash; missing explicit |
| Analyst | Validated evidence and price observations | AnalystOutput typed claims, up to five Opportunity objects and shortfall reason | Every factual assertion retained/measured; comparable arithmetic; conflicts preserved; opportunities evidence/rationale/benefit/assumptions/next step; fewer than three is flagged insufficiency |
| Reviewer | Exact draft version/hash, evidence and deterministic check results | ReviewerOutput ready_for_human/revise/unresolved, flagged claim IDs and limitations | Check source support, freshness, arithmetic, completeness and claims independently; ready_for_human is not human approval; bounded revisions |
| Orchestrator | Trusted run/checkpoint, node outputs, pending decisions | Trusted conditional transition/event, not model-generated approval | Sufficiency, clarification, both approval gates, fan-out/join, retries/deadlines, cancellation/recovery; no tool dispatch of its own |

Source records require public URL syntax, title/publisher, aware retrieval timestamp, status and hash for success. Retrieval restrictions remain gateway responsibilities. FieldObservation requires either value with evidence or reason-coded unavailable, never both. These skeleton values are text; production PriceObservation must use Decimal amount, currency, total pack grams, SKU/variant, source/dates and deterministic math. The current slice does not normalize prices.

Candidate/observation/agent claim evidence uses UnreviewedEvidence. Agents cannot output supported/contradicted labels or human adjudicator identities. Trusted evidence-review service imports signed/owner-scoped human/golden adjudication into EvidenceLink records later; schema validation alone cannot authenticate that service. Analyst may produce unsupported claims for review/measurement, but those remain in the factual denominator and cannot silently become supported.

Fact, interpretation, hypothesis and competitor_marketing_claim are distinct. Attributed marketing has a factual component (brand said X) and is counted when material; support for that attribution does not prove X clinically effective. Compound claims must be atomized before scoring. Missing-data notices only leave the factual denominator when they make no material assertion about the product. Claims cannot be retyped as hypotheses to conceal unsupported factual premises; Reviewer/human audits classifications.

## Handoff failure behavior

- Malformed or unknown-version output: schema error; bounded repair through gateway; then invalid limitation, not fabricated replacement.
- Unknown/cross-owner reference, invented candidate, quote/hash mismatch: reject handoff and preserve previous successful work; no silent repair of facts.
- Missing field: retain explicit unavailable reason and attempted source status; do not infer ingredients/weight.
- Conflicts: retain observations and ask targeted review; never overwrite to make comparison easier.
- Reviewer rejection: targeted bounded research/synthesis revision or safe partial draft with limitations; no automatic final approval.
- Restart: stable operation IDs and versioned checkpoints; same operation not replayed after committed completion, except uncertain external-response crash window documented in HARNESS_SPEC.md.

All outputs/fixtures shown as examples must visibly carry DEMO. None constitutes a real competitor report or achieved BRD acceptance target.
