# ADR 0007 Gateway-only discovery and durable shortlist review

Date: 25 October 2026. Status: implemented for the requested offline Scout stage; live activation and subsequent worker remain unapproved.

Context: the existing harness is schema/preflight only and Auth/storage already has owner-bound approval commands. The user now requires bounded Tavily/Scout discovery and a durable shortlist interrupt without spending credits. PRD places the full LangGraph worker after discovery and Researcher work. LLM quality/provider selection is independently benchmark-gated.

Decision: implement a search-specific gateway/port and fixed-endpoint HTTPX Tavily wire adapter with no enabled real transport. The harness alone owns argument validation, policy, atomic database accounting and retry/deadline decisions. Recorded transport is exact/hash/version checked and cannot fall back to network. Avoid hidden SDK retry loops and provider-selected answers/candidates.

Use a conservative deterministic relevance baseline with explicit quotes/unknowns and no model selection. Build candidates only from named maker snippets and deduplicate using the bundled public/private suffix rules. Preserve all exclusions and candidate shortfalls. This establishes controlled provenance, not measured live research quality or a final extraction/model strategy.

Persist pending shortlist approval, exact artifact hash/version, journal/source/usage/events and checkpoint in Postgres. This scoped application interrupt survives process restart and uses the existing owner/version-bound decision API. It is not a LangGraph checkpointer. Full graph/worker/leases/fencing and deeper research remain later work, so neither approval nor this stage starts them automatically.

Consequences: migration 0003 adds an RLS-protected attempt journal and explicit snippet/page source kind. Shared run locks prevent concurrent call/cost oversubscription; uncertain requests retain reservations and require reconciliation. No exactly-once remote billing claim. Request-depth/model quality benchmarking and live API credentials/price caps await separate approval. SCOUT_SPEC.md records limitations and SCOUT_STAGE_RESULTS.md records actual evidence. Original BRD/HTML/PRD files and acceptance targets are unchanged.
