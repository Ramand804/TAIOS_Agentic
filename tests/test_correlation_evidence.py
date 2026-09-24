from copy import deepcopy
from dataclasses import FrozenInstanceError, replace

import pytest

from agents.risk_agent import RiskAgent
from agents.trust_agent import TrustAgent
from core.correlation_assessment import (
    CorrelationAssessmentStatus, CorrelationEvidenceClass,
)
from core.runtime_inputs import runtime_observation
from core.taios_pipeline import TAIOSPipeline
from core.trust_assessment import AuditCorrelation
from environment.assets import get_asset
from environment.event_generator import EventGenerator
from environment.industrial_environment import IndustrialState
from intelligence.authorization_engine import AuthorizationEngine
from intelligence.correlation_evidence_model import CorrelationEvidenceModel
from intelligence.operational_semantic_model import OperationalSemanticModel
from intelligence.threat_evidence_model import ThreatEvidenceModel


def events(scenario='S6', seed=42):
    generator = EventGenerator(seed, observable_state=True)
    run = generator.create_run(scenario, 10)
    return generator.generate(scenario, 10, run)


def episode(scenario='S6', seed=42):
    return TAIOSPipeline().run_episode(events(scenario, seed), seed=seed)


def correlation_rows(source_events):
    semantics = OperationalSemanticModel()
    authorization = AuthorizationEngine()
    threats = ThreatEvidenceModel()
    correlations = CorrelationEvidenceModel()
    rows = []
    for event in source_events:
        observation = runtime_observation(event)
        semantic = semantics.assess(observation)
        authorized = authorization.assess(observation)
        threat = threats.assess(observation, semantic, authorized)
        rows.append(correlations.assess(observation, threat))
    return rows


def two_source_direct_events():
    source_events = events('S4')[:2]
    second = deepcopy(source_events[1])
    source = get_asset('PLC-04')
    second.source_id = source.asset_id
    second.source_type = source.asset_type
    second.network_zone = source.network_zone
    second.protocol = source.protocol
    return source_events[0], second


def test_contracts_are_immutable_and_references_deterministic():
    first, second = two_source_direct_events()
    assessment = correlation_rows((first, second))[1]
    item = assessment.evidence[0]
    with pytest.raises(FrozenInstanceError):
        item.strength = 1
    with pytest.raises(FrozenInstanceError):
        assessment.history_version = 99
    replay = correlation_rows((first, second))[1]
    assert assessment.reference == replay.reference
    assert item.reference == replay.evidence[0].reference


def test_same_target_direct_correlation_requires_multiple_sources():
    first, second = two_source_direct_events()
    rows = correlation_rows((first, second))
    assert rows[0].status == CorrelationAssessmentStatus.NO_CORRELATION_EVIDENCE
    assert rows[1].status == CorrelationAssessmentStatus.DIRECT_EVIDENCE
    assert rows[1].coordination_signal_score == 0.7
    assert 'MULTI_SOURCE_SAME_TARGET_SECURITY_ACTIVITY' in {
        item.category for item in rows[1].evidence}
    assert set(rows[1].participating_entities) == {'PLC-03', 'PLC-04'}


def test_shared_identity_direct_correlation_is_explicit():
    first, second = two_source_direct_events()
    assessment = correlation_rows((first, second))[1]
    shared = [item for item in assessment.evidence
              if item.category == 'SHARED_IDENTITY_MULTI_SOURCE_SECURITY_ACTIVITY']
    assert len(shared) == 1
    assert shared[0].evidence_class == CorrelationEvidenceClass.DIRECT
    assert shared[0].relationship_type == 'SHARED_IDENTITY'


def test_single_source_recurrence_is_not_cross_entity_coordination():
    result = episode('S2')
    assert all(row.correlation_assessment.status ==
               CorrelationAssessmentStatus.NO_CORRELATION_EVIDENCE
               for row in result.pipeline_results)
    assert all(row.correlation_assessment.coordination_signal_score == 0
               for row in result.pipeline_results)


def test_uncertainty_relationship_never_becomes_positive_signal():
    result = episode('S6')
    correlated = [row.correlation_assessment for row in result.pipeline_results
                  if row.correlation_assessment.evidence]
    assert correlated
    assert all(row.status == CorrelationAssessmentStatus.UNCERTAINTY_ONLY
               and row.coordination_signal_score == 0 for row in correlated)
    assert all(item.evidence_class == CorrelationEvidenceClass.UNCERTAINTY
               for row in correlated for item in row.evidence)


@pytest.mark.parametrize('scenario', ('S1', 'S2', 'S3', 'S4', 'S5'))
def test_negative_controls_have_no_direct_correlation(scenario):
    assert all(row.correlation_assessment.status !=
               CorrelationAssessmentStatus.DIRECT_EVIDENCE
               for row in episode(scenario).pipeline_results)


def test_s6_continuous_trajectory_first_uncertainty_is_event_four():
    result = episode('S6')
    statuses = [row.correlation_assessment.status for row in result.pipeline_results]
    assert statuses[:3] == [CorrelationAssessmentStatus.NO_CORRELATION_EVIDENCE] * 3
    assert statuses[3] == CorrelationAssessmentStatus.UNCERTAINTY_ONLY
    assert all(status != CorrelationAssessmentStatus.DIRECT_EVIDENCE for status in statuses)
    assert result.pipeline_results[3].correlation_assessment.participating_entities == (
        'HMI-02', 'SERVICE-03')


def test_history_window_and_reset_are_deterministic():
    model = CorrelationEvidenceModel()
    source_events = events('S6')
    first = correlation_rows(source_events)[4]
    assert first.history_version == 4
    model.reset()
    observation = runtime_observation(source_events[0])
    semantic = OperationalSemanticModel().assess(observation)
    authorization = AuthorizationEngine().assess(observation)
    threat = ThreatEvidenceModel().assess(observation, semantic, authorization)
    assert model.assess(observation, threat).history_version == 0


def test_prefix_causality():
    source_events = events('S6')
    full = correlation_rows(source_events)
    prefix = correlation_rows(source_events[:6])
    assert [row.to_dict() for row in full[:6]] == [row.to_dict() for row in prefix]


def test_pipeline_records_correlation_without_changing_risk_or_actions():
    source_events = events('S6')
    first = TAIOSPipeline().run_episode(source_events, seed=42)
    second = TAIOSPipeline().run_episode(source_events, seed=42)
    assert all(row.correlation_assessment is not None for row in first.pipeline_results)
    assert [row.risk_assessment.to_dict() for row in first.pipeline_results] == [
        row.risk_assessment.to_dict() for row in second.pipeline_results]
    assert first.structural_summary == second.structural_summary


def test_failure_after_correlation_rolls_back_history():
    class FailOnceRiskAgent:
        def __init__(self):
            self.delegate = RiskAgent()
            self.fail = True

        def assess(self, *args, **kwargs):
            if self.fail:
                self.fail = False
                raise ValueError('injected risk failure')
            return self.delegate.assess(*args, **kwargs)

    pipeline = TAIOSPipeline(risk_agent=FailOnceRiskAgent())
    event = events('S6')[0]
    with pytest.raises(Exception, match='injected risk failure'):
        pipeline.process_event(event, IndustrialState())
    result = pipeline.process_event(event, IndustrialState())
    assert result.correlation_assessment.history_version == 0


def test_leakage_invariance_and_input_immutability():
    originals = events('S6')
    changed = deepcopy(originals)
    for event in changed:
        event.scenario_id = 'OTHER'
        event.ground_truth = 'BENIGN'
        event.expected_safe_action = 'ALLOW'
        event.contextual_features.update(
            compromise_phase=True, coordination_group='DIFFERENT', formal_evaluation=1)
    snapshot = deepcopy(originals)
    assert [row.to_dict() for row in correlation_rows(originals)] == [
        row.to_dict() for row in correlation_rows(changed)]
    assert originals == snapshot


def test_audit_metadata_is_outside_correlation_inference():
    class AuditedTrustAgent(TrustAgent):
        def assess(self, *args, **kwargs):
            result = super().assess(*args, **kwargs)
            return replace(result, audit=AuditCorrelation('different-audit', 999))

    source_events = events('S6')
    plain = TAIOSPipeline().run_episode(source_events)
    audited = TAIOSPipeline(trust_agent=AuditedTrustAgent()).run_episode(source_events)
    assert [row.correlation_assessment.to_dict() for row in plain.pipeline_results] == [
        row.correlation_assessment.to_dict() for row in audited.pipeline_results]
    assert all(row.trust_assessment.audit is not None for row in audited.pipeline_results)


def test_all_scenarios_preserve_frozen_action_distribution():
    proposals, governance, execution = {}, {}, {}
    for scenario in (f'S{i}' for i in range(1, 7)):
        summary = episode(scenario).structural_summary
        for destination, key in ((proposals, 'proposals'),
                                 (governance, 'governance_statuses'),
                                 (execution, 'execution_statuses')):
            for name, count in summary[key].items():
                destination[name] = destination.get(name, 0) + count
    assert proposals == {'ALLOW': 20, 'REQUEST_APPROVAL': 40}
    assert governance == {'APPROVAL_REQUIRED': 40, 'APPROVED': 20}
    assert execution == {'PENDING_APPROVAL': 40, 'SUCCEEDED': 20}
