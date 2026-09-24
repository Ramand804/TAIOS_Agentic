from dataclasses import FrozenInstanceError, replace

import pytest

from adaptation.behavioral_adapter import BehavioralAdapter
from core.behavioral_reference import (
    AdaptationDecision, AdaptationMode, AdaptationProposal, AdaptationStatus,
    BehavioralReferenceSnapshot, ProposalStatus,
)
from core.feedback_assessment import FeedbackStatus
from core.pipeline_result import PipelineProcessingError
from core.taios_pipeline import TAIOSPipeline
from environment.event_generator import EventGenerator
from environment.industrial_environment import IndustrialState
from memory.behavioral_reference_store import BehavioralReferenceStore


def episode(scenario, *, seed=42, mode=AdaptationMode.ADAPTIVE):
    generator = EventGenerator(seed, observable_state=True)
    run = generator.create_run(scenario, 10)
    events = generator.generate(scenario, 10, run)
    pipeline = TAIOSPipeline(adaptation_mode=mode)
    result = pipeline.run_episode(events, scenario_reference=run.experiment_id, seed=seed)
    return pipeline, result, events


def test_contracts_are_immutable_and_references_are_deterministic():
    snapshot = BehavioralReferenceSnapshot(
        scope='PLC-01|MOTOR-02|set_speed', sample_count=2,
        reference_summary={'count': 2, 'mean': 85.0, 'minimum': 85, 'maximum': 85},
        operating_context={'operating_mode': 'HIGH_OUTPUT', 'production_state': 'ACTIVE'},
        version=1, provenance_references=('a', 'b'), model_version='v1')
    same = BehavioralReferenceSnapshot(**snapshot.to_dict())
    assert snapshot.reference == same.reference
    with pytest.raises(FrozenInstanceError):
        snapshot.version = 2
    proposal = AdaptationProposal(
        trigger_drift_reference='d', event_reference='e', scope=snapshot.scope,
        context_key='c', status=ProposalStatus.ELIGIBLE, current_reference=None,
        candidate_reference='candidate',
        candidate_summary={'mean': 85}, observable_support=('a', 'b'),
        semantic_support='SUPPORTED_VALID', feedback_support='OBSERVABLE_FEEDBACK',
        unresolved_requirements=(), proposal_version='v1', configuration_fingerprint='f')
    decision = AdaptationDecision(
        proposal_reference=proposal.reference, status=AdaptationStatus.APPLIED,
        reasons=('supported',), authorized_update=True, before_reference=None,
        after_reference=snapshot.reference, policy_version='v1', configuration_fingerprint='f')
    assert proposal.reference == AdaptationProposal(**proposal.to_dict()).reference
    assert decision.reference == AdaptationDecision(**decision.to_dict()).reference
    with pytest.raises(FrozenInstanceError):
        decision.status = AdaptationStatus.REJECTED


def test_baseline_bank_versions_and_separates_contexts():
    store = BehavioralReferenceStore()
    def snap(mode, mean, version=1):
        return BehavioralReferenceSnapshot(
            scope='PLC-01|MOTOR-02|set_speed', sample_count=2,
            reference_summary={'count': 2, 'mean': mean, 'minimum': mean, 'maximum': mean},
            operating_context={'operating_mode': mode, 'production_state': 'ACTIVE'},
            version=version, provenance_references=('a', 'b'), model_version='v1')
    normal, high = snap('NORMAL', 50), snap('HIGH_OUTPUT', 85)
    store.put(normal); store.put(high)
    assert store.get(normal.scope, dict(normal.operating_context)) == normal
    assert store.get(high.scope, dict(high.operating_context)) == high
    assert len(store.snapshots) == 2


def test_static_mode_preserves_frozen_drift_and_never_applies():
    _, static, _ = episode('S5', mode=AdaptationMode.STATIC)
    assert [r.drift_assessment.status.value for r in static.pipeline_results] == [
        'INSUFFICIENT_HISTORY'] * 3 + ['NO_CHANGE'] * 2 + ['KNOWN_REGIME_CHANGE'] * 5
    assert all(r.adaptation_decision.status == AdaptationStatus.NOT_ELIGIBLE
               for r in static.pipeline_results)
    assert all(r.behavioral_reference_used is None for r in static.pipeline_results)


def test_s5_adapts_after_two_supported_observations_and_uses_reference():
    pipeline, result, _ = episode('S5')
    rows = result.pipeline_results
    assert rows[5].adaptation_decision.status == AdaptationStatus.DEFERRED
    assert rows[6].adaptation_proposal.status == ProposalStatus.ELIGIBLE
    assert rows[6].adaptation_decision.status == AdaptationStatus.APPLIED
    assert [r.drift_assessment.status.value for r in rows[7:]] == ['NO_CHANGE'] * 3
    assert all(r.behavioral_reference_used for r in rows[7:])
    snapshot, = pipeline.behavioral_adapter.store.snapshots
    assert snapshot.version == 1
    assert snapshot.sample_count == 2
    assert dict(snapshot.reference_summary) == {
        'count': 2, 'mean': 85.0, 'minimum': 85, 'maximum': 85}


def test_existing_context_reference_is_not_continuously_relearned():
    pipeline, result, _ = episode('S5', seed=456)
    applied = [r for r in result.pipeline_results
               if r.adaptation_decision.status == AdaptationStatus.APPLIED]
    assert [r.sequence_number for r in applied] == [7]
    snapshot, = pipeline.behavioral_adapter.store.snapshots
    assert snapshot.version == 1


def test_s2_unexplained_drift_is_rejected_and_cannot_poison_reference():
    pipeline, result, _ = episode('S2')
    rows = result.pipeline_results
    assert rows[5].adaptation_decision.status == AdaptationStatus.NOT_ELIGIBLE
    assert all(r.adaptation_decision.status == AdaptationStatus.REJECTED for r in rows[6:])
    assert pipeline.behavioral_adapter.store.snapshots == ()
    assert all(r.behavioral_reference_used is None for r in rows)


@pytest.mark.parametrize('scenario', ('S1', 'S3', 'S4', 'S6'))
def test_negative_control_scenarios_do_not_adapt(scenario):
    pipeline, result, _ = episode(scenario)
    assert not any(r.adaptation_decision.status == AdaptationStatus.APPLIED
                   for r in result.pipeline_results)
    assert pipeline.behavioral_adapter.store.snapshots == ()


def test_pending_feedback_defers_known_regime_support():
    pipeline, result, _ = episode('S5', mode=AdaptationMode.STATIC)
    source = result.pipeline_results[5]
    feedback = pipeline.feedback_memory.get_by_event(source.event_reference)[0]
    pending = replace(feedback, feedback_status=FeedbackStatus.PENDING_EXTERNAL_FEEDBACK)
    adapter = BehavioralAdapter(mode=AdaptationMode.ADAPTIVE)
    proposal, decision = adapter.evaluate(
        dict(source.observable_input), source.operational_semantic_assessment,
        source.drift_assessment, pending)
    assert proposal.status == ProposalStatus.DEFERRED
    assert decision.status == AdaptationStatus.DEFERRED
    assert adapter.store.snapshots == ()


def test_reset_removes_episode_reference_and_support_state():
    pipeline, _, _ = episode('S5')
    assert pipeline.behavioral_adapter.store.snapshots
    pipeline.reset()
    assert pipeline.behavioral_adapter.store.snapshots == ()
    assert pipeline.behavioral_adapter.history == ()


def test_prefix_causality_and_no_future_feedback():
    _, full, events = episode('S5')
    prefix_pipeline = TAIOSPipeline(adaptation_mode=AdaptationMode.ADAPTIVE)
    prefix = prefix_pipeline.run_episode(events[:7], seed=42)
    assert [r.adaptation_decision.reference for r in prefix.pipeline_results] == [
        r.adaptation_decision.reference for r in full.pipeline_results[:7]]
    assert prefix.pipeline_results[-1].adaptation_decision.status == AdaptationStatus.APPLIED


class FailAfterApplication(BehavioralAdapter):
    def __init__(self):
        super().__init__(mode=AdaptationMode.ADAPTIVE)
        self.fail = True

    def evaluate(self, observation, semantics, drift, feedback):
        proposal, decision = super().evaluate(observation, semantics, drift, feedback)
        if self.fail and decision.status == AdaptationStatus.APPLIED:
            self.fail = False
            raise ValueError('injected failure after adaptation')
        return proposal, decision


def test_transactional_rollback_restores_bank_and_retry_is_identical():
    generator = EventGenerator(42, observable_state=True)
    run = generator.create_run('S5', 10)
    events = generator.generate('S5', 10, run)
    adapter = FailAfterApplication()
    pipeline = TAIOSPipeline(behavioral_adapter=adapter)
    # A supplied adapter determines mode; wire its store into the detector explicitly.
    pipeline.drift_detector.behavioral_reference_store = adapter.store
    pipeline.drift_detector.adaptive = True
    state = IndustrialState()
    completed = []
    for event in events[:6]:
        result = pipeline.process_event(event, state)
        completed.append(result)
        state = result.state_after
    with pytest.raises(PipelineProcessingError):
        pipeline.process_event(events[6], state)
    assert adapter.store.snapshots == ()
    retry = pipeline.process_event(events[6], state)
    clean = TAIOSPipeline(adaptation_mode=AdaptationMode.ADAPTIVE).run_episode(
        events[:7], seed=42).pipeline_results[-1]
    assert retry.adaptation_decision.reference == clean.adaptation_decision.reference
    assert adapter.store.snapshots[0].reference == clean.adaptation_decision.after_reference


def test_leakage_and_downstream_audit_fields_do_not_change_adaptation():
    _, original, events = episode('S5')
    pipeline = TAIOSPipeline(adaptation_mode=AdaptationMode.ADAPTIVE)
    replay = pipeline.run_episode(
        events, scenario_reference='different-evaluator-only-reference', seed=42)
    assert [r.adaptation_decision.status for r in replay.pipeline_results] == [
        r.adaptation_decision.status for r in original.pipeline_results]
    assert [r.drift_assessment.status for r in replay.pipeline_results] == [
        r.drift_assessment.status for r in original.pipeline_results]


def test_adaptation_isolated_from_inference_and_actions():
    _, static, events = episode('S5', mode=AdaptationMode.STATIC)
    adaptive_pipeline = TAIOSPipeline(adaptation_mode=AdaptationMode.ADAPTIVE)
    adaptive = adaptive_pipeline.run_episode(events, seed=42)
    for before, after in zip(static.pipeline_results, adaptive.pipeline_results):
        assert before.trust_assessment == after.trust_assessment
        assert before.threat_assessment == after.threat_assessment
        assert before.correlation_assessment == after.correlation_assessment
        assert before.risk_assessment == after.risk_assessment
        assert before.proposed_decision == after.proposed_decision
        assert before.governance_decision == after.governance_decision
        assert before.execution_result == after.execution_result
        assert before.experience_reference == after.experience_reference
        assert before.feedback_reference == after.feedback_reference
