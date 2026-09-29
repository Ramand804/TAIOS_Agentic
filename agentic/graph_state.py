"""Runtime-safe state used by the V2 mock advisory LangGraph subworkflow."""
from typing import TypedDict
from agentic.contracts import AgenticInput, AgenticProposal, ValidationStatus
from agentic.provenance import LLMProvenance

class AgenticGraphState(TypedDict, total=False):
    agentic_input: AgenticInput
    deterministic_proposal: object
    deterministic_assessments: object
    authority_state: object
    assurance_state: object
    governance_state: object
    execution_state: object
    feedback_state: object
    decision_context: object
    planning_result: object
    assurance_result: object
    selected_decision: object
    selection_provenance: object
    industrial_state: object
    event: object
    transaction: object
    input_state_reference: str
    event_key: str | None
    stage_holder: dict
    observation: object
    state_before: object
    state_after: object
    regime_transition: bool
    semantics: object
    event_reference: str
    drift: object
    reference_snapshot: object
    authorization: object
    threat: object
    correlation: object
    trust: object
    risk: object
    authority: object
    assured_authority: object
    plan: object
    proposal: object
    governance: object
    execution: object
    outcome: object
    experience: object
    feedback: object
    adaptation_proposal: object
    adaptation_decision: object
    result: object
    decision_trace: object
    working_memory: object
    memory_retrieval: object
    memory_context: tuple[object, ...]
    terminal_state: str
    validated_advisory: AgenticProposal
    resolved_proposal: object
    validation_status: ValidationStatus
    fallback_reason: str | None
    llm_provenance: LLMProvenance
    workflow_version: str
    agentic_mode: str
    visited_nodes: tuple[str, ...]

PROHIBITED_GRAPH_FIELDS = frozenset({
    'ground_truth', 'expected_safe_action', 'scenario_id', 'experiment_id',
    'phase_label', 'phase_labels', 'causal_annotation', 'causal_annotations',
    'compromise_label', 'compromise_labels', 'evaluation_oracle',
})
