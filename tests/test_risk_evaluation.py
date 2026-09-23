from copy import deepcopy
from dataclasses import replace
import pytest
from agents.trust_agent import TrustAgent
from agents.risk_agent import RiskAgent
from core.runtime_inputs import runtime_observation
from environment.event_generator import EventGenerator
from evaluation.evaluate_risk import assess_observations, trajectory_records, evaluate_run, evaluate_suite
from evaluation.evaluate_trust import stable_json
from evaluation.risk_metrics import risk_metrics, with_risk_deltas, TOLERANCE


def rows(values=(.2,.4,.3,.5)):
    return [dict(source_id='a',target_id='b',operation='x',sequence_number=n,phase='PRE' if n<3 else 'POST',
        ground_truth='BENIGN' if n<3 else 'MALICIOUS',risk_score=v,coverage=.45,
        component_availability={'THREAT':'MISSING','TRUST':'AVAILABLE','CRITICALITY':'AVAILABLE','ANOMALY':'MISSING'},
        component_contributions={'THREAT':0 if v is not None else None,'ANOMALY':0 if v is not None else None,
                                 'TRUST':v-.1 if v is not None else None,'CRITICALITY':.1 if v is not None else None})
        for n,v in enumerate(values,1)]


def test_hand_calculable_metrics():
    m=risk_metrics(rows(),3)
    assert m['initial_risk']==.2 and m['final_risk']==.5
    assert m['net_risk_change']==pytest.approx(.3)
    assert m['minimum_risk']==.2 and m['maximum_risk']==.5
    assert m['mean_risk']==pytest.approx(.35)
    assert m['pre_mean_risk']==pytest.approx(.3) and m['post_mean_risk']==pytest.approx(.4)
    assert m['signed_risk_escalation']==pytest.approx(.1)
    assert m['risk_response_delay']=={'status':'OBSERVED','sequence_delay':1}
    assert m['mean_absolute_risk_update']==pytest.approx(.5/3)
    assert m['false_escalation_count']==1 and m['false_escalation_rate']==1
    assert m['positive_risk_response_rate']==.5
    assert m['contributions']['TRUST']['mean']==pytest.approx(.25)
    assert m['contributions']['CRITICALITY']['transition_change']==0
    assert m['contributions']['CRITICALITY']['mean_share']==pytest.approx((.5+.25+1/3+.2)/4)
    assert m['mean_coverage']==m['min_coverage']==m['max_coverage']==.45
    assert m['availability_rates']=={'THREAT':0,'TRUST':1,'CRITICALITY':1,'ANOMALY':0}


def test_delay_sign_tolerance_and_missing_transition():
    assert risk_metrics(rows((.2,.3,.4)),3)['risk_response_delay']['sequence_delay']==0
    m=risk_metrics(rows((.4,.3,.2)),3)
    assert m['signed_risk_escalation']<0
    assert m['risk_response_delay']=={'status':'NOT_OBSERVED','sequence_delay':None}
    m=risk_metrics(rows((.2,.2+TOLERANCE/2)))
    assert m['false_escalation_count']==0
    assert m['risk_response_delay']['status']=='NOT_APPLICABLE'
    assert m['pre_mean_risk'] is m['post_mean_risk'] is None


def test_empty_null_zero_and_no_bridge():
    m=risk_metrics([])
    assert m['mean_risk'] is m['false_escalation_rate'] is m['positive_risk_response_rate'] is None
    m=risk_metrics(rows((.2,None,.4)),2)
    assert m['null_risk_count']==1 and m['mean_risk']==pytest.approx(.3)
    assert m['eligible_update_count']==0 and m['mean_absolute_risk_update'] is None
    assert risk_metrics(rows((None,None)))['final_risk'] is None
    assert risk_metrics(rows((0.,)))['contributions']['CRITICALITY']['mean_share'] is None
    assert risk_metrics(rows((None,.2)))['initial_risk'] is None


def test_matched_groups_not_adjacent_unrelated_events():
    r=rows((.2,.9,.3))
    r[1]['source_id']='other'
    out=with_risk_deltas(r)
    assert out[0]['risk_delta'] is out[1]['risk_delta'] is None
    assert out[2]['risk_delta']==pytest.approx(.1)
    assert risk_metrics(r)['mean_absolute_risk_update']==pytest.approx(.1)
    r[2]['target_id']='different'
    assert risk_metrics(r)['eligible_update_count']==0


@pytest.mark.parametrize('scenario',['S1','S2','S3','S5'])
def test_label_and_phase_boundary(scenario):
    events=EventGenerator(42,observable_state=True).generate(scenario,10)
    ta,ra=assess_observations(events,TrustAgent(),RiskAgent())
    original=trajectory_records(events,ta,ra)
    changed=deepcopy(events)
    for event in changed:
        event.ground_truth='MALICIOUS';event.expected_safe_action='ISOLATE';event.scenario_id='OTHER'
        event.provenance=replace(event.provenance,phase='OTHER',transition_type='OTHER',causal_tags=('OTHER',))
        event.contextual_features.update(anomaly_score=1,simulated_attack_probability=1)
    tb,rb=assess_observations(changed,TrustAgent(),RiskAgent())
    assert [a.to_inference_dict() for a in ta]==[a.to_inference_dict() for a in tb]
    assert [a.to_inference_dict() for a in ra]==[a.to_inference_dict() for a in rb]
    joined=trajectory_records(changed,tb,rb)
    assert [r['phase'] for r in joined]!=[r['phase'] for r in original]
    assert risk_metrics(joined,6)['eligible_benign_count']==0
    assert risk_metrics(original,6)['eligible_benign_count']>0
    # Manifest sequence controls canonical pre/post metrics, not phase text.
    assert risk_metrics(joined,6)['pre_mean_risk']==risk_metrics(original,6)['pre_mean_risk']
    assert risk_metrics(original,4)['pre_mean_risk']!=risk_metrics(original,6)['pre_mean_risk']
    with pytest.raises(ValueError): RiskAgent().assess(joined[0],tb[0])


def test_inference_never_reads_metadata():
    event=EventGenerator(42,observable_state=True).generate('S2',1)[0]
    class Guard:
        def __getattr__(self,name):
            if name in {'ground_truth','expected_safe_action','scenario_id','provenance','experiment_id','sequence_number'}:
                raise AssertionError('Inference accessed evaluation metadata')
            return getattr(event,name)
    trusts,risks=assess_observations([Guard()],TrustAgent(),RiskAgent())
    assert len(trusts)==len(risks)==1


def test_full_suite_reproducibility_and_properties():
    a=evaluate_suite(); b=evaluate_suite()
    assert len(a['runs'])==20 and a['seeds']==[42,123,456,789,2026]
    assert stable_json(a)==stable_json(b)
    assert a['aggregates']['S2']['positive_escalation_runs']==5
    assert a['aggregates']['S5']['runs_with_false_escalation']==0
    for run in a['runs']:
        m=run['metrics']
        assert m['min_coverage']==m['max_coverage']==.45
        if run['experiment']['scenario_id']=='S2':
            assert m['contributions']['TRUST']['transition_change']==pytest.approx(m['signed_risk_escalation'])
            assert m['contributions']['CRITICALITY']['transition_change']==0
        if run['experiment']['scenario_id']=='S3':
            assert m['positive_risk_response_rate']==0
            assert any('BEHAVIORAL SEMANTICS INSUFFICIENT' in x for x in run['limitations'])


def test_empty_run_and_invalid_metric_arguments():
    assert evaluate_run('S2',total_events=0)['metrics']['mean_risk'] is None
    for tolerance in (-1,True,float('nan')):
        with pytest.raises(ValueError): risk_metrics(rows(),tolerance=tolerance)
    with pytest.raises(ValueError): risk_metrics(rows(),0)
    with pytest.raises(ValueError): risk_metrics(list(reversed(rows())))
