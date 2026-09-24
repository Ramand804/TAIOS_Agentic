from copy import deepcopy
from dataclasses import FrozenInstanceError, replace

import pytest

from agents.risk_agent import RiskAgent
from core.drift_assessment import DriftStatus
from core.pipeline_result import PipelineProcessingError
from core.runtime_inputs import runtime_observation
from core.taios_pipeline import TAIOSPipeline
from core.trust_assessment import AuditCorrelation
from environment.event_generator import EventGenerator
from environment.industrial_environment import IndustrialState
from intelligence.drift_detector import DriftDetector
from intelligence.operational_semantic_model import OperationalSemanticModel


def events(scenario='S2', seed=42):
    generator = EventGenerator(seed, observable_state=True)
    run = generator.create_run(scenario, 10)
    return generator.generate(scenario, 10, run)


def episode(scenario='S2', seed=42, source_events=None):
    return TAIOSPipeline().run_episode(source_events or events(scenario, seed), seed=seed)


def drift_rows(source_events):
    detector = DriftDetector()
    semantics = OperationalSemanticModel()
    rows = []
    for event in source_events:
        observation = runtime_observation(event)
        rows.append(detector.assess(observation, semantics.assess(observation)))
    return rows


def test_contracts_are_immutable_and_references_deterministic():
    first = episode('S2').pipeline_results[5].drift_assessment
    evidence = first.evidence[0]
    with pytest.raises(FrozenInstanceError):
        first.change_score = 0
    with pytest.raises(FrozenInstanceError):
        evidence.reason = 'changed'
    replay = episode('S2').pipeline_results[5].drift_assessment
    assert first.reference == replay.reference
    assert evidence.reference == replay.evidence[0].reference


def test_minimum_history_numeric_no_change_transient_and_persistence():
    rows = episode('S2').pipeline_results
    statuses = [row.drift_assessment.status for row in rows]
    assert statuses[:3] == [DriftStatus.INSUFFICIENT_HISTORY] * 3
    assert statuses[3:5] == [DriftStatus.NO_CHANGE] * 2
    assert statuses[5] == DriftStatus.TRANSIENT_DEVIATION
    assert statuses[6:] == [DriftStatus.UNEXPLAINED_PERSISTENT_DRIFT] * 4
    assert [row.drift_assessment.persistence_count for row in rows[5:]] == [1, 2, 3, 4, 5]


def test_semantic_invalidity_supports_change_not_attack_claim():
    assessment = episode('S2').pipeline_results[6].drift_assessment
    assert assessment.status == DriftStatus.UNEXPLAINED_PERSISTENT_DRIFT
    assert assessment.to_dict()['score_semantics'].endswith('not probability of drift, regime, or attack.')
    assert {item.category for item in assessment.evidence} == {
        'NUMERIC_DISTRIBUTION_SHIFT', 'UNEXPLAINED_INVALID_SHIFT'}


def test_constant_invalid_values_are_no_change_after_history():
    rows = episode('S4').pipeline_results
    assert all(row.drift_assessment.status == DriftStatus.INSUFFICIENT_HISTORY
               for row in rows[:3])
    assert all(row.drift_assessment.status == DriftStatus.NO_CHANGE
               for row in rows[3:])


def test_known_mode_transition_and_context_explained_shift():
    rows = episode('S5').pipeline_results
    assert rows[5].drift_assessment.status == DriftStatus.KNOWN_REGIME_CHANGE
    assert 'OPERATING_MODE_CHANGE' in {
        item.category for item in rows[5].drift_assessment.evidence}
    assert all(row.drift_assessment.status == DriftStatus.KNOWN_REGIME_CHANGE
               for row in rows[5:])
    assert all(row.drift_assessment.context_explanation for row in rows[5:])
    assert all(row.operational_semantic_assessment.semantic_status.value == 'SUPPORTED_VALID'
               for row in rows[5:])


def test_s3_incomparable_register_semantics_never_create_numeric_drift():
    rows = episode('S3').pipeline_results
    assert all(row.drift_assessment.status == DriftStatus.INSUFFICIENT_SEMANTIC_SCOPE
               for row in rows)
    assert all(row.drift_assessment.change_score == 0 for row in rows)


def test_history_reset_and_prefix_causality():
    source_events = events('S2')
    full = drift_rows(source_events)
    prefix = drift_rows(source_events[:7])
    assert [row.to_dict() for row in full[:7]] == [row.to_dict() for row in prefix]
    detector = DriftDetector()
    semantics = OperationalSemanticModel()
    observation = runtime_observation(source_events[0])
    first = detector.assess(observation, semantics.assess(observation))
    detector.reset()
    reset = detector.assess(observation, semantics.assess(observation))
    assert first == reset


def test_no_retroactive_reclassification():
    source_events = events('S2')
    first_six = drift_rows(source_events[:6])
    full = drift_rows(source_events)
    assert first_six[5].status == DriftStatus.TRANSIENT_DEVIATION
    assert full[5] == first_six[5]
    assert full[6].status == DriftStatus.UNEXPLAINED_PERSISTENT_DRIFT


def test_rollback_restores_drift_history():
    class FailOnceRiskAgent:
        def __init__(self):
            self.delegate = RiskAgent()
            self.fail = True

        def assess(self, *args, **kwargs):
            if self.fail:
                self.fail = False
                raise ValueError('injected after-drift failure')
            return self.delegate.assess(*args, **kwargs)

    pipeline = TAIOSPipeline(risk_agent=FailOnceRiskAgent())
    event = events('S2')[0]
    with pytest.raises(PipelineProcessingError, match='injected after-drift failure'):
        pipeline.process_event(event, IndustrialState())
    result = pipeline.process_event(event, IndustrialState())
    assert result.drift_assessment.history_count == 0
    assert result.drift_assessment.status == DriftStatus.INSUFFICIENT_HISTORY


def test_s1_negative_control_has_no_unexplained_persistent_drift_seed42():
    assert all(row.drift_assessment.status != DriftStatus.UNEXPLAINED_PERSISTENT_DRIFT
               for row in episode('S1').pipeline_results)


def test_s6_is_entity_local_and_underspecified_activity_is_not_drift():
    rows = episode('S6').pipeline_results
    assert all(row.drift_assessment.status == DriftStatus.INSUFFICIENT_SEMANTIC_SCOPE
               for row in rows[3:])
    assert all('correlation' not in str(row.drift_assessment.to_dict()).lower()
               for row in rows)


def test_leakage_invariance_and_input_immutability():
    original = events('S2')
    changed = deepcopy(original)
    for event in changed:
        event.ground_truth = 'DIFFERENT'
        event.expected_safe_action = 'ISOLATE'
        event.scenario_id = 'OTHER'
        event.contextual_features.update(
            formal_evaluation=1, unsafe_action=True,
            attack_phase='changed', causal_label='changed')
    assert [runtime_observation(event) for event in original] == [
        runtime_observation(event) for event in changed]
    assert [row.to_dict() for row in drift_rows(original)] == [
        row.to_dict() for row in drift_rows(changed)]
    assert original == events('S2')


def test_pipeline_integration_is_audit_only_and_deterministic():
    first = episode('S6')
    second = episode('S6')
    assert [row.drift_assessment.to_dict() for row in first.pipeline_results] == [
        row.drift_assessment.to_dict() for row in second.pipeline_results]
    assert [row.trust_assessment.to_inference_dict() for row in first.pipeline_results] == [
        row.trust_assessment.to_inference_dict() for row in second.pipeline_results]
    assert [row.threat_assessment.to_dict() for row in first.pipeline_results] == [
        row.threat_assessment.to_dict() for row in second.pipeline_results]
    assert [row.risk_assessment.to_dict() for row in first.pipeline_results] == [
        row.risk_assessment.to_dict() for row in second.pipeline_results]
    assert [row.correlation_assessment.to_dict() for row in first.pipeline_results] == [
        row.correlation_assessment.to_dict() for row in second.pipeline_results]
    assert [row.experience_reference for row in first.pipeline_results] == [
        row.experience_reference for row in second.pipeline_results]
    assert [row.feedback_reference for row in first.pipeline_results] == [
        row.feedback_reference for row in second.pipeline_results]
    for key in ('proposals', 'governance_statuses', 'execution_statuses'):
        assert first.structural_summary[key] == second.structural_summary[key]


def test_downstream_audit_metadata_is_isolated_from_drift():
    row = episode('S2').pipeline_results[6]
    audited_trust = replace(row.trust_assessment,
                            audit=AuditCorrelation('audit-only', 999))
    assert audited_trust.audit is not None
    assert row.drift_assessment == drift_rows(events('S2'))[6]
