from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import json

import pytest

from agents.trust_agent import TrustAgent
from core.risk_input import COMPONENTS, RiskConfig, RiskInput
from core.risk_assessment import RiskAssessment
from core.runtime_inputs import runtime_observation
from core.trust_assessment import AuditCorrelation
from environment.assets import get_asset
from environment.event_generator import EventGenerator
from environment.validators import EventIntegrityError
from evaluation.evaluate_trust import assess_observations
from intelligence.risk_input_builder import build_risk_input


def run(scenario='S2'):
    events = EventGenerator(42, observable_state=True).generate(scenario, 10)
    assessments = assess_observations(events, TrustAgent())
    inputs = [build_risk_input(runtime_observation(e), a) for e, a in zip(events, assessments)]
    return events, assessments, inputs


@pytest.fixture
def example():
    return run()[2][5]


def test_current_contract_and_weights(example):
    assert example.distrust_score == 1-example.composite_trust
    assert example.criticality_score == get_asset(example.target_id).criticality == .91
    assert example.criticality_score != get_asset(example.source_id).criticality
    assert example.threat_probability is example.anomaly_score is None
    assert example.threat_available is example.anomaly_available is False
    assert example.coverage == .45
    assert example.original_weights == dict(zip(COMPONENTS, (.4, .25, .2, .15)))
    assert example.effective_weights['TRUST'] == .25/.45
    assert example.effective_weights['CRITICALITY'] == .20/.45
    assert example.effective_weights['THREAT'] == example.effective_weights['ANOMALY'] == 0
    assert example.coverage_details['status'] == 'INCOMPLETE'
    assert not hasattr(example, 'risk_score')
    assert not hasattr(example, 'audit')
    json.dumps(example.to_dict(), allow_nan=False)


def test_nested_immutability_and_export_copies(example):
    with pytest.raises(FrozenInstanceError):
        example.distrust_score = .9
    for mapping in (example.original_weights, example.effective_weights, example.trust_evidence_coverage):
        with pytest.raises(TypeError):
            mapping[next(iter(mapping))] = 0
    exported = example.to_dict()
    exported['trust_evidence_coverage']['BEHAVIOR'].clear()
    exported['original_weights']['THREAT'] = 0
    exported['reasons'].clear()
    assert example.trust_evidence_coverage['BEHAVIOR'] == ('NEGATIVE',)
    assert example.original_weights['THREAT'] == .4
    assert example.reasons
    coverage = {k: list(v) for k, v in example.trust_evidence_coverage.items()}
    copied = replace(example, trust_evidence_coverage=coverage)
    coverage['BEHAVIOR'].clear()
    assert copied == example


@pytest.mark.parametrize('field', ['composite_trust', 'distrust_score', 'criticality_score'])
@pytest.mark.parametrize('bad', [-.01, 1.01, float('nan'), float('inf'), True])
def test_scalar_bounds(example, field, bad):
    with pytest.raises(ValueError):
        replace(example, **{field: bad})


@pytest.mark.parametrize('signal', ['threat', 'anomaly'])
@pytest.mark.parametrize('bad', [-1, 2, float('nan'), float('inf'), False])
def test_available_signal_bounds(example, signal, bad):
    changes = ({'threat_available': True, 'threat_probability': bad, 'threat_score_kind': 'CONFIDENCE'}
               if signal == 'threat' else
               {'anomaly_available': True, 'anomaly_score': bad, 'anomaly_category': 'INDEPENDENT'})
    with pytest.raises(ValueError):
        replace(example, **changes)


@pytest.mark.parametrize('changes', [
    {'threat_available': True}, {'threat_probability': 0}, {'threat_available': 1},
    {'anomaly_available': True}, {'anomaly_score': 0}, {'anomaly_available': 0},
    {'distrust_score': .9}, {'trust_state_version': -1}, {'trust_state_version': True},
    {'source_id': ''}, {'reasons': ()}, {'reasons': 'text'},
    {'threat_score_kind': 'CALIBRATED_PROBABILITY'}, {'anomaly_category': 'INDEPENDENT'},
    {'trust_evidence_coverage': {}}, {'prior_only_dimensions': ('OTHER',)},
])
def test_contradictions_rejected(example, changes):
    with pytest.raises(ValueError):
        replace(example, **changes)


def test_known_zero_is_not_missing(example):
    # Explicit independent test fixtures only; the builder has no such detector.
    zero_threat = replace(example, threat_available=True, threat_probability=0.0,
                          threat_score_kind='CONFIDENCE')
    zero_anomaly = replace(example, anomaly_available=True, anomaly_score=0.0,
                           anomaly_category='INDEPENDENT')
    assert zero_threat.component_availability['THREAT'] == 'AVAILABLE'
    assert zero_anomaly.component_availability['ANOMALY'] == 'AVAILABLE'
    assert zero_threat.coverage == pytest.approx(.85)
    assert zero_anomaly.coverage == pytest.approx(.60)
    assert example.to_dict() != zero_threat.to_dict() != zero_anomaly.to_dict()


def test_correlated_signal_cannot_be_enabled(example):
    assert example.anomaly_category == 'OPERATIONAL_LIMIT_SHARED_WITH_TRUST'
    with pytest.raises(ValueError):
        replace(example, anomaly_available=True, anomaly_score=.5)


def test_builder_source_mismatch():
    events, assessments, _ = run()
    other = run('S5')[1][0]
    with pytest.raises(ValueError, match='entity'):
        build_risk_input(runtime_observation(events[0]), other)
    with pytest.raises(ValueError, match='TrustAssessment'):
        build_risk_input(runtime_observation(events[0]), assessments[0].to_dict())


@pytest.mark.parametrize('change', [
    {'asset_criticality': .92}, {'target_id': 'UNKNOWN'}, {'source_id': 'UNKNOWN'},
    {'source_type': 'service'}, {'network_zone': 'enterprise'}, {'protocol': 'https'},
    {'target_type': 'PLC'},
])
def test_shared_asset_integrity(change):
    events, assessments, _ = run()
    observation = runtime_observation(events[0])
    observation.update(change)
    with pytest.raises(EventIntegrityError):
        build_risk_input(observation, assessments[0])


@pytest.mark.parametrize('change', [
    {'asset_criticality': float('nan')}, {'asset_criticality': True},
    {'asset_criticality': -1}, {'authentication_status': 'yes'},
    {'contextual_features': {'operating_mode': 'UNDEFINED'}},
    {'contextual_features': {'ground_truth': 'MALICIOUS'}},
    {'scenario_id': 'S2'},
])
def test_invalid_projection(change):
    events, assessments, _ = run()
    observation = runtime_observation(events[0])
    observation.update(change)
    with pytest.raises(ValueError):
        build_risk_input(observation, assessments[0])


def test_raw_events_and_evaluation_rows_rejected():
    events, assessments, _ = run()
    for raw in (events[0], events[0].to_dict()):
        with pytest.raises(ValueError):
            build_risk_input(raw, assessments[0])


@pytest.mark.parametrize('scenario', ['S1', 'S2', 'S3', 'S5'])
def test_scenario_determinism_and_availability(scenario):
    events, assessments, inputs = run(scenario)
    repeated = run(scenario)[2]
    assert [x.to_dict() for x in inputs] == [x.to_dict() for x in repeated]
    for event, assessment, item in zip(events, assessments, inputs):
        assert item.composite_trust == assessment.composite_trust
        assert item.trust_state_version == assessment.trust_state_version
        assert item.coverage == .45
        assert not item.threat_available and not item.anomaly_available
        assert item.criticality_score == get_asset(event.target_id).criticality
        assert item.to_dict() == build_risk_input(runtime_observation(event), assessment).to_dict()


def test_s2_degradation_and_s5_mode_change():
    _, assessments, inputs = run()
    for i in range(5, 8):
        assert inputs[i].distrust_score > inputs[i-1].distrust_score
        assert assessments[i].evidence_coverage['BEHAVIOR'] == ['NEGATIVE']
        assert inputs[i].anomaly_score is None
        assert inputs[i].component_availability['ANOMALY'] == 'EXCLUDED_CORRELATED'
    events, _, inputs = run('S5')
    assert events[4].contextual_features['operating_mode'] == 'NORMAL'
    assert events[5].contextual_features['operating_mode'] == 'HIGH_OUTPUT'
    for i in (5, 6):
        assert inputs[i].distrust_score <= inputs[i-1].distrust_score
        assert inputs[i].anomaly_score is None
        assert inputs[i].trust_evidence_coverage['BEHAVIOR'] == ('POSITIVE',)


def test_s3_and_missing_mode_preserve_insufficiency():
    _, _, inputs = run('S3')
    assert inputs[5].trust_evidence_coverage['BEHAVIOR'] == ('INSUFFICIENT',)
    assert inputs[5].component_availability['ANOMALY'] == 'MISSING'
    assert inputs[5].coverage_details['status'] == 'INCOMPLETE'
    event = EventGenerator().generate('S2', 1)[0]
    o = runtime_observation(event)
    assessment = TrustAgent().assess(o, delivery_token='x', observation_number=1)
    item = build_risk_input(o, assessment)
    assert item.anomaly_score is None
    assert item.trust_evidence_coverage['BEHAVIOR'] == ('INSUFFICIENT',)


@pytest.mark.parametrize('scenario', ['S1', 'S2', 'S3', 'S5'])
def test_hidden_label_and_audit_mutation_invariance(scenario):
    events, assessments, inputs = run(scenario)
    changed = deepcopy(events)
    for event in changed:
        event.ground_truth = 'MALICIOUS'
        event.expected_safe_action = 'ISOLATE'
        event.scenario_id = 'HIDDEN-OTHER'
        event.provenance = replace(event.provenance, phase='OTHER', transition_type='OTHER', causal_tags=('OTHER',))
        event.event_id = 'unrelated'; event.timestamp = 'other'; event.sequence_number = 999
        event.contextual_features.update(anomaly_score=1, simulated_attack_probability=1,
            prior_device_trust=0, compromise_phase=True, compromise_marker=True, causal_tags=['OTHER'])
    other_assessments = assess_observations(changed, TrustAgent())
    for event, a, b, original in zip(changed, assessments, other_assessments, inputs):
        with_audit = replace(b, audit=AuditCorrelation('different', 999))
        assert a.to_inference_dict() == b.to_inference_dict()
        assert build_risk_input(runtime_observation(event), with_audit).to_dict() == original.to_dict()


def test_config_canonical_and_identity(tmp_path):
    config = RiskConfig.load()
    assert config.fingerprint == RiskConfig.load().fingerprint
    modified = RiskConfig(dict(zip(COMPONENTS, (.3, .35, .2, .15))))
    assert modified.fingerprint != config.fingerprint
    bad = tmp_path/'risk.yaml'
    bad.write_text('risk:\n  weights:\n    threat: 0.4\n')
    with pytest.raises(ValueError): RiskConfig.load(bad)
    for weights in ({}, dict(zip(COMPONENTS, (0, 0, 0, 0))),
                    dict(zip(COMPONENTS, (True, 0, 0, 0))), dict(zip(COMPONENTS, (float('nan'), 0, 0, 0)))):
        with pytest.raises(ValueError): RiskConfig(weights)


def test_all_unavailable_weight_mass(example):
    config = RiskConfig(dict(zip(COMPONENTS, (1, 0, 0, 0))))
    item = replace(example, config=config)
    assert item.coverage == 0
    assert all(x is None for x in item.effective_weights.values())
    assert item.coverage_details['status'] == 'INSUFFICIENT_INPUTS'


def test_assessment_contract_validation_and_audit(example):
    # Hand-specified zero-valued contract fixture, not a generated risk result.
    item = replace(example, composite_trust=1., distrust_score=0., criticality_score=0.)
    kwargs = {f.name: getattr(item, f.name) for f in fields(RiskInput)}
    result = RiskAssessment(**kwargs, risk_score=0.,
        component_contributions={key: 0. for key in COMPONENTS}, model_version='contract-fixture')
    with_audit = replace(result, audit=AuditCorrelation('audit-only', 1))
    assert result.to_inference_dict() == with_audit.to_inference_dict()
    assert result.to_dict() != with_audit.to_dict()
    with pytest.raises(FrozenInstanceError): result.risk_score = 1
    with pytest.raises(TypeError): result.component_contributions['THREAT'] = 1
    for change in ({'risk_score': None}, {'risk_score': 1}, {'risk_score': float('nan')},
                   {'audit': {}}, {'component_contributions': {}}, {'model_version': ''},
                   {'component_contributions': dict(zip(COMPONENTS, (.1, 0, 0, 0)))}):
        with pytest.raises(ValueError): replace(result, **change)
    empty = replace(item, config=RiskConfig(dict(zip(COMPONENTS, (1, 0, 0, 0)))))
    kwargs = {f.name: getattr(empty, f.name) for f in fields(RiskInput)}
    no_score = RiskAssessment(**kwargs, risk_score=None,
        component_contributions={key: None for key in COMPONENTS}, model_version='contract-fixture')
    assert no_score.to_inference_dict()['assessment_status'] == 'INSUFFICIENT_INPUTS'
