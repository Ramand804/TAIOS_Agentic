from copy import deepcopy
from dataclasses import FrozenInstanceError, replace

import pytest

from core.experience_record import ExperienceRecord
from core.observed_outcome import ObservedOutcome, OutcomeStatus
from core.pipeline_result import PipelineProcessingError
from core.runtime_inputs import runtime_observation
from core.taios_pipeline import TAIOSPipeline
from core.trust_assessment import AuditCorrelation
from environment.event_generator import EventGenerator
from environment.industrial_environment import IndustrialState
from intelligence.experience_builder import build_experience_record
from intelligence.outcome_observer import OutcomeObserver
from memory.episodic_memory import EpisodicMemory


def events(scenario='S2', seed=42):
    generator = EventGenerator(seed, observable_state=True)
    run = generator.create_run(scenario, 10)
    return generator.generate(scenario, 10, run)


def run(scenario='S2', seed=42):
    pipeline = TAIOSPipeline()
    result = pipeline.run_episode(events(scenario, seed), seed=seed)
    return pipeline, result


def rebuild_experience(row, trust=None):
    return build_experience_record(
        event_reference=row.event_reference, observation=dict(row.observable_input),
        semantics=row.operational_semantic_assessment, threat=row.threat_assessment,
        correlation=row.correlation_assessment,
        trust=row.trust_assessment if trust is None else trust,
        risk=row.risk_assessment, authorization=row.authorization_assessment,
        authority=row.authority_assessment, planning=row.planning_result,
        proposal=row.proposed_decision, governance=row.governance_decision,
        execution=row.execution_result, outcome=row.observed_outcome,
        state_before=row.state_before, state_after=row.state_after)


def test_observed_outcome_is_immutable_and_deterministic():
    _, result = run('S2')
    outcome = result.pipeline_results[0].observed_outcome
    with pytest.raises(FrozenInstanceError):
        outcome.mutation_observed = False
    _, replay = run('S2')
    assert outcome.reference == replay.pipeline_results[0].observed_outcome.reference
    assert outcome.to_dict() == replay.pipeline_results[0].observed_outcome.to_dict()


def test_successful_mutation_and_pending_outcomes():
    _, result = run('S2')
    rows = result.pipeline_results
    assert all(row.observed_outcome.outcome_status ==
               OutcomeStatus.EXECUTED_MUTATION_OBSERVED for row in rows[:5])
    assert all(row.observed_outcome.mutation_observed for row in rows[:5])
    assert all(row.observed_outcome.outcome_status ==
               OutcomeStatus.PENDING_EXTERNAL_APPROVAL for row in rows[5:])
    assert all(row.observed_outcome.unresolved_outcome_fields ==
               ('external_approval_decision', 'future_execution_effect') for row in rows[5:])


def test_successful_noop_is_observed_as_success_not_failure():
    _, result = run('S5')
    row = result.pipeline_results[6]
    assert row.execution_result.execution_status.value == 'SUCCEEDED'
    assert not row.execution_result.mutation_applied
    assert row.observed_outcome.outcome_status == OutcomeStatus.EXECUTED_NOOP_OBSERVED
    assert row.observed_outcome.state_version_before == row.observed_outcome.state_version_after


def test_experience_is_immutable_and_binds_complete_chain():
    pipeline, result = run('S6')
    row = result.pipeline_results[4]
    experience = pipeline.memory.records[4]
    assert type(experience) is ExperienceRecord
    with pytest.raises(FrozenInstanceError):
        experience.risk_score = 1
    assert experience.reference == row.experience_reference
    assert experience.correlation_assessment_reference == row.correlation_assessment.reference
    assert experience.execution_result_reference == row.execution_result.reference
    assert experience.observed_outcome_reference == row.observed_outcome.reference
    assert experience.state_before_reference == row.execution_result.state_before_reference
    assert experience.state_after_reference == row.execution_result.state_after_reference


def test_memory_append_and_all_retrieval_apis():
    pipeline, result = run('S2')
    memory = pipeline.memory
    assert memory.count == result.experience_count == 10
    first = memory.records[0]
    assert first in memory.get_by_event(first.event_reference)
    assert memory.get_by_source('PLC-07') == memory.records
    assert memory.get_by_target('MOTOR-02') == memory.records
    assert memory.get_by_operation('set_speed') == memory.records
    assert memory.recent(3) == memory.records[-3:]
    assert memory.recent(0) == ()


def test_memory_order_reset_and_fingerprint():
    pipeline, first = run('S2')
    original_records = pipeline.memory.records
    original_fingerprint = first.memory_fingerprint
    reversed_memory = EpisodicMemory()
    for record in reversed(original_records):
        reversed_memory.append(record)
    assert reversed_memory.memory_fingerprint != original_fingerprint
    pipeline.run_episode(events('S3'), seed=42)
    assert pipeline.memory.count == 10
    assert all(record.source_id == 'HMI-02' for record in pipeline.memory.records)


def test_same_episode_reproduces_experiences_and_memory_fingerprint():
    first_pipeline, first = run('S2')
    second_pipeline, second = run('S2')
    assert first_pipeline.memory.records == second_pipeline.memory.records
    assert [record.reference for record in first_pipeline.memory.records] == [
        record.reference for record in second_pipeline.memory.records]
    assert first.memory_fingerprint == second.memory_fingerprint


def test_exact_replay_does_not_commit_duplicate_experience():
    pipeline = TAIOSPipeline()
    event = events('S2')[0]
    first = pipeline.process_event(event, IndustrialState())
    replay = pipeline.process_event(event, first.state_after)
    assert pipeline.memory.count == 1
    assert replay.execution_result.execution_status.value == 'ALREADY_EXECUTED'
    assert replay.observed_outcome.outcome_status == OutcomeStatus.DUPLICATE_EXECUTION_PREVENTED
    assert replay.experience_reference == first.experience_reference


def test_pipeline_outcome_failure_rolls_back_all_state_and_memory():
    class FailOnceObserver(OutcomeObserver):
        def __init__(self):
            self.fail = True

        def observe(self, *args, **kwargs):
            if self.fail:
                self.fail = False
                raise ValueError('injected outcome failure')
            return super().observe(*args, **kwargs)

    pipeline = TAIOSPipeline(outcome_observer=FailOnceObserver())
    event = events('S2')[0]
    with pytest.raises(PipelineProcessingError, match='injected outcome failure'):
        pipeline.process_event(event, IndustrialState())
    assert pipeline.memory.count == 0
    result = pipeline.process_event(event, IndustrialState())
    assert result.execution_result.execution_status.value == 'SUCCEEDED'
    assert pipeline.memory.count == 1
    assert result.trust_assessment.trust_state_version == 1
    assert result.threat_assessment.source_history_version == 0
    assert result.correlation_assessment.history_version == 0


def test_s3_all_experiences_remain_pending_without_correctness_claim():
    pipeline, result = run('S3')
    assert pipeline.memory.count == 10
    assert all(row.observed_outcome.outcome_status ==
               OutcomeStatus.PENDING_EXTERNAL_APPROVAL for row in result.pipeline_results)
    assert all(not row.observed_outcome.mutation_observed for row in result.pipeline_results)


def test_s5_regime_continuity_and_noop_experience():
    pipeline, result = run('S5')
    outcomes = [row.observed_outcome for row in result.pipeline_results]
    assert [row.operating_mode_after for row in outcomes[:5]] == ['NORMAL'] * 5
    assert [row.operating_mode_after for row in outcomes[5:]] == ['HIGH_OUTPUT'] * 5
    assert sum(row.outcome_status == OutcomeStatus.EXECUTED_NOOP_OBSERVED
               for row in outcomes) == 1
    assert pipeline.memory.records[6].observed_outcome_reference == outcomes[6].reference


def test_s6_experience_records_local_and_correlation_references_only():
    pipeline, result = run('S6')
    for record, row in zip(pipeline.memory.records, result.pipeline_results):
        assert record.threat_assessment_reference == row.threat_assessment.reference
        assert record.correlation_assessment_reference == row.correlation_assessment.reference
    assert all(record.risk_score == row.risk_assessment.risk_score
               for record, row in zip(pipeline.memory.records, result.pipeline_results))


def test_leakage_fields_are_absent_from_outcome_experience_and_memory():
    original = events('S2')
    changed = deepcopy(original)
    for event in changed:
        event.ground_truth = 'DIFFERENT'
        event.expected_safe_action = 'ISOLATE'
        event.scenario_id = 'OTHER'
        event.contextual_features.update(
            formal_evaluation=1, attack_phase='changed', causal_label='changed')
    assert [runtime_observation(event) for event in original] == [
        runtime_observation(event) for event in changed]
    pipeline, result = run('S2')
    serialized = str([row.observed_outcome.to_dict() for row in result.pipeline_results]) + \
        str([record.to_dict() for record in pipeline.memory.records])
    for forbidden in ('ground_truth', 'expected_safe_action', 'scenario_id',
                      'formal_evaluation', 'attack_phase', 'causal_label'):
        assert forbidden not in serialized


def test_audit_metadata_is_excluded_from_experience_reference():
    _, result = run('S2')
    row = result.pipeline_results[0]
    audited = replace(row.trust_assessment,
                      audit=AuditCorrelation('audit-only', 999))
    assert rebuild_experience(row, audited) == rebuild_experience(row)


def test_outcome_and_memory_do_not_change_risk_correlation_or_actions():
    _, first = run('S6')
    _, second = run('S6')
    assert [row.risk_assessment.to_dict() for row in first.pipeline_results] == [
        row.risk_assessment.to_dict() for row in second.pipeline_results]
    assert [row.correlation_assessment.to_dict() for row in first.pipeline_results] == [
        row.correlation_assessment.to_dict() for row in second.pipeline_results]
    assert first.structural_summary['proposals'] == second.structural_summary['proposals']
    assert first.structural_summary['governance_statuses'] == second.structural_summary['governance_statuses']
    assert first.structural_summary['execution_statuses'] == second.structural_summary['execution_statuses']
