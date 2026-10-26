# ADR 0011 Immutable report presentation and approved local downloads

Status: implemented locally, pending user review. Date: 25 October 2026.

Context: the five HTML-faithful screens originally showed labeled synthetic previews while backend research/analysis/approvals became durable. Fixed preview metrics, chart coordinates and local approval cannot represent persisted evidence or authorize export.

Decision: freeze a versioned presentation with the report before hashing and independent review. Present owner-protected workspace/history projections through explicit BFF allowlists. Bind final decisions to owner, run, version, hash, request and independent receipt; require leased-worker save before exporting. Export deterministic escaped HTML/formula-safe structured CSV from that snapshot only. Preserve immutable rows; earlier compatible analysis artifacts use explicitly marked projections without backfill. Bump the graph pin to workflow-1.2 and reject incompatible checkpoints.

A coverage ring measures intact citations over all non-null material fact/source-claim IDs, including unsupported assertions. It cannot adjudicate genuine support. Missing chart axes/prices stay unavailable; charts never manufacture coordinates, zeroes, FX or weights. Positioning is an explicitly categorical interpretation with cited premises. Historical timelines show real metadata; semantic changes remain B11. Recorded data stays DEMO.

Alternatives rejected: client approval state, export of an unapproved draft, mutable report formatting/data, latest-source replacement, citation-presence acceptance, fabricated chart coordinates and premature historical difference claims. A separate mutable reporting cache would risk divergence from the human-reviewed hash.

Consequences: actual run screens are evidence-bound, immutable downloads are reproducible and direct URLs cannot bypass approval. No new database migration, external API/provider choice, credits, publishing or deployment. Genuine semantic support and owner usefulness remain separate acceptance evidence. Original requirements are unchanged; UI differences and exact tests are in REPORT_SPEC.md and REPORT_STAGE_RESULTS.md. Stop for review before B11.
