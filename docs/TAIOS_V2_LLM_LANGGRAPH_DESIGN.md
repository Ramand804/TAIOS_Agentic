# TAIOS V2: minimal LLM and LangGraph design

## Scope and invariant

V2 adds an optional LangGraph orchestration layer and an LLM planning assistant. It does not replace V1 safety controls. Operational semantics, authorization, trust, threat evidence, risk, drift, governed adaptation, decision assurance, governance, and execution remain deterministic authorities. The LLM cannot execute actions, change assessment values, or override deterministic controls.

## LangGraph role and state

LangGraph coordinates existing V1 stages as explicit nodes with a runtime-safe state: allowlisted observation; semantic, authorization, trust, threat, risk, drift, correlation, adaptation, authority, assurance, planning, proposal, governance, execution, outcome, feedback, and provenance references. It contains no ground truth, expected action, scenario ID, phase, causal annotation, evaluator provenance, or secrets.

The initial node order follows V1: `context -> semantics -> drift -> authorization -> threat -> correlation -> trust -> risk -> authority -> assurance -> planning -> decision -> governance -> execution -> outcome -> feedback -> adaptation/memory`. Adaptation remains governed and does not precede assurance. Nodes may be grouped only when this ordering and contracts are retained.

## LLM boundary

The optional `llm_planning` node runs after deterministic context, authority, and assurance are available and before deterministic proposal validation/governance. Its input is a sanitized contract: runtime observation, semantic status/constraints, authorization status, permitted assured actions, risk/trust summaries, drift/correlation/threat categorical statuses, and candidate capability descriptions. It excludes raw event records and all evaluator-only fields.

The output is strict JSON:

```json
{
  "recommended_action": "ALLOW|MONITOR|LIMIT|REQUEST_APPROVAL|BLOCK|ISOLATE",
  "candidate_actions": ["..."],
  "reason_codes": ["KNOWN_CODE"],
  "rationale": "bounded text",
  "confidence": 0.0
}
```

No command, payload, tool invocation, policy edit, score, or free-form executable instruction is accepted. A deterministic validator requires exact schema conformance, known action vocabulary, candidate membership, assured authority permission, bounded rationale/uncertainty/list sizes, finite confidence in [0,1], reason-code allowlisting, and rejection of executable text markers. The existing deterministic planning/decision contracts remain the only path to governance and execution.

The minimal integration pattern is **advisory candidate ranking only**: the deterministic PlanningAgent first generates the canonical candidate set from assured context; the LLM may rank or recommend only a member of that set; DecisionAgent consumes either the validated advice through a bounded adapter or the unchanged deterministic proposal path. The LLM is not a second planner and never produces a payload.

## Conditional edges and safe failure

Insufficient deterministic evidence follows the existing V1 path. Timeout, API error, unavailable model, malformed JSON, unknown/hallucinated action, unauthorized action, or failed validation records an LLM failure and uses the unmodified deterministic V1 PlanningAgent/DecisionAgent proposal for the same assured context. This avoids assuming that `REQUEST_APPROVAL` is always authorized. Assurance restriction always precedes and constrains LLM recommendations. Governance rejection always prevents execution. Execution continues to require the governance authorization artifact and exact authorized payload. **LLM failure cannot create additional autonomous authority relative to the deterministic V1 path.**

## Graph routing and implementation modes

Conditional edges are selected only by deterministic validated state: failed event/context validation terminates through the existing pipeline failure contract; valid state reaches canonical planning; LLM validation success reaches bounded advisory merge, while any LLM failure returns to deterministic planning/decision; assurance-restricted authority remains in the canonical candidate set; governance veto terminates without execution; governance approval reaches execution; outcome reaches experience, feedback, and then governed adaptation. The LLM never chooses an edge.

Expose three modes without duplicating V1 safety code: `DETERMINISTIC_V1` invokes the existing pipeline unchanged; `AGENTIC_MOCK` invokes the graph with a deterministic mock advisory client; `AGENTIC_LLM` invokes the same graph through a provider-neutral structured adapter. No provider SDK or external API client is included. Without an explicitly supplied provider, `AGENTIC_LLM` yields `MODEL_UNAVAILABLE` and follows the exact deterministic fallback. Any future provider is not exactly reproducible, whereas mock mode is required for CI and regression tests.

## Provenance and reproducibility

V2 adds `llm_provider`, `llm_model`, `prompt_version`, `response_schema_version`, `llm_raw_response_hash`, `validated_llm_proposal`, `validation_status`, and `fallback_reason`. Secrets, API keys, and unbounded raw prompts are not persisted. LLM responses may be nondeterministic; deterministic mock mode is required for tests and V1 deterministic mode remains available as a baseline.

## Test plan before implementation

1. LLM input excludes evaluator labels and provenance annotations.
2. LLM cannot exceed assured authority or bypass assurance.
3. LLM cannot bypass governance or execution authorization.
4. Invalid/unknown action and malformed JSON fail safely.
5. Timeout, provider failure, and unavailable model fail safely.
6. Deterministic mock output is reproducible.
7. Provenance records involvement without secrets.
8. Existing V1 deterministic pipeline remains selectable and unchanged.

## Proposed V2 files

Add: `core/llm_contracts.py`, `intelligence/llm_output_validator.py`, `orchestration/langgraph_pipeline.py`, `orchestration/llm_planning_node.py`, `tests/test_llm_safety_boundary.py`, and `tests/test_langgraph_orchestration.py`. Modify only V2 orchestration entry points and provenance/result contracts after tests are approved. Do not install LangGraph or invoke an LLM API until implementation begins.
