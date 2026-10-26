# ADR 0004 Required stack and explicit egress controls

Status: proposed for review. Date: 25 October 2026.

Context: user prescribes FastAPI, LangGraph, Next.js TypeScript, Supabase Postgres, Tavily, configurable model adapter and LangSmith. User prohibits API calls/deployment now and spending/provisioning/publication/contact without approval. PRD provider/hosting choices are proposals, not provisioned resources.

Decision: retain required stack and place search/retrieval/model/tracing behind interfaces. Default to offline replay. Production secrets stay server-side and never enter code/logs/browser bundles. Require explicit live-research/budget authorization before dispatch and separately authorize LangSmith telemetry. Do not initialize SDKs in ways that automatically send data. Store version/configuration identifiers, not secret values, in run context.

Keep Next.js reference-fidelity screens with actual state and visible DEMO labels for synthetic data. Defer provider choice, runtime/package pins and hosting compatibility verification to their implementation stages. ADR 0005 records the later binding quality-first/provider-neutral user decision: PRD's Fireworks-first consideration is superseded, with no preference for Fireworks, Nebius or OpenAI. Benchmark before final model selection. Netlify/Railway/Supabase are hosting candidates; no provisioning or deployment is performed by this ADR.

Alternatives: hard-coding a provider impairs configurability; automatic traces violate current egress limits; choosing a simpler UI would disregard the user and visual contract. Additional vector/graph/memory services have no demonstrated MVP need.

Consequences: offline checks cost no provider credits but cannot demonstrate real integration. Approved telemetry must be minimized/redacted. Chaos injection is server-gated to isolated test/DEMO modes and denied in production.

Verification planned: S02–S04, P01, UI01–UI06 and later approved integration checks. No current versions, credit validity or provider capability is asserted.
