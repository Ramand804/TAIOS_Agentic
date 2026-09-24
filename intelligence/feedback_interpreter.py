"""Current-experience-only factual feedback interpretation."""
from core.decision_contracts import ExecutionResult, ExecutionStatus
from core.experience_record import ExperienceRecord
from core.feedback_assessment import (
    ExecutionFeedback, FeedbackAssessment, FeedbackEvidence, FeedbackStatus,
    OperationalFeedback, SecurityFeedback, StateEffectFeedback,
)
from core.observed_outcome import ObservedOutcome, OutcomeStatus


class FeedbackInterpreter:
    @staticmethod
    def _item(category, dimension, basis, source, reason):
        return FeedbackEvidence(
            category=category, dimension=dimension, observable_basis=basis,
            source_reference=source, factual_reason=reason)

    def interpret(self, experience, outcome, execution):
        if type(experience) is not ExperienceRecord:
            raise ValueError('Expected ExperienceRecord')
        if type(outcome) is not ObservedOutcome:
            raise ValueError('Expected ObservedOutcome')
        if type(execution) is not ExecutionResult:
            raise ValueError('Expected ExecutionResult')
        if (experience.event_reference != outcome.event_reference or
                experience.execution_result_reference != execution.reference or
                experience.observed_outcome_reference != outcome.reference):
            raise ValueError('Experience/outcome/execution chain mismatch')
        evidence = []
        unresolved = ['Security correctness requires external or evaluator confirmation.']
        security = SecurityFeedback.UNAVAILABLE
        status = FeedbackStatus.PARTIAL_FEEDBACK
        available = ['EXECUTION']

        if outcome.outcome_status == OutcomeStatus.EXECUTED_MUTATION_OBSERVED:
            execution_feedback = ExecutionFeedback.TECHNICAL_EXECUTION_SUCCEEDED
            state_feedback = StateEffectFeedback.EXPECTED_STATE_EFFECT_OBSERVED
            operational = OperationalFeedback.REQUESTED_STATE_OBSERVED
            available.extend(('STATE_EFFECT', 'OPERATIONAL'))
            status = FeedbackStatus.OBSERVABLE_FEEDBACK
            evidence.extend((
                self._item('AUTHORIZED_PAYLOAD_APPLIED', 'EXECUTION',
                           f'{execution.operation}:{execution.applied_value!r}', execution.reference,
                           'Governance-authorized execution completed technically.'),
                self._item('EXPECTED_STATE_VALUE_OBSERVED', 'STATE_EFFECT',
                           f'{outcome.target_id}:{outcome.resulting_observable_value!r}', outcome.reference,
                           'The resulting simulator state exposes the applied target value.'),
                self._item('REQUESTED_OPERATIONAL_STATE_OBSERVED', 'OPERATIONAL',
                           f'{outcome.operating_mode_after}:{outcome.production_state_after}', outcome.reference,
                           'The requested value is observable under the recorded operating context.'),
            ))
        elif outcome.outcome_status == OutcomeStatus.EXECUTED_NOOP_OBSERVED:
            execution_feedback = ExecutionFeedback.SUCCESSFUL_NOOP_CONFIRMED
            state_feedback = StateEffectFeedback.EXPECTED_NOOP_OBSERVED
            operational = OperationalFeedback.AUTHORIZED_NOOP_OBSERVED
            available.extend(('STATE_EFFECT', 'OPERATIONAL'))
            status = FeedbackStatus.OBSERVABLE_FEEDBACK
            evidence.extend((
                self._item('AUTHORIZED_PAYLOAD_APPLIED', 'EXECUTION',
                           f'{execution.operation}:{execution.applied_value!r}', execution.reference,
                           'Execution succeeded technically without requiring a state mutation.'),
                self._item('NOOP_STATE_CONFIRMED', 'STATE_EFFECT',
                           f'{outcome.state_version_before}->{outcome.state_version_after}', outcome.reference,
                           'Equal state versions and the resulting value confirm a successful no-op.'),
                self._item('AUTHORIZED_NOOP_OBSERVED', 'OPERATIONAL',
                           f'{outcome.target_id}:{outcome.resulting_observable_value!r}', outcome.reference,
                           'The target already exposed the authorized requested value.'),
            ))
        elif outcome.outcome_status == OutcomeStatus.PENDING_EXTERNAL_APPROVAL:
            execution_feedback = ExecutionFeedback.EXTERNAL_APPROVAL_PENDING
            state_feedback = StateEffectFeedback.STATE_EFFECT_PENDING
            operational = OperationalFeedback.OPERATIONAL_EFFECT_PENDING
            status = FeedbackStatus.PENDING_EXTERNAL_FEEDBACK
            unresolved.extend((
                'Human approval decision is unavailable.',
                'Subsequent execution result is unavailable.',
                'Subsequent observable state effect is unavailable.',
            ))
            evidence.append(self._item(
                'EXTERNAL_APPROVAL_PENDING', 'EXECUTION', outcome.execution_status,
                outcome.reference,
                'Governance deferred execution; no external decision or later effect is observed.'))
        else:
            execution_feedback = (ExecutionFeedback.EXECUTION_PREVENTED
                                  if execution.execution_status in {
                                      ExecutionStatus.REJECTED, ExecutionStatus.UNSUPPORTED,
                                      ExecutionStatus.STALE_STATE, ExecutionStatus.DENIED,
                                      ExecutionStatus.ALREADY_EXECUTED}
                                  else ExecutionFeedback.EXECUTION_RESULT_PARTIAL)
            state_feedback = (StateEffectFeedback.STATE_EFFECT_NOT_OBSERVED
                              if not outcome.mutation_observed else
                              StateEffectFeedback.STATE_EFFECT_PARTIALLY_OBSERVED)
            operational = OperationalFeedback.OPERATIONAL_EFFECT_UNAVAILABLE
            status = FeedbackStatus.PARTIAL_FEEDBACK
            unresolved.extend(('Longer-term operational effect is unavailable.',))
            evidence.append(self._item(
                'EXECUTION_PREVENTED_OR_PARTIAL', 'EXECUTION', outcome.execution_status,
                outcome.reference, 'The runtime exposes a non-success execution result.'))

        return FeedbackAssessment(
            experience_reference=experience.reference,
            event_reference=experience.event_reference,
            execution_reference=execution.reference,
            outcome_reference=outcome.reference,
            source_id=experience.source_id, target_id=experience.target_id,
            operation=experience.operation, feedback_status=status,
            execution_feedback=execution_feedback,
            state_effect_feedback=state_feedback, security_feedback=security,
            operational_feedback=operational, evidence_items=tuple(evidence),
            feedback_coverage=len(available) / 4,
            available_dimensions=tuple(available),
            unresolved_feedback_requirements=tuple(unresolved))
