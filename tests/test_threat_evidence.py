from copy import deepcopy
from dataclasses import FrozenInstanceError, replace

import pytest

from core.authorization import AuthorizationStatus
from core.runtime_inputs import runtime_observation
from core.threat_assessment import (
    ThreatAssessment, ThreatAssessmentStatus, ThreatEvidence, ThreatEvidenceClass,
)
from core.taios_pipeline import TAIOSPipeline
from environment.event_generator import EventGenerator
from environment.industrial_environment import IndustrialState
from intelligence.authorization_engine import AuthorizationEngine
from intelligence.operational_semantic_model import OperationalSemanticModel
from intelligence.threat_evidence_model import ThreatEvidenceModel


def events(scenario='S2', seed=42):
    generator = EventGenerator(seed, observable_state=True)
    run = generator.create_run(scenario, 10)
    return generator.generate(scenario, 10, run)


def assess(event, model=None):
    observation = runtime_observation(event)
    semantics = OperationalSemanticModel().assess(observation)
    authorization = AuthorizationEngine().assess(observation)
    return (model or ThreatEvidenceModel()).assess(observation, semantics, authorization)


def test_evidence_and_assessment_contracts_are_immutable_and_deterministic():
    first, second = assess(events()[5]), assess(events()[5])
    assert type(first) is ThreatAssessment
    assert all(type(item) is ThreatEvidence for item in first.evidence)
    assert first.to_dict() == second.to_dict()
    assert first.reference == second.reference
    with pytest.raises(FrozenInstanceError):
        first.status = ThreatAssessmentStatus.NO_SECURITY_EVIDENCE


def test_authentication_and_authorization_failure_are_direct_evidence():
    event = deepcopy(events()[0])
    event.authentication_status = False
    result = assess(event)
    categories = {item.evidence_type for item in result.evidence}
    assert {'AUTHENTICATION_FAILURE', 'AUTHORIZATION_FAILURE'} <= categories
    assert result.status == ThreatAssessmentStatus.DIRECT_EVIDENCE
    assert result.security_signal_score == 0.9


def test_operational_constraint_violation_is_factual_direct_evidence():
    result = assess(events('S2')[5])
    item = next(item for item in result.evidence
                if item.evidence_type == 'OPERATIONAL_CONSTRAINT_VIOLATION')
    assert item.evidence_class == ThreatEvidenceClass.DIRECT
    assert 'outside' in item.reason and '[20,80]' in item.reason
    assert 'malicious' not in item.reason.lower()


def test_semantic_underspecification_and_unsupported_are_uncertainty_only():
    s3 = assess(events('S3')[5])
    s1_unsupported = next(event for event in events('S1')
                          if OperationalSemanticModel().assess(
                              runtime_observation(event)).semantic_status.value == 'UNSUPPORTED')
    unsupported = assess(s1_unsupported)
    assert s3.status == ThreatAssessmentStatus.UNCERTAINTY_ONLY
    assert unsupported.status == ThreatAssessmentStatus.UNCERTAINTY_ONLY
    assert s3.security_signal_score == unsupported.security_signal_score == 0.0
    assert any(item.evidence_type == 'SEMANTIC_UNDERSPECIFICATION' for item in s3.evidence)
    assert any(item.evidence_type == 'UNSUPPORTED_SEMANTICS' for item in unsupported.evidence)


def test_repeated_violation_uses_only_prior_source_history():
    model = ThreatEvidenceModel()
    trajectory = [assess(event, model) for event in events('S2')]
    first = trajectory[5]
    second = trajectory[6]
    assert first.prior_operational_violation_count == 0
    assert not any(item.evidence_type == 'REPEATED_OPERATIONAL_VIOLATION'
                   for item in first.evidence)
    assert second.prior_operational_violation_count == 1
    assert any(item.evidence_type == 'REPEATED_OPERATIONAL_VIOLATION'
               for item in second.evidence)


def test_history_reset_and_prefix_causality():
    full_model = ThreatEvidenceModel()
    full = [assess(event, full_model).to_dict() for event in events('S2')]
    prefix_model = ThreatEvidenceModel()
    prefix = [assess(event, prefix_model).to_dict() for event in events('S2')[:7]]
    assert full[:7] == prefix
    full_model.reset()
    reset = assess(events('S2')[0], full_model)
    assert reset.source_history_version == 0


def test_s1_has_no_direct_security_evidence():
    model = ThreatEvidenceModel()
    trajectory = [assess(event, model) for event in events('S1')]
    assert all(row.direct_evidence_count == 0 for row in trajectory)


def test_s2_trajectory_adds_recurrence_without_labels():
    episode = TAIOSPipeline().run_episode(events('S2'), seed=42)
    rows = [result.threat_assessment for result in episode.pipeline_results]
    assert all(row.direct_evidence_count == 0 for row in rows[:5])
    assert rows[5].direct_evidence_count == 1
    assert all(row.direct_evidence_count == 2 for row in rows[6:])


def test_s3_remains_uncertainty_not_attack_verdict():
    episode = TAIOSPipeline().run_episode(events('S3'), seed=42)
    assert all(row.threat_assessment.status == ThreatAssessmentStatus.UNCERTAINTY_ONLY
               for row in episode.pipeline_results)
    assert all(row.threat_assessment.security_signal_score == 0
               for row in episode.pipeline_results)


def test_s4_preserves_decomposed_signals():
    episode = TAIOSPipeline().run_episode(events('S4'), seed=42)
    row = episode.pipeline_results[1]
    categories = {item.evidence_type for item in row.threat_assessment.evidence}
    assert 'OPERATIONAL_CONSTRAINT_VIOLATION' in categories
    assert 'REPEATED_OPERATIONAL_VIOLATION' in categories
    assert row.trust_assessment is not None
    assert row.authorization_assessment.status in AuthorizationStatus


def test_s5_high_output_does_not_emit_stale_range_evidence():
    episode = TAIOSPipeline().run_episode(events('S5'), seed=42)
    assert all(row.threat_assessment.direct_evidence_count == 0
               for row in episode.pipeline_results)
    assert all(not any(item.evidence_type == 'OPERATIONAL_CONSTRAINT_VIOLATION'
                       for item in row.threat_assessment.evidence)
               for row in episode.pipeline_results)


def test_s6_contains_only_local_evidence_and_no_coordination_claim():
    episode = TAIOSPipeline().run_episode(events('S6'), seed=42)
    assert all('COORDINATED' not in item.evidence_type
               for row in episode.pipeline_results for item in row.threat_assessment.evidence)
    assert all('coordination' not in reason.lower()
               for row in episode.pipeline_results
               for reason in row.threat_assessment.observable_reasons)


def test_leakage_and_audit_invariance():
    event = events('S2')[5]
    before = assess(event)
    changed = deepcopy(event)
    changed.ground_truth = 'BENIGN'
    changed.expected_safe_action = 'ALLOW'
    changed.scenario_id = 'OTHER'
    changed.event_id = 'OTHER'
    changed.sequence_number = 999
    changed.provenance = None
    changed.contextual_features.update(
        anomaly_score=999, transition='OTHER', causal_tags=['OTHER'],
        formal_evaluation_score=1.0)
    after = assess(changed)
    assert before.to_dict() == after.to_dict()


def test_pipeline_integration_and_action_behavior_unchanged():
    episode = TAIOSPipeline().run_episode(events('S2'), seed=42)
    assert all(result.threat_assessment is not None for result in episode.pipeline_results)
    assert episode.structural_summary['proposals'] == {'ALLOW': 5, 'REQUEST_APPROVAL': 5}
    assert episode.structural_summary['governance_statuses'] == {
        'APPROVAL_REQUIRED': 5, 'APPROVED': 5}
    assert episode.structural_summary['execution_statuses'] == {
        'PENDING_APPROVAL': 5, 'SUCCEEDED': 5}


def test_threat_assessment_does_not_mutate_inputs():
    event = events()[5]
    observation = runtime_observation(event)
    semantic = OperationalSemanticModel().assess(observation)
    authorization = AuthorizationEngine().assess(observation)
    before = (deepcopy(observation), semantic.to_dict(), authorization.to_dict())
    ThreatEvidenceModel().assess(observation, semantic, authorization)
    assert before == (observation, semantic.to_dict(), authorization.to_dict())
