# ADR 0001 Harness before agents

Status: proposed for review. Date: 25 October 2026.

Context: BRD sections 8–13 require conditional tool use, source integrity, bounded failure handling and recorded actual tests. PRD sections 6/11 require a separate harness and evaluations from the first sprint.

Decision: implement backend/app/harness/ contracts, policy, bounded execution and offline replay before agent prompts/live adapters. Inject model/search interfaces, clock, RNG and IDs. Keep deterministic normalization separate from model synthesis. Use LangGraph for typed conditional coordination after harness behavior is testable. Four agent roles and Orchestrator are logical responsibilities, not five model processes.

Alternatives: prompt-chain first makes approval/recovery hard to verify; separate autonomous services per role add coordination without a demonstrated need. Neither is selected.

Consequences: early deliverables run offline with visibly DEMO fixtures and explicit versions. This proves controlled behavior, not real search quality or business usefulness. Stable contracts need deliberate schema/version migration as agents evolve.

Verification planned: D01–D17, T01–T08, S03/S04 and trajectory assertions. No such application tests executed in this stage.
