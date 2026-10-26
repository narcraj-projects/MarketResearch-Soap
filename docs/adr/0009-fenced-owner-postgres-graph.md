# ADR 0009 Owner-protected graph checkpoints and fenced execution

Status: implemented for this local replay stage, pending user review. Date: 25 October 2026. Refines ADR 0002 without changing the original BRD targets.

Context: Existing Scout and Researcher persist evidence and approval records, but have no graph checkpoint or worker lease. An upstream PostgresSaver created with default setup would not automatically satisfy this repository's forced owner RLS or atomic generation fencing. Memory checkpoints cannot recover after a process restart.

Decision: Implement a synchronous LangGraph BaseCheckpointSaver using two Alembic-managed owner/run-scoped Postgres tables, whole snapshots and pending task writes. Use a strict non-pickle serializer, root graph namespaces and pinned graph version. Keep source/result journals authoritative for completed effects. Keep the existing independent ThreadPoolExecutor research lanes inside one graph node, and reconcile their immutable completed artifacts on re-entry.

Managed jobs opt in on a fresh run, carry immutable replay configuration/deadline, and are claimed by owner-scoped non-bypass workers with database-clock leases, heartbeat and monotonically increasing generations. Managed store/checkpointer writes and pre-dispatch checks require the active fence. Commands/approval transitions lock in the same run-then-job order. Persisted decisions resume actual LangGraph interrupts; graph input alone cannot approve. Final approval queues save rather than completing a managed run directly.

Alternatives: An unfenced saver would allow a stale worker to overwrite progress after takeover. A separate credential/queue service would add unmeasured operational dependencies. Upstream PostgresSaver remains a possible future replacement only with equivalent RLS/fence/migration tests. LangGraph Send/subgraphs could move fan-out into graph tasks later; the current lane journals already provide independent commit/recovery without copying competitor evidence into shared state.

Consequences: Maintain a small custom saver and its runtime-compatibility tests. Only root synchronous graphs/full snapshots are supported; no runtime deletion/forks/delta channels. Snapshot storage is larger. 0005 downgrade refuses live leases and deliberately removes graph checkpoints/lease metadata, so it is an explicit rollback with lost resume positions, not lossless graph recovery. Domain sources/reports/approvals remain. Restore/replay plans and retention policy need review before production.

Boundaries: Analysis and review nodes use an honest DEMO evidence inventory/mechanical review to verify orchestration. They do not satisfy strategic analysis, genuine-support coverage or owner-usefulness requirements. Rejected/request_changes human decisions stop partial; a feedback-edit loop is deferred and visible in WORKFLOW_SPEC.md. All live tools and tracing remain disabled. No model/provider is selected.

Verification: W01..W18 as enumerated in WORKFLOW_SPEC.md, including actual lost-process recovery in parallel research and both durable gates. Read WORKFLOW_STAGE_RESULTS.md for executed counts, commands, failures corrected and remaining gaps. Do not infer cloud readiness or business acceptance from local fixture results.
