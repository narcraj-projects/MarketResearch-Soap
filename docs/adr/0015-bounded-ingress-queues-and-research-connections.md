# ADR 0015: bounded ingress, owner queues and research connections

Status: implemented for B14 review; operating defaults and baseline pending review. Date: 25 October 2026.

Preserve BRD business targets, immutable evidence/history and both owner approval gates. Address the PRD security/load requirements without enabling live tools or changing UI design. Bound request bytes before parsing, redact validation payloads and transport logs, deny sensitive URL credentials/NAT64 destinations, and keep direct browser CORS closed behind the existing same-origin BFF. Remote plaintext Auth/backend configuration is rejected; local dedicated test origins remain supported.

Use an owner-scoped PostgreSQL advisory transaction lock to serialize queue count/admission and worker count/claim. Include all nonterminal runs in the 128-run allowance, including approval waits, so resume cannot evade the bound. Permit at most four unexpired worker leases per owner; expired jobs retain database-clock recovery and stale-generation fencing. Do not add a privileged global tenant counter or grant clients mutation rights. Local request/login valves are explicitly per process; shared edge/account controls are deferred operational work, not a solved fleet limit.

Concurrent recorded runs exposed pool starvation: lane session locks retained every connection while needing another connection to save work. Share a three-slot semaphore across ResearchStore instances using the same engine; acquire before taking a session lock and release on all exits. Wait at most ten seconds or the remaining deadline, then fail with a capacity reason. Reserve other pool connections for short transactions, checkpoints and heartbeat. Keep pool bounds explicit, measure rather than presume throughput, and retain the initially failing test artifact.

Extend golden execution fingerprints to security/Auth/queue/lease/storage code. Keep old proposed baselines immutable; record and independently compare a new proposed revision after the code is frozen. Do not downgrade version drift into success or promote baseline review automatically.

Do not invent retention periods or silently delete durable evidence. No destructive retention action, provisioning, hosting or external transmission of research is part of this decision. Business retention/deletion/backup objectives, shared limits, restore evidence, provider-neutral quality benchmark, semantic support and owner usefulness remain prerequisites for later reviewed work. Stop for review before B15 or any subsequent stage.
