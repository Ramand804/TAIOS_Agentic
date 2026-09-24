from copy import deepcopy
from dataclasses import FrozenInstanceError, replace

import pytest

from core.feedback_assessment import (
    ExecutionFeedback, FeedbackAssessment, FeedbackStatus, OperationalFeedback,
    SecurityFeedback, StateEffectFeedback,
)
from core.pipeline_result import PipelineProcessingError
from core.runtime_inputs import runtime_observation
from core.taios_pipeline import TAIOSPipeline
from core.trust_assessment import AuditCorrelation
from environment.event_generator import EventGenerator
from environment.industrial_environment import IndustrialState
from intelligence.feedback_interpreter import FeedbackInterpreter
from intelligence.experience_builder import build_experience_record
from memory.feedback_memory import FeedbackMemory


def events(scenario='S2', seed=42):
    generator = EventGenerator(seed, observable_state=True)
    run = generator.create_run(scenario, 10)
    return generator.generate(scenario, 10, run)


def run(scenario='S2', seed=42, source_events=None):
    pipeline = TAIOSPipeline()
    episode = pipeline.run_episode(source_events or events(scenario, seed), seed=seed)
    return pipeline, episode


def test_feedback_is_immutable_and_reference_is_deterministic():
    pipeline, _ = run('S2')
    feedback = pipeline.feedback_memory.records[0]
    with pytest.raises(FrozenInstanceError):
        feedback.feedback_coverage = 1
    replay, _ = run('S2')
    assert feedback.reference == replay.feedback_memory.records[0].reference


def test_successful_mutation_feedback_is_technical_not_security_correctness():
    pipeline, _ = run('S2')
    feedback = pipeline.feedback_memory.records[0]
    assert feedback.feedback_status == FeedbackStatus.OBSERVABLE_FEEDBACK
    assert feedback.execution_feedback == ExecutionFeedback.TECHNICAL_EXECUTION_SUCCEEDED
    assert feedback.state_effect_feedback == StateEffectFeedback.EXPECTED_STATE_EFFECT_OBSERVED
    assert feedback.operational_feedback == OperationalFeedback.REQUESTED_STATE_OBSERVED
    assert feedback.security_feedback == SecurityFeedback.UNAVAILABLE
    assert 'SECURITY' not in feedback.available_dimensions
    assert feedback.feedback_coverage == 0.75
    assert 'do not establish security correctness' in feedback.to_dict()['interpretation']


def test_successful_noop_produces_valid_operational_feedback():
    pipeline, episode = run('S5')
    feedback = pipeline.feedback_memory.records[6]
    assert episode.pipeline_results[6].observed_outcome.outcome_status.value == 'EXECUTED_NOOP_OBSERVED'
    assert feedback.execution_feedback == ExecutionFeedback.SUCCESSFUL_NOOP_CONFIRMED
    assert feedback.state_effect_feedback == StateEffectFeedback.EXPECTED_NOOP_OBSERVED
    assert feedback.operational_feedback == OperationalFeedback.AUTHORIZED_NOOP_OBSERVED
    assert {item.category for item in feedback.evidence_items} == {
        'AUTHORIZED_PAYLOAD_APPLIED', 'NOOP_STATE_CONFIRMED', 'AUTHORIZED_NOOP_OBSERVED'}


def test_pending_external_feedback_remains_unresolved():
    pipeline, _ = run('S3')
    for feedback in pipeline.feedback_memory.records:
        assert feedback.feedback_status == FeedbackStatus.PENDING_EXTERNAL_FEEDBACK
        assert feedback.execution_feedback == ExecutionFeedback.EXTERNAL_APPROVAL_PENDING
        assert feedback.state_effect_feedback == StateEffectFeedback.STATE_EFFECT_PENDING
        assert feedback.operational_feedback == OperationalFeedback.OPERATIONAL_EFFECT_PENDING
        assert feedback.security_feedback == SecurityFeedback.UNAVAILABLE
        assert feedback.feedback_coverage == 0.25
        assert len(feedback.unresolved_feedback_requirements) == 4


def test_interpretation_is_idempotent_for_same_canonical_experience():
    pipeline, episode = run('S2')
    experience = pipeline.memory.records[0]
    row = episode.pipeline_results[0]
    interpreter = FeedbackInterpreter()
    first = interpreter.interpret(experience, row.observed_outcome, row.execution_result)
    second = interpreter.interpret(experience, row.observed_outcome, row.execution_result)
    assert first == second
    assert first.reference == second.reference


def test_feedback_memory_append_retrieval_reset_and_fingerprint():
    pipeline, _ = run('S2')
    memory = pipeline.feedback_memory
    assert memory.count == 10
    first = memory.records[0]
    assert memory.get_by_experience(first.experience_reference) == first
    assert first in memory.get_by_event(first.event_reference)
    assert memory.get_by_source('PLC-07') == memory.records
    assert memory.get_by_target('MOTOR-02') == memory.records
    assert memory.recent(3) == memory.records[-3:]
    original = memory.memory_fingerprint
    memory.append(first)
    assert memory.count == 10 and memory.memory_fingerprint == original
    memory.reset()
    assert memory.count == 0 and memory.records == ()


def test_pipeline_exposes_feedback_and_episode_summary():
    pipeline, episode = run('S2')
    assert episode.feedback_count == 10
    assert episode.feedback_memory_fingerprint == pipeline.feedback_memory.memory_fingerprint
    assert all(row.feedback_reference == feedback.reference
               for row, feedback in zip(episode.pipeline_results,
                                        pipeline.feedback_memory.records))


def test_feedback_failure_rolls_back_experience_feedback_and_existing_state():
    class FailOnceInterpreter(FeedbackInterpreter):
        def __init__(self):
            self.fail = True

        def interpret(self, *args, **kwargs):
            if self.fail:
                self.fail = False
                raise ValueError('injected feedback failure')
            return super().interpret(*args, **kwargs)

    pipeline = TAIOSPipeline(feedback_interpreter=FailOnceInterpreter())
    event = events('S2')[0]
    with pytest.raises(PipelineProcessingError, match='injected feedback failure'):
        pipeline.process_event(event, IndustrialState())
    assert pipeline.memory.count == pipeline.feedback_memory.count == 0
    result = pipeline.process_event(event, IndustrialState())
    assert result.execution_result.execution_status.value == 'SUCCEEDED'
    assert pipeline.memory.count == pipeline.feedback_memory.count == 1
    assert result.trust_assessment.trust_state_version == 1
    assert result.threat_assessment.source_history_version == 0
    assert result.correlation_assessment.history_version == 0


@pytest.mark.parametrize('scenario', ('S1', 'S4', 'S6'))
def test_scenarios_preserve_unavailable_security_feedback(scenario):
    pipeline, _ = run(scenario)
    assert all(row.security_feedback == SecurityFeedback.UNAVAILABLE
               for row in pipeline.feedback_memory.records)


def test_s2_feedback_trajectory_is_five_observable_then_five_pending():
    pipeline, _ = run('S2')
    statuses = [row.feedback_status for row in pipeline.feedback_memory.records]
    assert statuses[:5] == [FeedbackStatus.OBSERVABLE_FEEDBACK] * 5
    assert statuses[5:] == [FeedbackStatus.PENDING_EXTERNAL_FEEDBACK] * 5


def test_s5_high_output_and_noop_do_not_claim_adaptation():
    pipeline, episode = run('S5')
    assert all(row.observed_outcome.operating_mode_after == 'HIGH_OUTPUT'
               for row in episode.pipeline_results[5:])
    noop = pipeline.feedback_memory.records[6]
    assert noop.operational_feedback == OperationalFeedback.AUTHORIZED_NOOP_OBSERVED
    assert 'adapt' not in str(noop.to_dict()).lower()


def test_s6_correlation_uncertainty_is_not_security_confirmation():
    pipeline, episode = run('S6')
    uncertain = [feedback for feedback, row in zip(
        pipeline.feedback_memory.records, episode.pipeline_results)
        if row.correlation_assessment.status.value == 'UNCERTAINTY_ONLY']
    assert uncertain
    assert all(row.security_feedback == SecurityFeedback.UNAVAILABLE for row in uncertain)


def test_leakage_invariance_and_input_immutability():
    original = events('S2')
    changed = deepcopy(original)
    for event in changed:
        event.ground_truth = 'DIFFERENT'
        event.expected_safe_action = 'ISOLATE'
        event.scenario_id = 'OTHER'
        event.contextual_features.update(
            evaluation_correctness=False, unsafe_action=True,
            false_intervention=True, attack_phase='changed')
    assert [runtime_observation(event) for event in original] == [
        runtime_observation(event) for event in changed]
    pipeline, _ = run('S2')
    serialized = str([row.to_dict() for row in pipeline.feedback_memory.records])
    for forbidden in ('ground_truth', 'expected_safe_action', 'scenario_id',
                      'evaluation_correctness', 'unsafe_action',
                      'false_intervention', 'attack_phase'):
        assert forbidden not in serialized


def test_prefix_causality_current_experience_only():
    full_pipeline, _ = run('S2')
    prefix_pipeline, _ = run('S2', source_events=events('S2')[:6])
    assert full_pipeline.feedback_memory.records[:6] == prefix_pipeline.feedback_memory.records


def test_audit_metadata_is_isolated_from_feedback():
    pipeline, episode = run('S2')
    row = episode.pipeline_results[0]
    audited_trust = replace(row.trust_assessment,
                            audit=AuditCorrelation('audit-only', 999))
    audited_experience = build_experience_record(
        event_reference=row.event_reference, observation=dict(row.observable_input),
        semantics=row.operational_semantic_assessment, threat=row.threat_assessment,
        correlation=row.correlation_assessment, trust=audited_trust,
        risk=row.risk_assessment, authorization=row.authorization_assessment,
        authority=row.authority_assessment, planning=row.planning_result,
        proposal=row.proposed_decision, governance=row.governance_decision,
        execution=row.execution_result, outcome=row.observed_outcome,
        state_before=row.state_before, state_after=row.state_after)
    assert audited_experience == pipeline.memory.records[0]
    interpreted = FeedbackInterpreter().interpret(
        audited_experience, row.observed_outcome, row.execution_result)
    assert interpreted == pipeline.feedback_memory.records[0]


def test_feedback_does_not_change_trust_risk_correlation_experience_or_actions():
    first_pipeline, first = run('S6')
    second_pipeline, second = run('S6')
    assert [row.trust_assessment.to_inference_dict() for row in first.pipeline_results] == [
        row.trust_assessment.to_inference_dict() for row in second.pipeline_results]
    assert [row.risk_assessment.to_dict() for row in first.pipeline_results] == [
        row.risk_assessment.to_dict() for row in second.pipeline_results]
    assert [row.correlation_assessment.to_dict() for row in first.pipeline_results] == [
        row.correlation_assessment.to_dict() for row in second.pipeline_results]
    assert first_pipeline.memory.records == second_pipeline.memory.records
    for key in ('proposals', 'governance_statuses', 'execution_statuses'):
        assert first.structural_summary[key] == second.structural_summary[key]
