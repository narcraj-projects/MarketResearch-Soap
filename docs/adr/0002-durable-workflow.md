# ADR 0002 Durable worker and versioned approvals

Status: proposed for review. Date: 25 October 2026.

Context: FR-09 and A06 require completed work and pending approval to survive interruption. HTTP request lifetime and in-memory conversation do not satisfy that requirement. FR-08 requires human review.

Decision: FastAPI persists commands/jobs; separate worker leases runs with fencing generations. Supabase Postgres stores domain state, completion journal, events and LangGraph checkpoints. Operation IDs deduplicate committed results. Resume reconciles the completion journal with checkpoints. Approval decisions bind authenticated owner, run state and artifact version/hash, with transactional idempotency. Approval freezes a report snapshot; drafts are durable beforehand.

Alternatives: request-bound tasks risk loss on restart; memory-only checkpointing fails FR-09; client-only approvals permit bypass. A separate queue service is deferred until measured need justifies it.

Consequences: worker lease and crash-boundary tests are mandatory. Database transactions must remain short around network calls. Remote response-before-commit failures can repeat read calls/billing; exactly-once external execution is not promised. Uncertain operations retain conservative budget accounting. Elevated worker credentials never substitute for ownership checks.

Verification planned: D13/D14/D17, T08, S01. Both shortlist and final gates are proposed mandatory controls, stronger than BRD's conditional shortlist wording. This interpretation awaits review.
