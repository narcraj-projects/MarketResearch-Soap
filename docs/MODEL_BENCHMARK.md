# Lather Lens model quality benchmark design

Version 1.0 proposal, 25 October 2026. Benchmark NOT implemented or executed; no dataset records, model scores, baseline, winner or provider recommendation is claimed. Research quality takes priority over API cost. This design must be reviewed before candidate evaluation or final model selection. No paid calls, external research or deployment now.

## Objective and separate evaluation tracks

Evaluate factual accuracy, citation grounding, competitor relevance, extraction reliability and strategic analysis quality. Permit different evaluated models by role, or one model if evidence supports it; never predetermine a vendor. Fireworks, Nebius and OpenAI receive no special default or ranking advantage. Provider/model eligibility is verified later in approved scope, not inferred from credits or API compatibility claims.

Track A is deterministic harness replay D01–D17: verifies policy/recovery/contracts, not model reasoning. Track B is controlled model evaluation on identical frozen evidence/tool transcripts, isolating model quality from search differences. Track C is later approved end-to-end real research with dated sources and owner review, measuring model/search/orchestration interaction and all BRD gates. A Track B winner alone is not a release-ready application.

## Dataset design and preparation

Proposed model-quality dataset LL-MQ-v1: 60 tasks, 12 per dimension below. Each dimension uses four calibration tasks and eight untouched holdout tasks, totaling 20 calibration and 40 holdout. Split by source/brand/SKU families, not just question, to prevent near-duplicate leakage. Specify cross-role applicability before scoring; role specialists are evaluated on applicable strata, and the proposed full routing configuration is evaluated across all five dimensions.

Each task records ID, dimension/role, brief, frozen evidence pack/tool transcript, source provenance/access/date/hash/excerpts, expected atomic facts or relevance labels, missing/contradictory fields, acceptable uncertainty, forbidden assertions, rubric, annotation provenance and split. Synthetic records are labeled DEMO with reserved example domains. Synthetic/adversarial cases test behavior; realistic public snapshots or owner-provided evidence are required before final quality selection. Those snapshots must be supplied or collected later with approval and access restrictions; none are invented here.

Two human reviewers independently annotate facts, support and relevance from source evidence; resolve disagreements before freezing holdout. Freeze dataset/hash, rubrics, prompts, normalization policy, repair budget, scoring and selection rules before opening holdout outputs. Keep holdout reference answers outside candidate context. Audit public dataset familiarity/leakage risks. Calibration permits prompt tuning; holdout failure prompts require a new version/unseen holdout, not repeated tuning on the same answers.

## Dimensions and proposed metrics

All weights/thresholds here are proposed benchmark rules for review, not BRD amendments or measured results. Scores normalize to 0–100; report per-task and per-stratum results, denominators and abstention/completeness alongside aggregate.

| Dimension | Weight | Measurement and negative controls |
| --- | --- | --- |
| Factual accuracy | 30% | Correct atomic factual assertions / all asserted factual assertions against trusted reference. Report assertion count, omissions and uncertainty; penalize incorrect dates/currency/SKU/ingredient/certification/medical claims. Empty assertion set is unavailable, not perfect |
| Citation grounding | 25% | Material factual assertions with usable, scope-correct supporting excerpt / all material factual assertions. Separately report citation presence and provenance/quote validity. Include authentic but irrelevant citation, contradicted quote, wrong pack/date and marketing-as-efficacy controls |
| Competitor relevance | 15% | nDCG@3 over fixed candidate pool using independently annotated five-dimension relevance grades; report precision@3, invented/unsupported entity count and insufficient-evidence behavior. Missing expected slots are not padded. Pool tasks have enough credible labels; insufficiency tasks use explicit decision accuracy separately |
| Extraction reliability | 15% | Field-level evidence-backed precision/recall/F1 over normalized expected values, including missing and conflict statuses; normalize currency/weight/pack deterministically and compare Decimal arithmetic exactly. Report first-pass schema validity and repaired validity separately; schema-valid fabrication is wrong |
| Strategic analysis | 15% | Two blinded humans rate grounded comparison, useful differentiation, rationale/benefit, assumptions/uncertainty and practical next step from 0–4; average normalized to 100. Audit factual premises separately. Unsupported confidence cannot score as insightful strategy |

Strategy anchors: 0 absent/fabricated/contradictory; 1 generic or weakly grounded; 2 partly supported with material gaps; 3 well grounded and practical with explicit assumptions; 4 strong comparative reasoning, testable differentiation and clear limitations. Adjudicate disagreement of more than one point before final score; report raw reviewer agreement. Owner usefulness A04 stays a separate actual-report gate.

## Citation presence is not genuine support

First verify the cited source exists in the frozen pack, correct owner/run/source ID, hash and exact excerpt membership. Then verify entity/SKU/pack/time/claim scope. Human reference adjudication determines whether the evidence entails each atomic assertion. A source link plus accurate quote can still be irrelevant or support only part of a compound claim. Marketing evidence supports 'brand claims X', not X's efficacy. Count material attribution claims; inspect factual premises even when output labels them hypotheses. Unreviewed/insufficient/contradicted support cannot earn grounding credit. Current claim_metrics only counts trusted labels and is not this adjudicator.

## Fair comparison protocol

Freeze identical task evidence and vendor-neutral prompt semantics. Use a declared common evidence envelope that all admitted candidates can consume without dropping relevant content; report envelope limits. If capacity is insufficient, mark candidate ineligible for that task/configuration, not silently truncate it. Maintain a separately reported larger-context track if needed. Provider token counts are not directly interchangeable: compare the same evidence and output requirements, while recording actual tokens and limits per adapter.

Require same output schema, canonical tool definitions, timeout policy and repair allowance. Report native schema/JSON output and adapter repair separately. No provider gets undisclosed retrieval, extra context or repeated human correction. Retry transport failures within fixed bounded policy; count semantic failures even if a later repair succeeds. Missing/failed outputs remain in applicable task denominators, never dropped to improve averages.

Randomize/blind output labels and assessment order. Proposed three independent repetitions per task/candidate configuration: 180 primary model invocations for 60 tasks before retries/repairs. This is a future experiment size, not authorization or an executed count. Temperature zero/seed when supported is recorded but does not guarantee deterministic provider output. Preserve exact model revision, adapter version, role profile, prompt, parameters, dataset/evidence hashes, response artifact and usage for every call. No model-as-judge calls are authorized now; future supplemental judging must not replace human/deterministic gates.

## Selection procedure

1. Before calls, approve dataset/rubric/candidate matrix, maximum experiment invocations/retries and monetary ceiling. Capability/privacy/access requirements are eligibility constraints, not quality points. If budget cannot cover the approved design, stop and request a revised experiment; never silently substitute a cheaper model.
2. Run calibration then freeze prompts/configuration; evaluate blinded holdout with independent annotations. A candidate routing configuration must pass absolute critical controls: no invented controlled competitors, fabricated sources/certifications/medical efficacy, unauthorized actions or approval bypass. Any critical violation blocks selection pending investigation and new reviewed evaluation.
3. Proposed quality eligibility: factual accuracy >=95%, genuinely supported material facts >=90% (preserves BRD floor), each other dimension >=75/100, applicable extraction schema/pack/arithmetic critical cases correct, and all required tasks produce evaluable outputs. Report uncertainty; passing a point estimate is not a claim of general accuracy. These thresholds need review and do not relax BRD A07.
4. Rank eligible full configurations by the five weighted QUALITY scores. Cost and latency are recorded in separate columns and contribute zero score. A cheaper candidate cannot beat a demonstrably better-quality eligible candidate on cost. Compare role specialists on declared applicable dimensions and validate the assembled configuration end-to-end; no opaque composite of incomparable role scores.
5. Report paired differences and 95% task-cluster bootstrap intervals; repetitions are correlated observations, not three times the independent sample. With only eight holdout tasks per dimension, conclusions may remain uncertain. If quality differences are inconclusive, do not announce a final winner; expand a reviewed unseen holdout before selection. No cost-based tie-break silently resolves uncertainty.
6. Human reviews benchmark artifacts and later real-report usefulness before approving final role profiles. None passing means no selection; investigate prompts/evidence/tooling/candidates, version changes and rerun under approval. Re-evaluate model revision, provider, prompt, adapter, tools or routing changes against pinned regression and fresh holdout when needed.

## Budget and result reporting

Quality-first does not authorize unlimited spending or infinite repair. Hard approved caps/deadlines stay enforced; insufficient budget produces a transparent partial/inconclusive evaluation. Prices and provider capabilities must be verified later in approved scope. Never log keys or upload raw private evidence automatically; LangSmith transmission needs separate approval.

Future report must include candidate configuration manifest and status, dataset/version/split/hashes, exact commands, sample and repetition counts, raw/per-dimension quality metrics, support versus presence, failure/abstention counts, reviewer agreement, confidence limits, real latency/cost and explicit selection rationale. No model is selected in this document. Results record for this documentation-only stage is QUALITY_STAGE_RESULTS.md.
