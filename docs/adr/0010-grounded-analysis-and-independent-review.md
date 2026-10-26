# ADR 0010 Same-item normalization and separate analysis/review responsibilities

Status: implemented locally for this stage, pending user review. Date: 25 October 2026. Original BRD targets remain unchanged.

Context: B08 exercised orchestration using a DEMO evidence inventory and mechanical citation checks. Its database generated a unit price whenever raw total weight existed, without an explicit same-item eligibility record. B09 requires attributable normalization/comparison/hypotheses and independent validation without selecting a provider or spending credits.

Decision: Introduce versioned provider-neutral typed handoffs, a raw-source evidence catalog, deterministic same-SKU/variant/offer/weight normalization, a conservative comparison/opportunity baseline, and a separate Reviewer. The Reviewer shares raw evidence verification infrastructure and the declared proposal contract, but does not call Analyst.analyze or reuse its arithmetic outputs. It independently recomputes arithmetic and checks each draft against immutable input. It never assigns human approval or genuine semantic-support status.

Only eligible price rows enable Postgres computed price-per-100g. Migration 0006 preserves legacy raw records, suppresses unverified old normalized values and refuses unsafe downgrade. No automatic evidence backfill or forced rollback deletion occurs. The dedicated disposable local rollback test explicitly handles its DEMO cohorts; it cannot authorize production deletion.

Five versioned proposal rules can return three to five hypotheses when their narrow evidence triggers hold; fewer is explicit insufficiency. Facts are listing observations, source claims are attributed, interpretations retain premise IDs and uncertainty, and hypotheses require assumptions/next steps. Medical/certification claims are not established by advertising or reviews. A 30-day default freshness input is a proposed policy, not a changed business acceptance target.

Corrections target named rows/sections in the same frozen evidence pack and remain bounded. Prior drafts and independently version/hash-bound review receipts persist immutably. Unresolved or malformed drafts stop partial before final approval; warning-only gaps remain visible. Graph version becomes workflow-1.1; old checkpoints are not silently reinterpreted. Model/provider remain none; no cheapest-provider selection, model benchmark or paid call occurs.

Alternatives: Merely checking arithmetic cannot detect wrong-item weights. Counting links cannot prove source support. Asking the Analyst to grade itself would collapse distinct responsibilities. Unbounded reruns or padding opportunities would conceal missing evidence. A general LLM strategist/reviewer can later implement the same boundary only after the reviewed quality-first benchmark and separately approved calls.

Consequences: Current strategy is constrained to inspectable templates and sampled comparisons. Independent human source-truth adjudication and owner usefulness remain necessary; genuine-support coverage stays null. Schema/quote/price success is not a model-quality result. No new UI/export/history or deployment is included. See ANALYSIS_SPEC.md and ANALYSIS_STAGE_RESULTS.md for exact tests, commands, actual results and limitations.
