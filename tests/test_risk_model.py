from dataclasses import FrozenInstanceError, replace
import math

import pytest

from core.risk_input import COMPONENTS, RiskConfig, RiskInput
from intelligence.risk_model import MODEL_VERSION, RiskModel
from tests.test_risk_inputs import run


def fixture(**changes):
    values = dict(source_id='source', target_id='target', operation='fixture',
        composite_trust=.8, distrust_score=.2, criticality_score=.9, trust_state_version=1,
        trust_evidence_coverage={k: ['INSUFFICIENT'] for k in ('IDENTITY','DEVICE','BEHAVIOR','HISTORY','CONTEXT')},
        prior_only_dimensions=(), config=RiskConfig.load(), reasons=('Observable fixture.',))
    values.update(changes)
    return RiskInput(**values)


@pytest.mark.parametrize('signals,coverage,expected', [
    ({}, .45, .23/.45),
    ({'threat_available':True,'threat_probability':.5,'threat_score_kind':'CONFIDENCE'}, .85, .43/.85),
    ({'anomaly_available':True,'anomaly_score':.4,'anomaly_category':'INDEPENDENT'}, .60, .29/.60),
    ({'threat_available':True,'threat_probability':.5,'threat_score_kind':'CONFIDENCE',
      'anomaly_available':True,'anomaly_score':.4,'anomaly_category':'INDEPENDENT'}, 1., .49),
])
def test_hand_calculable_math(signals, coverage, expected):
    item=fixture(**signals); before=item.to_dict()
    result=RiskModel().evaluate(item)
    assert result.risk_score == pytest.approx(expected)
    assert result.coverage == pytest.approx(coverage)
    assert math.fsum(result.effective_weights.values()) == pytest.approx(1)
    assert math.fsum(result.component_contributions.values()) == pytest.approx(result.risk_score)
    assert result.original_weights == item.original_weights
    assert item.to_dict() == before
    assert result.to_dict()['configuration_fingerprint'] == item.config.fingerprint
    assert result.model_version == MODEL_VERSION


def test_one_usable_component_and_none():
    # Frozen contract requires trust/criticality values: zero their weights,
    # rather than claiming these are missing-data fixtures under default config.
    config=RiskConfig(dict(zip(COMPONENTS,(.4,0,0,.6))))
    one=fixture(config=config,threat_available=True,threat_probability=.7,threat_score_kind='CONFIDENCE')
    result=RiskModel().evaluate(one)
    assert result.coverage == .4
    assert result.effective_weights['THREAT'] == 1
    assert result.risk_score == .7
    none=RiskModel().evaluate(fixture(config=config))
    assert none.risk_score is None
    assert none.coverage == 0
    assert all(v is None for v in none.effective_weights.values())
    assert all(v is None for v in none.component_contributions.values())
    assert none.to_inference_dict()['assessment_status'] == 'INSUFFICIENT_INPUTS'


@pytest.mark.parametrize('component', ['threat','anomaly'])
def test_missing_differs_from_known_zero(component):
    original=fixture()
    changes=({'threat_probability':0.,'threat_available':True,'threat_score_kind':'CONFIDENCE'}
             if component=='threat' else
             {'anomaly_score':0.,'anomaly_available':True,'anomaly_category':'INDEPENDENT'})
    missing=RiskModel().evaluate(original)
    zero=RiskModel().evaluate(replace(original,**changes))
    assert zero.risk_score < missing.risk_score
    assert zero.coverage > missing.coverage
    assert zero.effective_weights[component.upper()] > 0
    assert zero.component_contributions[component.upper()] == 0
    assert missing.effective_weights[component.upper()] == 0


@pytest.mark.parametrize('value',[0.,.2,1.])
@pytest.mark.parametrize('threat,anomaly',[(False,False),(True,False),(False,True),(True,True)])
def test_bounds(value,threat,anomaly):
    item=fixture(composite_trust=1-value,distrust_score=value,criticality_score=value,
        threat_probability=value if threat else None,threat_available=threat,
        threat_score_kind='CONFIDENCE' if threat else 'UNAVAILABLE',
        anomaly_score=value if anomaly else None,anomaly_available=anomaly,
        anomaly_category='INDEPENDENT' if anomaly else 'NONE')
    result=RiskModel().evaluate(item)
    assert 0 <= result.risk_score <= 1
    assert result.risk_score == pytest.approx(value)


def test_determinism_immutability_and_strict_boundary():
    item=fixture(); model=RiskModel()
    result=model.evaluate(item)
    assert result.to_dict() == model.evaluate(item).to_dict() == RiskModel().evaluate(item).to_dict()
    with pytest.raises(FrozenInstanceError): result.risk_score=0
    with pytest.raises(TypeError): result.component_contributions['THREAT']=1
    for bad in (item.to_dict(), result, None, run()[0][0], run()[1][0]):
        with pytest.raises(ValueError): model.evaluate(bad)


@pytest.mark.parametrize('scenario',['S1','S2','S3','S5'])
def test_leakage(scenario):
    from agents.trust_agent import TrustAgent
    from core.runtime_inputs import runtime_observation
    from core.trust_assessment import AuditCorrelation
    from evaluation.evaluate_trust import assess_observations
    from intelligence.risk_input_builder import build_risk_input
    events,_,inputs=run(scenario)
    for event in events:
        event.ground_truth='MALICIOUS'; event.expected_safe_action='ISOLATE'; event.scenario_id='HIDDEN'
        event.provenance=replace(event.provenance,phase='HIDDEN',transition_type='HIDDEN',causal_tags=('HIDDEN',))
        event.contextual_features.update(anomaly_score=1,simulated_attack_probability=1,compromise_phase=True)
    assessments=assess_observations(events,TrustAgent())
    model=RiskModel()
    for e,a,original in zip(events,assessments,inputs):
        changed=build_risk_input(runtime_observation(e),replace(a,audit=AuditCorrelation('OTHER',999)))
        assert model.evaluate(original).to_dict() == model.evaluate(changed).to_dict()


def test_double_counting_and_independent_fixture():
    item=run()[2][5]; model=RiskModel()
    result=model.evaluate(item)
    assert result.anomaly_score is None
    assert result.component_contributions['ANOMALY'] == 0
    independent=replace(item,anomaly_score=.5,anomaly_available=True,anomaly_category='INDEPENDENT')
    assert model.evaluate(independent).component_contributions['ANOMALY'] == pytest.approx(.15/.6*.5)


def test_scenario_properties():
    model=RiskModel()
    s2=[model.evaluate(i) for i in run()[2]]
    for before,after in zip(s2[4:7],s2[5:8]):
        assert after.composite_trust < before.composite_trust
        assert after.distrust_score > before.distrust_score
        assert after.risk_score > before.risk_score
        assert after.risk_score-before.risk_score == pytest.approx((.25/.45)*(after.distrust_score-before.distrust_score))
    s3=model.evaluate(run('S3')[2][5])
    assert s3.coverage == .45
    assert s3.coverage_details['status'] == 'INCOMPLETE'
    assert s3.trust_evidence_coverage['BEHAVIOR'] == ('INSUFFICIENT',)
    s5=[model.evaluate(i) for i in run('S5')[2]]
    assert s5[4].risk_score >= s5[5].risk_score >= s5[6].risk_score
    assert all(i.component_contributions['ANOMALY']==0 for i in s5)
    assert model.evaluate(run('S1')[2][5]).risk_score > 0
