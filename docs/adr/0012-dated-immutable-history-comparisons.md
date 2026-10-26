# ADR 0012 Dated immutable versions and conservative history diffs

Status: implemented locally for B11, pending review. Date: 25 October 2026.

Context: reports already have immutable owner-protected rows, version/hash and exact approval. History only displayed metadata. BRD FR-09 requires repeat-run comparison and past/current separation. The HTML Gone/Not found example cannot establish a discontinuation under the evidence requirement.

Decision: reuse reports as immutable (run, version) artifacts rather than duplicate a report_versions table or backfill old data. Add paginated exact version metadata and exact version viewing. Diff only two distinct chronological approved/saved snapshots with compatible category/geography/customer. Version identity and diff contracts. Use explicit host/name and SKU/variant identities; no fuzzy matching, array-position joins or automatic rebrand aliases. Derive comparison purely from frozen report data.

Counters describe field observations. New is newly observed in the sample, changed is a supported changed observation with advancing evidence, gone is explicitly attributed first-party discontinued status. Retrieval gaps, missing fields, conflicting/cached evidence and identity ambiguity become unknown/stale. Different price currency/weight/pack basis cannot silently produce price-change claims. All source dates remain historical and no wall clock changes a past comparison. Optional listing availability is captured only with an actual quoted status and correct offer scope.

Retain reference timeline/counters/before-after cards, add real run/version controls and source dialogs. Unapproved drafts remain read-only; they cannot compare or export. Reject mismatched report presentation/run/brief/owner binding and clear failed typed projections. Invalid legacy-version metadata cannot conceal valid siblings.

Alternatives rejected: mutable report overwrite, current-data joins into old reports, a duplicate versions table, name/price similarity as identity, treating 404/omission/out-of-stock as discontinued, counting observations as proven launches and calling a model to guess missing values. No model/provider chosen and no paid call.

Consequences: reproducible local historical comparisons and explicit uncertainty, with conservative unmatched records. Reviewed aliases/domain verification and no-SKU matching remain limitations. No migration/dependency/graph-version changes, cloud resources, publishing or following stage. HISTORY_SPEC.md and HISTORY_STAGE_RESULTS.md define scope, actual tests/commands and unchanged BRD acceptance.
