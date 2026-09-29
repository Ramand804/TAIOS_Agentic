"""Machine-readable, non-authoritative explanation for canonical pipeline results."""
from core.decision_contracts import export

def build_decision_trace(result, *, agentic=None, selection=None, workflow=None):
    """Keep deterministic facts separate from LLM rationale and workflow metadata."""
    return {
      'observation': export(result.observable_input),
      'deterministic_assessments': {
        'semantics': result.operational_semantic_assessment.to_dict(),
        'authorization': result.authorization_assessment.to_dict(),
        'drift': result.drift_assessment.to_dict(),
        'threat': result.threat_assessment.to_dict(),
        'correlation': result.correlation_assessment.to_dict(),
        'trust': result.trust_assessment.to_inference_dict(),
        'risk': result.risk_assessment.to_inference_dict(),
        'authority': result.authority_assessment.to_dict(),
        'assurance': result.assurance_assessment.to_dict(),
      },
      'planning': result.planning_result.to_dict(),
      'deterministic_baseline': (selection.deterministic_v1_action if selection else result.proposed_decision.selected_action.value),
      'agentic_reasoning': (None if agentic is None else {
        'recommended_action': agentic.recommended_action.value,
        'ranked_candidate_actions': list(agentic.ranked_candidate_actions),
        'reason_codes': list(agentic.reason_codes), 'rationale': agentic.rationale,
        'confidence': agentic.confidence, 'uncertainty': agentic.uncertainty,
        'evidence_references': list(agentic.evidence_references)}),
      'selection': None if selection is None else export(selection),
      'decision': result.proposed_decision.to_dict(),
      'governance': result.governance_decision.to_dict(),
      'execution': result.execution_result.to_dict(),
      'outcome': result.observed_outcome.to_dict(),
      'feedback_reference': result.feedback_reference,
      'adaptation': result.adaptation_decision.to_dict() if result.adaptation_decision else None,
      'workflow': workflow or {},
    }
