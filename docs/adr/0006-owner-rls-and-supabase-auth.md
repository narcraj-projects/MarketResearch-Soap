# ADR 0006 Supabase identity and constrained database access

25 October 2026. Implemented locally; hosted rollout not authorized.

Use Supabase Auth's verified /auth/v1/user response to derive authenticated user identity. Do not parse unsigned JWT identity or store signing/service secrets in frontend. Runtime uses a public/anon key for Auth verification and no service-role key. An Auth outage fails closed; per-request verification latency is an explicit tradeoff.

Use a separate non-bypass runtime database login, transaction-local SET ROLE lather_api and claims derived from verified identity. Apply explicit owner filters, forced RLS on every domain table and composite owner/run foreign keys. Supabase authenticated browser role is read-only; creating human approvals directly through the Data API is forbidden. Immutable reports, observations and decisions have no runtime update/delete grants.

Start and approval commands serialize owner/operation/key retries with transaction advisory locks and persist request hashes/responses with the state/event changes. Approval also locks the run and verifies pending gate/state/artifact hash/version. No worker consumes queued jobs in this stage.

Alembic owns the domain schema using a frozen initial snapshot; Supabase owns Auth/system schemas. Rollback is destructively tested only on the dedicated local instance with a marker/port guard. Hosted migrations, UI sign-in, session UX, retention/deletion and LangGraph crash recovery require later review. No cloud resources or paid APIs are used by this decision.
