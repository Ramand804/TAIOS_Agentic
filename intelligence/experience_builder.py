"""Build an auditable reference-only experience after outcome observation."""
from core.experience_record import ExperienceRecord
from core.experiment import fingerprint
from core.observed_outcome import ObservedOutcome


def build_experience_record(*, event_reference, observation, semantics, threat,
                            correlation, trust, risk, authorization, authority,
                            planning, proposal, governance, execution, outcome,
                            state_before, state_after):
    if type(outcome) is not ObservedOutcome:
        raise ValueError('Expected ObservedOutcome')
    if outcome.event_reference != event_reference or outcome.execution_reference != execution.reference:
        raise ValueError('Outcome chain mismatch')
    return ExperienceRecord(
        event_reference=event_reference,
        source_id=observation['source_id'], target_id=observation['target_id'],
        operation=observation['operation'], requested_value=observation['requested_value'],
        semantic_assessment_reference=semantics.reference,
        threat_assessment_reference=threat.reference,
        correlation_assessment_reference=correlation.reference,
        trust_assessment_reference=fingerprint(trust.to_inference_dict()),
        risk_assessment_reference=fingerprint(risk.to_inference_dict()),
        authorization_assessment_reference=authorization.reference,
        authority_assessment_reference=authority.reference,
        planning_result_reference=planning.reference,
        proposed_decision_reference=proposal.reference,
        governance_decision_reference=governance.reference,
        execution_result_reference=execution.reference,
        observed_outcome_reference=outcome.reference,
        state_before_reference=fingerprint(state_before.to_dict()),
        state_after_reference=fingerprint(state_after.to_dict()),
        trust_before=trust.previous_composite_trust,
        trust_after=trust.composite_trust,
        risk_score=risk.risk_score,
        risk_coverage=risk.coverage)
