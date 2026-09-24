from copy import deepcopy
from dataclasses import replace

import pytest

from agents.risk_agent import RiskAgent
from agents.trust_agent import TrustAgent
from core.runtime_inputs import runtime_observation
from core.taios_pipeline import TAIOSPipeline
from core.trust_assessment import AuditCorrelation
from environment.event_generator import EventGenerator
from evaluation.evaluate_risk import assess_observations
from intelligence.authorization_engine import AuthorizationEngine
from intelligence.operational_semantic_model import OperationalSemanticModel
from intelligence.risk_input_builder import build_risk_input
from intelligence.threat_evidence_model import ThreatEvidenceModel


def events(scenario='S2', seed=42):
    generator = EventGenerator(seed, observable_state=True)
    run = generator.create_run(scenario, 10)
    return generator.generate(scenario, 10, run)


def episode(scenario='S2'):
    return TAIOSPipeline().run_episode(events(scenario), seed=42)


def test_direct_threat_signal_is_available_and_bound():
    row = episode('S2').pipeline_results[5]
    risk = row.risk_assessment
    assert risk.threat_available
    assert risk.threat_signal == risk.threat_probability == 0.7
    assert risk.threat_score_kind == 'SECURITY_SIGNAL'
    assert risk.threat_assessment_reference == row.threat_assessment.reference
    assert risk.threat_evidence_coverage == row.threat_assessment.evidence_coverage
    assert risk.threat_unavailable_reason is None
    assert risk.coverage == pytest.approx(0.85)


def test_uncertainty_only_is_unavailable_not_zero():
    row = episode('S3').pipeline_results[5]
    risk = row.risk_assessment
    assert not risk.threat_available
    assert risk.threat_signal is None
    assert risk.threat_unavailable_reason == 'THREAT_EVIDENCE_UNCERTAIN'
    assert risk.coverage == pytest.approx(0.45)


def test_complete_no_security_evidence_is_observed_zero_available():
    row = episode('S5').pipeline_results[0]
    assert row.threat_assessment.status.value == 'NO_SECURITY_EVIDENCE'
    assert row.threat_assessment.evidence_coverage == 1
    assert row.risk_assessment.threat_available
    assert row.risk_assessment.threat_signal == 0.0
    assert row.risk_assessment.coverage == pytest.approx(0.85)


def test_exact_renormalization_equation_and_anomaly_unchanged():
    risk = episode('S2').pipeline_results[5].risk_assessment
    expected = (0.40 * 0.7 + 0.25 * risk.distrust_score +
                0.20 * risk.criticality_score) / 0.85
    assert risk.risk_score == pytest.approx(expected)
    assert not risk.anomaly_available
    assert risk.component_availability['ANOMALY'] == 'EXCLUDED_CORRELATED'


def test_recurrence_is_not_double_counted():
    rows = episode('S2').pipeline_results
    assert rows[5].threat_assessment.direct_evidence_count == 1
    assert rows[6].threat_assessment.direct_evidence_count == 2
    assert rows[5].risk_assessment.threat_signal == rows[6].risk_assessment.threat_signal == 0.7
    assert rows[5].risk_assessment.effective_weights['THREAT'] == pytest.approx(0.4 / 0.85)
    assert rows[6].risk_assessment.effective_weights['THREAT'] == pytest.approx(0.4 / 0.85)


def test_threat_assessment_scope_binding():
    event = events()[5]
    observation = runtime_observation(event)
    trust = assess_observations([event], TrustAgent(), RiskAgent())[0][0]
    semantics = OperationalSemanticModel().assess(observation)
    authorization = AuthorizationEngine().assess(observation)
    threat = ThreatEvidenceModel().assess(observation, semantics, authorization)
    with pytest.raises(ValueError, match='scope'):
        build_risk_input(observation, trust,
                         threat_assessment=replace(threat, source_id='PLC-01'))


def test_backward_compatible_missing_threat_assessment():
    event = events()[0]
    observation = runtime_observation(event)
    trust = assess_observations([event], TrustAgent(), RiskAgent())[0][0]
    risk = RiskAgent().assess(observation, trust)
    assert risk.threat_signal is None
    assert not risk.threat_available
    assert risk.threat_unavailable_reason == 'NO_THREAT_ASSESSMENT'
    assert risk.coverage == pytest.approx(0.45)
    assert risk.model_version == 'day3c-model-v1'


def test_s2_s3_s4_s5_and_s6_behavior():
    s2 = episode('S2')
    assert all(row.risk_assessment.coverage == pytest.approx(0.85)
               for row in s2.pipeline_results)
    assert all(row.risk_assessment.threat_signal == 0 for row in s2.pipeline_results[:5])
    assert all(row.risk_assessment.threat_signal == 0.7 for row in s2.pipeline_results[5:])
    s3 = episode('S3')
    assert all(row.risk_assessment.coverage == pytest.approx(0.45)
               for row in s3.pipeline_results)
    s4 = episode('S4')
    assert all(row.risk_assessment.threat_signal == 0.7 for row in s4.pipeline_results)
    s5 = episode('S5')
    assert all(row.risk_assessment.threat_signal == 0 for row in s5.pipeline_results)
    assert all(row.risk_assessment.coverage == pytest.approx(0.85)
               for row in s5.pipeline_results)
    s6 = episode('S6')
    assert all(row.risk_assessment.threat_unavailable_reason in (
        None, 'THREAT_EVIDENCE_UNCERTAIN', 'THREAT_EVIDENCE_INCOMPLETE')
               for row in s6.pipeline_results)


def test_action_isolation_and_integration_model_version():
    distributions = {'proposals': {}, 'governance': {}, 'execution': {}}
    for scenario in (f'S{i}' for i in range(1, 7)):
        result = episode(scenario)
        for key, source in (
                ('proposals', result.structural_summary['proposals']),
                ('governance', result.structural_summary['governance_statuses']),
                ('execution', result.structural_summary['execution_statuses'])):
            for name, count in source.items():
                distributions[key][name] = distributions[key].get(name, 0) + count
        assert all(row.risk_assessment.model_version ==
                   'milestone6c-risk-threat-integration-v1'
                   for row in result.pipeline_results)
    assert distributions == {
        'proposals': {'ALLOW': 20, 'REQUEST_APPROVAL': 40},
        'governance': {'APPROVAL_REQUIRED': 40, 'APPROVED': 20},
        'execution': {'PENDING_APPROVAL': 40, 'SUCCEEDED': 20}}


def test_leakage_audit_determinism_and_input_immutability():
    original = events('S2')[5]
    changed = deepcopy(original)
    changed.ground_truth = 'BENIGN'
    changed.expected_safe_action = 'ALLOW'
    changed.scenario_id = 'OTHER'
    changed.contextual_features.update(anomaly_score=999, formal_evaluation=1)

    def assess(event):
        observation = runtime_observation(event)
        trust = assess_observations([event], TrustAgent(), RiskAgent())[0][0]
        semantics = OperationalSemanticModel().assess(observation)
        authorization = AuthorizationEngine().assess(observation)
        threat = ThreatEvidenceModel().assess(observation, semantics, authorization)
        return RiskAgent().assess(observation, trust, threat_assessment=threat)

    original_snapshot = deepcopy(original)
    first = assess(original)
    second = assess(changed)
    assert first.to_dict() == second.to_dict()
    assert original == original_snapshot


def test_audit_metadata_is_output_only_for_integrated_risk():
    event = events('S2')[5]
    observation = runtime_observation(event)
    trust = assess_observations([event], TrustAgent(), RiskAgent())[0][0]
    semantics = OperationalSemanticModel().assess(observation)
    authorization = AuthorizationEngine().assess(observation)
    threat = ThreatEvidenceModel().assess(observation, semantics, authorization)
    agent = RiskAgent()
    plain = agent.assess(observation, trust, threat_assessment=threat)
    audit = AuditCorrelation('audit-only', 999)
    attached = agent.assess(observation, trust, threat_assessment=threat,
                            correlation_metadata=audit)
    assert attached.to_inference_dict() == plain.to_inference_dict()
    assert attached.audit == audit


def test_integrated_risk_is_deterministic_for_identical_runs():
    first = episode('S2')
    second = episode('S2')
    assert [row.risk_assessment.to_dict() for row in first.pipeline_results] == [
        row.risk_assessment.to_dict() for row in second.pipeline_results]
    assert [row.pipeline_fingerprint for row in first.pipeline_results] == [
        row.pipeline_fingerprint for row in second.pipeline_results]
