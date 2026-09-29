from agentic.contracts import AgenticInput

def build_agentic_input(result):
    """Allowlisted input from an already deterministic V1 pipeline result."""
    o=dict(result.observable_input)
    return AgenticInput(observation=o, semantics=result.operational_semantic_assessment.to_dict(), authorization_status=result.authorization_assessment.status.value, trust_summary=result.trust_assessment.to_inference_dict(), threat_summary=result.threat_assessment.to_dict(), risk_summary=result.risk_assessment.to_inference_dict(), drift_summary=result.drift_assessment.to_dict(), adaptation_summary=(result.adaptation_decision.to_dict() if result.adaptation_decision else {'status':'UNAVAILABLE'}), assured_actions=tuple(k for k,v in result.assured_authority_assessment.action_authority.items() if v=='PERMITTED'), planner_candidates=tuple(c.action.value for c in result.planning_result.candidates), evidence_references=(result.event_reference,result.assurance_assessment.reference))
