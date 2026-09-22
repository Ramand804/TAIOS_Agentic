from dataclasses import FrozenInstanceError, replace
import pytest
from agents.trust_agent import TrustAgent
from core.runtime_inputs import runtime_observation
from core.trust_assessment import AuditCorrelation
from environment.event_generator import EventGenerator
from intelligence.trust_model import TrustModel
from intelligence.trust_evidence_extractor import TrustEvidenceExtractor


def events(scenario='S2'):
    return EventGenerator(observable_state=True).generate(scenario,10)


def assess(agent,event,n=1,**kwargs):
    return agent.assess(runtime_observation(event),delivery_token=f'token-{n}',observation_number=n,**kwargs)


def test_assessment_matches_model_counts_delta_and_immutability():
    event=events()[0]; a=assess(TrustAgent(),event)
    model=TrustModel(); model.initialize_entity(a.entity_id)
    state=model.update(a.entity_id,TrustEvidenceExtractor().extract(runtime_observation(event)),delivery_token='a',observation_number=1)
    assert a.composite_trust==state.composite_trust
    assert a.previous_composite_trust==.8
    assert a.trust_delta==a.composite_trust-.8
    assert (a.evidence_count,a.positive_evidence_count,a.negative_evidence_count,a.neutral_evidence_count)==(5,3,0,2)
    assert a.evidence_coverage['HISTORY']==['INSUFFICIENT']
    assert a.trust_state_version==a.observation_count==1
    with pytest.raises(FrozenInstanceError): a.composite_trust=0
    exported=a.to_dict(); exported['evidence'][0]['strength']=99
    assert a.evidence[0].strength==.1
    assert all(0<=getattr(a,name)<=1 for name in ('identity_trust','device_trust','behavioral_trust','historical_trust','contextual_trust','composite_trust'))


@pytest.mark.parametrize('change',[{'identity_trust':-1},{'composite_trust':2},{'trust_delta':1},{'reasons':()}, {'audit':{'scenario':'S2'}}])
def test_assessment_validation(change):
    with pytest.raises(ValueError): replace(assess(TrustAgent(),events()[0]),**change)


def test_reset_replay_isolation_and_order():
    agent=TrustAgent(); source=events(); first=assess(agent,source[0]); second=assess(agent,source[1],2)
    assert second.observation_count==2
    for n in (1,4):
        with pytest.raises(ValueError): assess(agent,source[2],n)
    other=assess(agent,events('S5')[0])
    assert other.observation_count==1 and other.previous_composite_trust==.8
    third=assess(agent,source[2],3)
    assert third.observation_count==3
    agent.reset()
    assert assess(agent,source[0])==first
    assert assess(agent,source[1],2)==second


@pytest.mark.parametrize('scenario',['S2','S3','S5'])
def test_replay_and_leakage(scenario):
    left,right=TrustAgent(),TrustAgent()
    for n,event in enumerate(events(scenario),1):
        a=assess(left,event,n,correlation_metadata=AuditCorrelation('original',n))
        event.ground_truth='OTHER';event.expected_safe_action='OTHER';event.provenance=None;event.scenario_id='OTHER'
        event.contextual_features.update(compromise_phase=True,causal_tags=['OTHER'],anomaly_score=999)
        b=assess(right,event,n,correlation_metadata=AuditCorrelation('different',999))
        assert a.to_inference_dict()==b.to_inference_dict()
        assert a.audit!=b.audit


def test_raw_input_and_bad_correlation_rejected_without_update():
    agent=TrustAgent(); e=events()[0]
    for value in (e,e.to_dict()):
        with pytest.raises(ValueError): agent.assess(value,delivery_token='x',observation_number=1)
    with pytest.raises(ValueError): assess(agent,e,correlation_metadata={'scenario':'S2'})
    assert assess(agent,e).observation_count==1


def test_s2_reasons_and_decrease():
    agent=TrustAgent(); result=[assess(agent,e,n) for n,e in enumerate(events(),1)]
    assert result[4].negative_evidence_count==0
    a=result[5]
    assert a.evidence_coverage['BEHAVIOR']==['NEGATIVE']
    assert a.behavioral_trust_delta<0 and a.trust_delta<0
    reason=a.reasons[2]
    for term in ('set_speed','97','NORMAL','80'): assert term in reason
    assert not any(term in ' '.join(a.reasons) for term in ('POST_COMPROMISE','DEVICE_COMPROMISE','compromised'))


def test_s3_insufficiency_and_s5_current_mode():
    agent=TrustAgent()
    a=assess(agent,events('S3')[5])
    assert a.evidence_coverage['IDENTITY']==['POSITIVE']
    assert a.evidence_coverage['BEHAVIOR']==a.evidence_coverage['CONTEXT']==['INSUFFICIENT']
    assert 'MISSING_LIMIT' in a.reasons[2]
    agent.reset()
    results=[assess(agent,e,n) for n,e in enumerate(events('S5'),1)]
    assert 'NORMAL' in results[4].reasons[2] and '[20, 80]' in results[4].reasons[2]
    assert 'HIGH_OUTPUT' in results[5].reasons[2] and '[60, 95]' in results[5].reasons[2]
    assert results[5].evidence_coverage['BEHAVIOR']==['POSITIVE']
