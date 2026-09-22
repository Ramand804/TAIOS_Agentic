from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json

import pytest

from core.runtime_inputs import runtime_observation
from core.trust_evidence import TrustEvidence, attach_audit_correlation
from environment.event_generator import EventGenerator
from intelligence.trust_evidence_extractor import EvidenceConfig, TrustEvidenceExtractor


def observation(mode='NORMAL', value=60):
    result = runtime_observation(EventGenerator().generate('S2', 1)[0])
    result['contextual_features']['operating_mode'] = mode
    result['requested_value'] = value
    return result


def by_dimension(records):
    return {e.dimension.value: e for e in records}


def test_model_and_correlation():
    evidence = TrustEvidence('asset:PLC-01', 'DEVICE', 'POSITIVE', .2, .5, 'fixture', 'Registered device.')
    assert evidence.effective_magnitude == .1
    assert json.loads(json.dumps(evidence.to_dict())) == evidence.to_dict()
    with pytest.raises(FrozenInstanceError): evidence.strength = .4
    correlated = attach_audit_correlation([evidence], event_id='EXP-S2-E000001', sequence_number=1)[0]
    assert evidence.event_id is None
    assert replace(correlated, event_id=None, sequence_number=None) == evidence
    with pytest.raises(ValueError): attach_audit_correlation([correlated], event_id='other', sequence_number=2)


@pytest.mark.parametrize('field,value', [
    ('strength', -1), ('strength', 1.1), ('strength', True), ('strength', float('nan')),
    ('confidence', -1), ('confidence', 1.1), ('confidence', float('inf')), ('confidence', '0.5'),
    ('entity_id', ''), ('reason', '  '), ('source', ''), ('dimension', 'RISK'),
    ('direction', 'SAFE'), ('event_id', 'unpaired'), ('sequence_number', 0),
])
def test_invalid_model(field, value):
    args = dict(entity_id='asset:A', dimension='DEVICE', direction='POSITIVE', strength=.1, confidence=.5,
                source='test', reason='Test observation.')
    args[field] = value
    with pytest.raises(ValueError): TrustEvidence(**args)


def test_identity_cases():
    extractor = TrustEvidenceExtractor()
    o = observation()
    e = by_dimension(extractor.extract(o))['IDENTITY']
    assert e.direction == 'POSITIVE' and e.strength == .1 and e.effective_magnitude == .05
    o['authentication_status'] = False
    assert by_dimension(extractor.extract(o))['IDENTITY'].direction == 'NEGATIVE'
    o['identity_id'] = 'unknown'
    o['authentication_status'] = True
    e = by_dimension(extractor.extract(o))['IDENTITY']
    assert e.direction == 'NEUTRAL' and e.effective_magnitude == 0
    o['authentication_status'] = False
    assert by_dimension(extractor.extract(o))['IDENTITY'].direction == 'NEGATIVE'


@pytest.mark.parametrize('field,value', [('source_type','HMI'),('protocol','https'),('network_zone','enterprise')])
def test_device_reference_mismatch(field, value):
    o = observation()
    extractor = TrustEvidenceExtractor()
    assert by_dimension(extractor.extract(o))['DEVICE'].direction == 'POSITIVE'
    o[field] = value
    e = by_dimension(extractor.extract(o))['DEVICE']
    assert e.direction == 'NEGATIVE' and field in e.reason


def test_unknown_source_is_uncertain():
    o = observation(); o['source_id'] = 'UNKNOWN'
    evidence = by_dimension(TrustEvidenceExtractor().extract(o))['DEVICE']
    assert evidence.direction == 'NEUTRAL' and evidence.effective_magnitude == 0


@pytest.mark.parametrize('mode,value,direction,strength', [
    ('NORMAL',60,'POSITIVE',.1), ('NORMAL',90,'NEGATIVE',1/6),
    ('HIGH_OUTPUT',90,'POSITIVE',.1), ('MAINTENANCE',90,'NEGATIVE',1),
])
def test_behavior_current_mode(mode,value,direction,strength):
    e = by_dimension(TrustEvidenceExtractor().extract(observation(mode,value)))['BEHAVIOR']
    assert e.direction == direction
    assert e.strength == pytest.approx(strength)
    assert e.confidence == .5


def test_missing_limits_and_mode():
    o = observation(); extractor = TrustEvidenceExtractor()
    o['operation'] = 'write_register'
    assert 'MISSING_LIMIT' in by_dimension(extractor.extract(o))['BEHAVIOR'].reason
    o = observation(); o['contextual_features'].pop('operating_mode')
    assert 'MISSING_MODE' in by_dimension(extractor.extract(o))['BEHAVIOR'].reason


def test_context_and_history_are_neutral():
    extractor = TrustEvidenceExtractor(); o = observation()
    e = by_dimension(extractor.extract(o))
    assert e['CONTEXT'].direction == 'NEUTRAL' and 'NO_CONTEXT_RULE' in e['CONTEXT'].reason
    assert e['HISTORY'].direction == 'NEUTRAL' and e['HISTORY'].effective_magnitude == 0
    o['contextual_features'] = {}
    assert 'MISSING_CONTEXT' in by_dimension(extractor.extract(o))['CONTEXT'].reason


@pytest.mark.parametrize('scenario', [f'S{i}' for i in range(1,7)])
def test_leakage_metamorphic_and_determinism(scenario):
    event = EventGenerator().generate(scenario,10)[-1]
    extractor = TrustEvidenceExtractor()
    safe = runtime_observation(event); original = deepcopy(safe)
    evidence = extractor.extract(safe)
    assert safe == original and evidence == extractor.extract(safe)
    event.ground_truth = 'OTHER'
    event.expected_safe_action = 'OTHER'
    event.scenario_id = 'S-SECRET'
    event.provenance = None
    event.event_id = 'secret-id'; event.sequence_number = 999
    event.experiment_id = 'secret-run'
    event.contextual_features.update({'compromise_phase': True, 'causal_tags': ['POST_COMPROMISE'],
        'anomaly_score': 999, 'prior_device_trust': 0, 'simulated_attack_probability': 1,
        'regime_change_sequence': 99, 'drift_phase': 'post', 'state_snapshot': {'hidden': 1}})
    assert extractor.extract(runtime_observation(event)) == evidence
    assert all(e.event_id is None and e.sequence_number is None for e in evidence)


def test_raw_or_enriched_inputs_rejected():
    extractor = TrustEvidenceExtractor(); event = EventGenerator().generate('S2',1)[0]
    for value in (event, event.to_dict(), dict(observation(), ground_truth='BENIGN')):
        with pytest.raises(ValueError): extractor.extract(value)
    o = observation(); o['contextual_features']['compromise_phase'] = True
    with pytest.raises(ValueError): extractor.extract(o)


def test_authentication_independent_of_negative_behavior():
    records = by_dimension(TrustEvidenceExtractor().extract(observation('NORMAL',90)))
    assert records['IDENTITY'].direction == 'POSITIVE'
    assert records['BEHAVIOR'].direction == 'NEGATIVE'


def test_s2_missing_mode_before_after():
    events = EventGenerator().generate('S2',10)
    extractor = TrustEvidenceExtractor()
    assert extractor.extract(runtime_observation(events[4])) == extractor.extract(runtime_observation(events[5]))
    assert 'MISSING_MODE' in by_dimension(extractor.extract(runtime_observation(events[5])))['BEHAVIOR'].reason


def test_s3_reports_missing_reference():
    events = EventGenerator().generate('S3',10)
    for event in (events[4],events[5]):
        e = by_dimension(TrustEvidenceExtractor().extract(runtime_observation(event)))
        assert e['IDENTITY'].direction == 'POSITIVE'
        assert e['BEHAVIOR'].direction == 'NEUTRAL' and 'MISSING_LIMIT' in e['BEHAVIOR'].reason


def test_s5_current_mode_not_hidden_phase():
    events = EventGenerator().generate('S5',10); extractor = TrustEvidenceExtractor()
    for event in events:
        assert by_dimension(extractor.extract(runtime_observation(event)))['BEHAVIOR'].direction == 'POSITIVE'
    o = runtime_observation(events[5]); o['contextual_features']['operating_mode'] = 'NORMAL'
    assert by_dimension(extractor.extract(o))['BEHAVIOR'].direction == 'NEGATIVE'


@pytest.mark.parametrize('field,value', [('identity_confidence',2),('device_negative_strength',float('nan')),
                                       ('deviation_saturation',0),('deviation_saturation',True)])
def test_invalid_config(field,value):
    with pytest.raises(ValueError): replace(EvidenceConfig.load(), **{field:value})


def test_configuration_controls_strength():
    config = replace(EvidenceConfig.load(), behavior_positive_strength=.2, behavior_confidence=.3)
    e = by_dimension(TrustEvidenceExtractor(config).extract(observation()))['BEHAVIOR']
    assert e.effective_magnitude == .06


def test_audit_fields_cannot_influence_inference():
    records = TrustEvidenceExtractor().extract(observation())
    first = attach_audit_correlation(records,event_id='S2-post-compromise',sequence_number=6)
    second = attach_audit_correlation(records,event_id='S5-benign',sequence_number=1)
    assert [replace(e,event_id=None,sequence_number=None) for e in first] == [replace(e,event_id=None,sequence_number=None) for e in second]


def test_correlation_requires_metadata_even_for_empty_evidence():
    with pytest.raises(ValueError):
        attach_audit_correlation([], event_id=None, sequence_number=None)
