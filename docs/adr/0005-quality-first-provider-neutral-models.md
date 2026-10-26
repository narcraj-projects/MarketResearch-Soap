# ADR 0005 Quality first provider neutral model selection

Date: 25 October 2026. Status: architectural principle accepted by explicit user decision; benchmark thresholds and implementation mechanics proposed for review.

Context: the user prioritizes factual accuracy, citation grounding, competitor relevance, extraction reliability and strategic analysis over API cost, and prohibits paid calls/deployment now. PRD section 5's Fireworks-first consideration conflicts with that decision. Existing contracts are vendor-neutral strings but lack a dedicated model adapter and multi-role provenance manifest.

Decision: retain required application stack while making LLM choice independent of Fireworks, Nebius and OpenAI. Supersede the PRD provider preference in implementation planning without modifying the authoritative source files. Domain agents use a neutral adapter; vendor transports and capabilities stay isolated. Benchmark before selecting final role models; permit multiple evaluated role profiles with versioned provenance. No model selected or vendor default introduced now.

Quality-only ranking follows reviewed MODEL_BENCHMARK.md dimensions and hard gates. Cost/latency remain diagnostic and authorized spend/deadline caps remain enforced. Budget exhaustion produces a transparent stop; it never silently downgrades to a cheaper model. Uncertain quality rankings require more reviewed evidence, not a cost tie-break.

Alternatives rejected: selecting by existing credits; hard-coding one provider; treating API compatibility as identical behavior; using citation presence as support; selecting on a cost-weighted composite before quality gates.

Consequences: add model-adapter conformance, neutral errors/tool intents, offline benchmarking, role-profile manifests and explicit schema migration before live evaluation. Human support/strategy review remains required. MODEL_IMPLEMENTATION_PLAN.md orders later work with review/paid-call boundaries. No live benchmark, final model choice or deployment is authorized by this ADR.
