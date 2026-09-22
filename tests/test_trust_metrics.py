from copy import deepcopy
import pytest
from agents.trust_agent import TrustAgent
from environment.event_generator import EventGenerator
from evaluation.evaluate_trust import assess_observations, trajectory_records, evaluate_run, evaluate_suite, stable_json
from evaluation.trust_metrics import trust_metrics, aggregate_runs


def fixture():
    rows=[]
    previous=.8
    for i,(value,label) in enumerate(((.9,'BENIGN'),(.7,'MALICIOUS'),(.6,'BENIGN')),1):
        rows.append({'entity_id':'asset:A','sequence_number':i,'composite_trust':value,
                     'previous_composite_trust':previous,'trust_delta':value-previous,'ground_truth':label,
                     'negative_evidence_count':int(value<previous),
                     'evidence_coverage':{dim:['NEGATIVE'] if dim=='BEHAVIOR' and value<previous else ['INSUFFICIENT'] for dim in ('IDENTITY','DEVICE','BEHAVIOR','HISTORY','CONTEXT')},
                     'evidence':[{'dimension':'CONTEXT','direction':'NEUTRAL'}]})
        previous=value
    return rows


def test_exact_metric_equations():
    m=trust_metrics(fixture(),2)
    assert m['initial_trust']==.8 and m['final_trust']==.6
    assert m['trust_change']==pytest.approx(-.2)
    assert m['mean_trust']==pytest.approx(2.2/3)
    assert m['minimum_trust']==.6 and m['maximum_trust']==.9
    assert m['pre_intervention_mean']==.9 and m['post_intervention_mean']==pytest.approx(.65)
    assert m['degradation_magnitude']==pytest.approx(.3)
    assert m['first_post_intervention_trust']==.7
    assert m['degradation_delay']=={'status':'OBSERVED','sequence_delay':0,'entity_observation_delay':0}
    assert m['false_degradation_count']==1 and m['false_degradation_rate']==.5
    assert m['negative_response_rate']==1
    assert m['volatility_mean_absolute_update']==pytest.approx(.4/3)
    assert m['evidence_coverage']['BEHAVIOR']['NEGATIVE']['rate']==pytest.approx(2/3)
    assert m['evidence_coverage']['CONTEXT']['NEUTRAL']['count']==3
    assert m['evidence_coverage']['CONTEXT']['INSUFFICIENT']['count']==3


def test_empty_denominators_and_missing_intervention():
    m=trust_metrics([])
    assert m['initial_trust'] is m['final_trust'] is m['mean_trust'] is None
    assert m['negative_response_rate'] is m['false_degradation_rate'] is None
    assert m['degradation_delay']['status']=='NOT_APPLICABLE'
    assert m['recovery']=={'status':'NOT_MEASURABLE_WITH_CURRENT_SCENARIOS','delay':None}
    m=trust_metrics(fixture())
    assert m['degradation_magnitude'] is None
    assert m['pre_intervention_mean'] is None
    m=trust_metrics(fixture(),4)
    assert m['degradation_delay']['status']=='NOT_OBSERVED'
    assert m['degradation_delay']['sequence_delay'] is None


def test_multientity_summary_does_not_subtract_unrelated_scores():
    rows=fixture()[:1]
    other=deepcopy(rows[0]);other.update(entity_id='asset:B',sequence_number=2,composite_trust=.5,previous_composite_trust=.5,trust_delta=0)
    m=trust_metrics(rows+[other])
    assert m['initial_trust']==pytest.approx(.65)
    assert m['final_trust']==pytest.approx(.7)
    assert m['volatility_mean_absolute_update']==pytest.approx(.05)


def test_labels_only_affect_evaluation():
    events=EventGenerator(observable_state=True).generate('S2',10)
    changed=deepcopy(events)
    for event in changed:
        event.ground_truth='BENIGN'
        event.expected_safe_action='ALLOW'
        from dataclasses import replace
        event.provenance=replace(event.provenance,phase='OTHER')
    a=assess_observations(events,TrustAgent())
    b=assess_observations(changed,TrustAgent())
    assert [x.to_inference_dict() for x in a]==[x.to_inference_dict() for x in b]
    original=trajectory_records(events,a); alternative=trajectory_records(changed,b)
    assert trust_metrics(original,6)['false_degradation_count']==0
    assert trust_metrics(alternative,6)['false_degradation_count']==5
    assert original[0]['phase']!=alternative[0]['phase']
    assert trust_metrics(original,5)['pre_intervention_mean']!=trust_metrics(original,6)['pre_intervention_mean']
    with pytest.raises(ValueError):
        TrustAgent().assess(original[0],delivery_token='x',observation_number=1)


@pytest.mark.parametrize('scenario',['S1','S2','S3','S5'])
@pytest.mark.parametrize('seed',[42,123])
def test_reproducible_output(scenario,seed):
    first=evaluate_run(scenario,seed)
    assert stable_json(first)==stable_json(evaluate_run(scenario,seed))
    assert len(first['trajectory'])==10
    if scenario=='S3':
        assert any('BEHAVIORAL SEMANTICS INSUFFICIENT' in text for text in first['limitations'])
        assert first['metrics']['negative_response_rate']==0
        assert first['metrics']['degradation_delay']['status']=='NOT_OBSERVED'
    if scenario=='S5':
        assert first['metrics']['false_degradation_count']==0
        assert first['metrics']['evidence_coverage']['BEHAVIOR']['NEGATIVE']['count']==0


def test_five_seed_aggregation_and_missing_values():
    result=evaluate_suite(scenarios=('S2','S3'))
    assert len(result['runs'])==10
    assert result['aggregates']['S2']['negative_response_rate']['mean']==1
    assert result['aggregates']['S3']['degradation_sequence_delay']['defined_runs']==0
    assert result['aggregates']['S3']['degradation_sequence_delay']['missing_runs']==5
    assert result['aggregates']['S2']['final_trust']['minimum']<=result['aggregates']['S2']['final_trust']['mean']<=result['aggregates']['S2']['final_trust']['maximum']


def test_no_evaluation_fields_read_during_inference():
    class Guard:
        def __init__(self,event): self._event=event
        def __getattr__(self,name):
            if name in {'ground_truth','expected_safe_action','provenance','scenario_id','experiment_id','sequence_number','event_id'}:
                raise AssertionError('Evaluation metadata accessed during inference')
            return getattr(self._event,name)
    events=[Guard(event) for event in EventGenerator(observable_state=True).generate('S5',10)]
    assert len(assess_observations(events,TrustAgent()))==10
