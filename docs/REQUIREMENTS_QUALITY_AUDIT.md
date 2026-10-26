# Lather Lens quality first requirements audit

25 October 2026. Documentation-only stage. The user's current architectural decision is binding: prioritize research quality over API cost, retain provider neutrality, benchmark before final model selection, and make no paid API calls or deployments. Original BRD business requirements remain authoritative. Original PRD/BRD/HTML files and their hashes are preserved.

## Requirements and findings

| ID | Requirement or finding | Audit result and resolution | Verification or future evidence |
| --- | --- | --- | --- |
| Q01 | Provider-neutral LLM architecture | No provider SDK/vendor import or hard-coded vendor found in current harness. A dedicated ModelAdapter boundary is still absent; ToolGateway alone does not complete it | MODEL_IMPLEMENTATION_PLAN.md M02; future adapter conformance tests |
| Q02 | No preference for Fireworks, Nebius or OpenAI | PRD section 5 says Fireworks considered first. Current user decision supersedes that implementation preference; no preferred provider/default is selected | ADR 0005; original PRD remains unchanged |
| Q03 | Research quality before cost | Existing budgets correctly bound authorized spending. Clarify that cost cannot select a lower-quality model or cause silent downgrade | MODEL_BENCHMARK.md quality-only ranking; retain hard authorized caps |
| Q04 | Evaluate factual accuracy and citation grounding separately | Existing metric aggregator counts trusted support labels; it cannot determine truth, quote integrity or entailment | Benchmark human reference labels, atomic factual checking and negative citation controls |
| Q05 | Competitor relevance | FR-02 requires five relevance dimensions and three competitors when evidence permits, never quota fill | Fixed candidate-pool relevance ranking plus separate later discovery evaluation |
| Q06 | Extraction reliability | Current schemas constrain shape; price/weight/SKU extraction and arithmetic are not implemented | Evidence-backed precision/recall, missing/conflict/pack cases, schema and arithmetic checks |
| Q07 | Strategic analysis quality | BRD FR-05/06 require grounded comparison and three-to-five hypotheses with rationale/benefit/assumptions/next step | Blinded human rubric and unsupported-premise audit, not fluent prose score |
| Q08 | Benchmark before final selection | Existing D01–D17 specify harness workflow cases, not a multi-model benchmark | MODEL_BENCHMARK.md defines separate dataset/splits/metrics/selection; no benchmark executed |
| Q09 | Multi-role provenance | Current Versions has one provider/model/prompt tuple; this cannot faithfully record heterogeneous role routing | Future versioned model-profile manifest with per-operation resolved profile; no schema code changed now |
| Q10 | No paid calls/deployment this stage | Replay-only code and no live adapters exist; no installs, API calls, trace uploads, provisioning or deployment in this task | Local checks only; execution results in QUALITY_STAGE_RESULTS.md |

## Business requirements retained

FR-01..09 retain intake/clarification, evidence-backed discovery, public collection, comparable normalization, competitive analysis, grounded opportunities, full report, human review and durable history. Exact eight BRD section 12 targets stay in REQUIREMENTS_TRACEABILITY.md and EVAL_PLAN.md: three relevant competitors when sufficient evidence exists; >=90% source-supported material facts; fields populated/unavailable; >=4/5 owner-useful reports; >=4/5 designed failures handled; restart without lost work; no knowingly fabricated final facts; final human review before external business action.

Benchmark thresholds are proposed model-selection controls, not replacements for those application acceptance gates. A cheap candidate cannot pass through a quality failure, and a high benchmark score cannot bypass human approval, public-access policy or durable recovery. Five owner ratings on actual reports remain required; synthetic tests cannot establish that result.

## Scope limits

Audit evidence comes from local code/docs and existing source integrity checks. No current model availability, capability, pricing, relative performance or best provider is asserted. No candidate shortlist or final models selected. Planning a paid evaluation is not permission to run it. Model-interface/schema changes and benchmark implementation wait for a separately reviewed stage.
