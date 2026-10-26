# Lather Lens provider neutral model implementation plan

Documentation-only plan, 25 October 2026. No model code, benchmark runner, dataset, paid execution or deployment is added now. The user decision establishing provider neutrality and quality-first selection is accepted; interface/scoring mechanics remain proposed for review. Each future step stops for review and requires a separate instruction.

## Planned architecture

Domain agents and LangGraph nodes depend on a ModelAdapter protocol owned by the harness, never on vendor SDK response types. A provider registry resolves an explicitly configured model profile. No default Fireworks/Nebius/OpenAI model and no automatic cheaper fallback. Supporting an OpenAI-compatible transport does not make the OpenAI SDK or API semantics the domain contract; provider-specific behavior stays inside its adapter.

Proposed neutral request: operation/run/role/profile IDs, versioned prompt/messages and evidence references, expected output schema, canonical tool specs, evidence-envelope/output constraints, deadline and generation parameters. Proposed response: typed structured content or typed invalid/refusal/error, canonical tool intents, resolved provider/model/revision, finish reason, actual usage/known cost or explicit unknown accounting, response artifact hash and adapter version. Vendor-specific content/credentials remain private to adapters. Parsed JSON never means semantically supported evidence.

Canonical tool intents return to the harness for schema/allowlist/approval/URL/budget checks; a provider SDK cannot execute tools directly. Search stays Tavily behind its own interface. Deterministic normalization and human final approval never become model responsibilities. Refusal, malformed output, timeout and rate-limit normalize explicitly without converting failed research into invented content.

ModelProfile binds role(s), provider key, model/revision, adapter version, neutral prompt/schema/tool versions, generation limits, capability declaration and benchmark evidence ID. Secrets are references resolved server-side, not values in profiles/events/checkpoints. Routing configuration is explicit/versioned and may use different evaluated profiles per role. No profile becomes production-eligible without reviewed benchmark evidence. Failover must be separately evaluated and authorized; any switch records profile provenance and rechecks quality/budget rather than silently downgrading.

## Current gaps and ordered work

| Step | Smallest coherent future change | Verification and dependency |
| --- | --- | --- |
| M01 | Review quality audit/benchmark specification; prepare and human-annotate frozen calibration/holdout evidence without inventing real research | Validate task coverage, source permissions/hashes, splits, all five rubrics and original BRD targets; no paid calls |
| M02 | Implement neutral ModelAdapter request/response/capability interfaces and offline fake/replay implementations | Contract conformance, refusal/error/schema/repair/tool normalization tests; domain/graph imports no vendor SDK; depends reviewed M01 architecture |
| M03 | Version model-profile manifest and per-operation provenance; migrate replay/event/checkpoint schema explicitly | Current Versions v1.0 has one provider/model tuple; replace/extend through a reviewed schema version and migration/quarantine tests, never mutate frozen 1.0 silently |
| M04 | Implement offline benchmark runner and scoring/annotation ingestion, paired task-level comparison and reports | No live fallback; blind labels; citation presence != entailment; failed tasks retained; sample counts/seeds/versions correct; no invented baseline |
| M05 | Add isolated concrete adapters only for an explicitly approved candidate matrix | Verify current capabilities locally/official docs in approved scope, conformance and secret handling; construction/import must not transmit; no preferred vendor |
| M06 | Prepare reviewable experiment budget/configuration and request explicit paid execution approval | Declare call count/retries/evidence policy/monetary cap and telemetry separately; configuration is ready before approval; no approval inferred from credits |
| M07 | Execute approved calibration/holdout, blinded annotation and uncertainty analysis | All benchmark hard gates, five quality dimensions and real usage; no cost-weighted winner; stop if evidence inconclusive; separate approval and review |
| M08 | Propose role profiles and validate full configuration on approved real-report/end-to-end evaluation | All eight BRD application gates including owner five-report usefulness and durable recovery; final selection only with reviewed evidence |

M01–M04 can be developed offline in later separately authorized stages. M05 does not authorize network transmission; M06/M07 need explicit scope/budget approval. Application scaffold/auth/UI/durable worker order in BACKLOG.md is retained; these steps add dependencies before live integration and final model selection, not permission to skip harness/database/review gates. No deployment work begins under this plan.

## Budget handling

Budget/deadline policy remains an authorization boundary. Optimize research quality inside approved caps; if the best evaluated profile exceeds the cap, stop and disclose the constraint rather than choosing lower quality invisibly. Keep cost/latency as diagnostic operational data, outside quality score. Record unknown usage conservatively; no free-call assumptions. Specific models, providers, ceilings and current pricing are deliberately unresolved until approved evaluation preparation.
