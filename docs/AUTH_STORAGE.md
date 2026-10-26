# Lather Lens authentication and owner storage

25 October 2026. This stage implements backend Supabase Auth integration, PostgreSQL storage/RLS, repositories and protected APIs. Verification uses actual local Supabase Auth/Postgres, not SQLite or an identity mock. No hosted project, cloud resource, model/search call or deployment is used.

## Authentication

Clients obtain sessions through Supabase Auth. FastAPI accepts a Bearer access token, sends it to the configured trusted Supabase /auth/v1/user endpoint with a publishable/anon key, and derives the user UUID from the verified response. It never trusts an unsigned JWT payload, client owner_id or model-supplied identity. Invalid/missing tokens return 401; unavailable/unconfigured Auth returns 503. Anonymous Auth users are rejected. Redirects are disabled and timeouts bounded. Auth checks can make local network calls even while research mode remains replay and paid external tools are disabled.

Backend settings accept only a publishable key or legacy anon-key classification; privileged keys are rejected. The legacy JWT payload is decoded only to reject the wrong key class, not to authenticate users. Signature/lifetime/user validity comes from Supabase Auth. No JWT signing secret or service-role key is used by the application. Tokens/keys are never persisted in domain records or emitted in application logs. Do not log HTTP authorization headers or config object contents.

This follows [Supabase JWT verification guidance](https://supabase.com/docs/guides/auth/jwts), including verification through Auth for shared-secret installations. Current tradeoff: one Auth lookup per protected request; Auth outage fails closed. Frontend sign-in screens/session-refresh UX are not implemented in this backend/storage stage. Supabase's own signup and password-login endpoints are exercised in local setup; clients can use official Supabase clients later. No service-role key is present in frontend source or public environment settings, verified by a unit check.

## Database identities and RLS

Migration/admin connection is separate from the runtime login. The migration creates NOLOGIN NOINHERIT NOBYPASSRLS role lather_api, with minimal table grants. Local bootstrap creates a generated-password runtime login with no superuser, bypass, database-create, role-create or inherited privileges, and grants membership in lather_api. Every repository transaction rejects superuser/BYPASSRLS login, uses SET LOCAL ROLE lather_api, then sets transaction-local Supabase identity claims from the verified user. Claims/role cannot leak through pooled connections after transaction end.

All 17 domain tables enable AND force RLS. SELECT policies scope owner_id to auth.uid(); INSERT/UPDATE policies have WITH CHECK on the owner. Every repository query also applies owner filters. Same-owner and same-run composite foreign keys prevent cross-owner/run links even when a UUID is known. Owner references point to existing auth.users, which this migration never creates/drops. Supabase authenticated role gets read-only access to owned records, with no access to the idempotency ledger. The API role alone can insert records; only runs, approval requests and job state can update. Reports/evidence observations/decision records are append-only through granted runtime permissions. No DELETE is granted. Retention/deletion workflows remain separately reviewed future work.

Supabase service/admin capabilities are not runtime credentials. A privileged database administrator can bypass data policies by design; none of those credentials enter frontend or normal request handling. See [Supabase RLS documentation](https://supabase.com/docs/guides/database/postgres/row-level-security).

## Migration 0001

| Table | Stored state |
| --- | --- |
| briefs | Immutable structured brief and version |
| runs | Owner/brief, status/version, budget, checkpoint pointer payload, failure code |
| run_events | Per-run sequence, event kind, versioned data |
| competitors | Run-scoped identity and URL |
| sources | URL/title/publisher/retrieval date/hash/access status/excerpt |
| claims | Factual/interpretation/hypothesis/marketing type, materiality, review status |
| claim_sources | Same-run source/claim link, excerpt/hash |
| products | Competitor/SKU, disclosed ingredients and attributes |
| price_observations | Product/source, Decimal price, currency, total pack grams, pack quantity/date and computed unit price |
| reports | Immutable version/hash/document |
| approval_requests | Pending gate, exact artifact version/hash/reference |
| approval_decisions | One immutable decision per request |
| evaluation_cases | Owner-scoped versioned case definition |
| evaluation_results | Run/case, outcome and result payload |
| usage_records | Unique operation/attempt accounting |
| run_jobs | One durable queued job per run; worker execution not implemented |
| idempotency_keys | Owner/operation/hashed key, request hash, original response |

Finite nonnegative price/cost and positive known weights/pack quantities are constrained. Unit price is generated by PostgreSQL from price / total pack grams * 100; missing weight remains null. Same-SKU/source interpretation still requires future evidence validation; arithmetic does not establish source support. Successful sources require a hash. Report hash/version and approval binding are checked before final decision.

Alembic is the sole domain migration owner. Supabase config runs local Auth/system schema only; no parallel domain migration copies. Revision 0001 imports a frozen schema_v1 snapshot, not evolving app metadata. Downgrade removes domain tables and API role, preserving auth.users and Supabase system schema. Reapply recreates the domain schema; a runtime login needs its API-role membership restored after role recreation. Rollback is destructive to domain data and is tested only on the dedicated marked local instance, never a hosted database.

## Repositories and endpoints

All /api routes require Bearer auth. OpenAPI includes security schemes, validation, typed data/command responses and error responses; exported docs/openapi.json is reproducible through backend/tools/export_openapi.py.

- GET /api/auth/me
- POST /api/briefs; GET /api/briefs/{id}
- POST /api/runs; GET /api/runs/{id}; GET /api/history
- POST /api/runs/{id}/shortlist-decision; POST /api/runs/{id}/report-decision
- GET /api/runs/{id}/events, /competitors, /sources, /claims, /products, /prices, /reports, /approvals, /evals, /usage
- GET /api/runs/{id}/report returns the exact approved report after completion, otherwise latest draft

Collections have bounded limits and offset; events also have an after sequence cursor. Events are JSON polling in this stage, not SSE. Unknown or other-owner identifiers return the same 404. Owner IDs are output fields only and cannot be assigned through command inputs. Internal writers use repositories; clients cannot post arbitrary source/report/approval rows through the Data API.

Start requires Idempotency-Key, locks an owner/operation/key advisory transaction lock, checks canonical request hash and atomically creates run/job/queued event/original response. Retries return the original response; changed payload gives 409. Approval keys are also scoped to owner/gate/run; run row is locked, pending request/gate/run state/version/hash checked, then decision/state/event/idempotency response committed together. Concurrent retries yield one decision. Different keys cannot approve a decided/stale request. Shortlist approval permits one to three listed candidates; fewer requires explicit insufficiency. Report decisions bind the immutable report ID/version/hash. Only trusted internal work creates pending artifacts; no fake report/request is generated by start.

Repository dependencies use function scope so transaction commit/rollback completes before the HTTP response is sent. A failed command rolls back its decision/state/event/idempotency changes. One engine pool is constructed without opening connections during app construction, avoiding first-request pool-creation races; it is disposed at shutdown.

Queued jobs are durable storage only. No worker consumes them, no research starts or credits are spent. Human rejection/change request records a partial state; subsequent revision/rediscovery routing belongs to the later workflow stage. Cancellation/export/history-diff/SSE and full LangGraph recovery remain future work.

## Local operation

Requires Docker daemon access, pinned uv/Node from README, and public image/package download access on first use. Supabase CLI is pinned to 2.122.0 and telemetry disabled. See [local Supabase guidance](https://supabase.com/docs/guides/local-development/cli/getting-started). The dedicated project is lather-lens-local, API loopback port 57421, DB loopback port 57422. Other services and cloud integrations are disabled in config.

From root after scripts/project.ps1 install:

```powershell
powershell -NoProfile -File scripts/local-auth.ps1 -Action start
powershell -NoProfile -File scripts/local-auth.ps1 -Action prepare
powershell -NoProfile -File scripts/local-auth.ps1 -Action test
powershell -NoProfile -File scripts/local-auth.ps1 -Action stop
```

Preparation applies migrations ONLY to this local instance, creates/validates the least-privileged runtime login, registers/password-signs-in two generated DEMO users with email confirmation disabled, and stores runtime/admin URLs, tokens and publishable key only in ignored .cache/auth-stage.json. CLI output containing credentials is captured and never displayed or logged by wrappers. Do not print or commit that file. Local test-only control schema records a random instance marker; integration tests require loopback ports and matching marker before destructive rollback. Ordinary unit tests deny socket access; explicitly marked integration tests allow only the dedicated loopback ports. libpq uses native I/O, so guarded configuration and instance identity are also essential.

To run the API against this local setup without copying secrets into source, in a local shell:

```powershell
$local = Get-Content -Raw .cache/auth-stage.json | ConvertFrom-Json
$env:LATHER_DATABASE_URL = $local.runtime_url
$env:LATHER_SUPABASE_URL = $local.supabase_url
$env:LATHER_SUPABASE_PUBLISHABLE_KEY = $local.publishable_key
powershell -NoProfile -File scripts/project.ps1 -Action api
```

These assignments do not print values. Do not paste tokens into shell commands/history or tool output. Auth UI is a later stage. Health readiness still states database not_checked; protected DB requests exercise actual connectivity, and the health dependency probe remains a limitation.

Integration CI job uses the same local stack wrappers, no hosted Supabase account or service secrets. Hosted CI execution and cloud migration compatibility are not claimed. Actual executed tests, errors corrected and current limits are in AUTH_STORAGE_STAGE_RESULTS.md. Stop for review before any UI/research/worker stage.
