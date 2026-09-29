# V2-2C bounded agentic selection

V2 adds `BoundedAgenticSelector`: a V2-only adapter that can select a validated agentic recommendation only when it is an existing planner candidate and is simultaneously assurance-permitted and authority-permitted. It produces the canonical V1 `ProposedDecision`; fallback always calls the unchanged V1 `DecisionAgent`.

The full mock lifecycle is source-derived: `context → semantics → drift → authorization → threat → correlation → trust → risk → decision_context → planning → decision → llm_planning → bounded_selection → governance → execution → outcome → experience → feedback_interpretation → feedback_commit → adaptation → result → transaction_commit`. Each node invokes one protected V1 lifecycle helper; there is no opaque `process_event()` graph node and no persistent LangGraph checkpointer. Governance and execution call the existing V1 agents and retain their canonical bindings.

The graph begins one TAIOS transaction, uses the same V1 checkpoint/rollback helpers, and rejects replay of a completed graph stage. An existing event replay is deliberately routed to the V1 public replay contract, which uses the execution idempotency behavior without rerunning scientific assessments. All failures in a normal graph path restore the TAIOS checkpoint and report the current V1 stage label.

The deterministic default MockLLM is given the already-created V1 baseline action and recommends it, supporting exact parity. A test-only deterministic reasoner can recommend another planner candidate such as `MONITOR`; bounded selection admits it only when it is a planner candidate and permitted by both assurance and authority. Governance remains the exclusive authorization path and execution receives the resulting canonical governance decision.

`AgenticSelectionProvenance` records the baseline action, candidates, assured actions, recommendation, validation, selection source, fallback status, and selected action. This shows bounded architectural influence only; it makes no effectiveness claim.
