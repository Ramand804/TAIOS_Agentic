from dataclasses import FrozenInstanceError, replace
from itertools import permutations
import json

import pytest

from core.runtime_inputs import runtime_observation
from core.trust_evidence import TrustEvidence, attach_audit_correlation
from core.trust_state import TRUST_FIELDS
from environment.event_generator import EventGenerator
from intelligence.trust_evidence_extractor import TrustEvidenceExtractor
from intelligence.trust_model import TrustModel, TrustModelConfig

ENTITY = 'asset:PLC-07'


def evidence(direction='POSITIVE', strength=1, confidence=1, dimension='BEHAVIOR', reason='Observed fixture.', entity=ENTITY):
    return TrustEvidence(entity, dimension, direction, strength, confidence, 'unit-test', reason)


def initialized(config=None, entity=ENTITY):
    model = TrustModel(config)
    model.initialize_entity(entity)
    return model


def apply(model, batch, entity=ENTITY):
    number = model.get_state(entity).observation_count + 1
    return model.update(entity, batch, delivery_token=f'delivery-{number}', observation_number=number)


@pytest.mark.parametrize('entity,prior', [(ENTITY,.8),('identity:operator-01',.8),('asset:UNSEEN',.5),('identity:UNSEEN',.5)])
def test_priors(entity,prior):
    state = initialized(entity=entity).get_state(entity)
    assert all(getattr(state,name) == prior for name in TRUST_FIELDS)
    assert state.composite_trust == pytest.approx(prior)
    assert (state.version,state.observation_count,state.last_sequence_number) == (0,0,0)


@pytest.mark.parametrize('field,value', [
    ('weights',(.2,.2,.2,.2,.3)),('weights',(-.1,.3,.3,.3,.2)),('weights',(1,)),
    ('known_prior',float('nan')),('unknown_prior',0),('unknown_prior',1),
    ('negative_rate',.001),('positive_rate',0),('recovery_rate',.1),
    ('recency',0),('history_confidence',True),('weight_tolerance',.1),
])
def test_invalid_configuration(field,value):
    with pytest.raises(ValueError): replace(TrustModelConfig.load(),**{field:value})


def test_configured_priors_and_weights():
    config = replace(TrustModelConfig.load(),known_prior=.7,unknown_prior=.4,weights=(0,0,1,0,0))
    model = initialized(config)
    state = apply(model,[evidence()])
    assert state.behavioral_trust == pytest.approx(.71)
    assert state.composite_trust == pytest.approx(.71)
    assert model.initialize_entity('asset:NEW').identity_trust == .4


@pytest.mark.parametrize('strength,confidence,delta', [(1,1,.01),(.5,1,.005),(1,.5,.005),(.4,.5,.002),(1,0,0)])
def test_effective_positive_and_only_target_dimension(strength,confidence,delta):
    state = apply(initialized(),[evidence(strength=strength,confidence=confidence)])
    assert state.behavioral_trust == pytest.approx(.8+delta)
    assert state.identity_trust == state.device_trust == state.contextual_trust == state.historical_trust == .8
    assert state.composite_trust == pytest.approx(.8+.25*delta)


def test_asymmetry_and_negative_magnitude():
    positive=apply(initialized(),[evidence(strength=.4,confidence=.5)])
    negative=apply(initialized(),[evidence('NEGATIVE',.4,.5)])
    assert negative.behavioral_trust == pytest.approx(.78)
    assert .8-negative.behavioral_trust > positive.behavioral_trust-.8


def test_permutation_invariance_and_maximum_aggregation():
    batch=[evidence(strength=.2,reason='A'),evidence(strength=.8,reason='B'),evidence('NEUTRAL',reason='C')]
    states=[apply(initialized(),list(order)) for order in permutations(batch)]
    assert all(state==states[0] for state in states)
    assert states[0].behavioral_trust == pytest.approx(.808)


def test_negative_suppresses_all_positive_dimensions():
    batch=[evidence('NEGATIVE',.5,.8), evidence(dimension='IDENTITY'), evidence(reason='another')]
    states=[apply(initialized(),list(order)) for order in permutations(batch)]
    assert all(state==states[0] for state in states)
    assert states[0].behavioral_trust == pytest.approx(.76)
    assert states[0].identity_trust == .8


def test_duplicate_evidence_and_conflict_atomicity():
    assert apply(initialized(),[evidence(),evidence()]) == apply(initialized(),[evidence()])
    model=initialized(); before=model.get_state(ENTITY)
    with pytest.raises(ValueError,match='Conflicting'):
        apply(model,[evidence(),evidence('NEGATIVE')])
    assert model.get_state(ENTITY)==before
    assert apply(model,[evidence()]).version == 1


def test_history_exact_lag_recurrence_and_no_feedback():
    model=initialized()
    first=apply(model,[evidence()])
    assert first.history_statistic == .25 and first.historical_trust == .8
    second=apply(model,[evidence()])
    assert second.history_statistic == .4375
    assert second.historical_trust == pytest.approx(.80125)
    third=apply(model,[evidence('NEGATIVE')])
    assert third.history_statistic == pytest.approx(.75*.4375-.25)
    assert third.historical_trust == second.historical_trust
    assert third.behavioral_trust == pytest.approx(second.behavioral_trust-.1)


@pytest.mark.parametrize('batch',[[],[evidence('NEUTRAL')],[evidence(confidence=0)]])
def test_empty_neutral_zero_confidence_hold_trust_and_history(batch):
    model=initialized(); before=apply(model,[evidence('NEGATIVE')])
    after=apply(model,batch)
    assert [getattr(before,k) for k in TRUST_FIELDS] == [getattr(after,k) for k in TRUST_FIELDS]
    assert before.history_statistic == after.history_statistic
    assert before.negative_history == after.negative_history
    assert after.observation_count == after.version == 2
    assert after.evidence_counts == before.evidence_counts


def test_history_negative_delays_but_does_not_prevent_recovery():
    model=initialized()
    damaged=apply(model,[evidence('NEGATIVE')])
    first_good=apply(model,[evidence()])
    assert first_good.behavioral_trust == damaged.behavioral_trust
    assert first_good.historical_trust < damaged.historical_trust
    second_good=apply(model,[evidence()])
    assert second_good.behavioral_trust == pytest.approx(damaged.behavioral_trust+.005)
    for _ in range(100): recovered=apply(model,[evidence()])
    assert recovered.behavioral_trust > damaged.behavioral_trust
    assert recovered.negative_history[2]


def test_old_positive_history_cannot_mask_direct_negative():
    model=initialized()
    for _ in range(100): before=apply(model,[evidence()])
    after=apply(model,[evidence('NEGATIVE')])
    assert after.behavioral_trust == pytest.approx(before.behavioral_trust-.1)
    assert after.composite_trust < before.composite_trust


def test_repeated_evidence_bounds():
    model=initialized()
    for _ in range(300): high=apply(model,[evidence()])
    assert high.behavioral_trust == 1
    previous=high.behavioral_trust
    for _ in range(300):
        low=apply(model,[evidence('NEGATIVE')])
        assert 0 <= low.behavioral_trust <= previous
        previous=low.behavioral_trust
    assert low.behavioral_trust == 0
    assert all(0 <= getattr(low,name) <= 1 for name in TRUST_FIELDS+('composite_trust',))


def test_order_replay_and_no_partial_mutation():
    model=initialized(); before=apply(model,[evidence()])
    for token,ordinal in [('delivery-1',2),('new',1),('new',3),('new',True)]:
        with pytest.raises(ValueError): model.update(ENTITY,[evidence()],delivery_token=token,observation_number=ordinal)
        assert model.get_state(ENTITY)==before
    assert apply(model,[evidence()]).version == 2


def test_entities_are_isolated_and_state_is_immutable():
    model=initialized()
    asset=model.initialize_entity('asset:PLC-01')
    identity=model.initialize_entity('identity:operator-01')
    state=apply(model,[evidence()])
    assert model.get_state('asset:PLC-01')==asset
    assert model.get_state('identity:operator-01')==identity
    with pytest.raises(FrozenInstanceError): state.identity_trust=0
    export=state.to_dict(); export['negative_history'][0]=True
    assert not state.negative_history[0]
    assert model.initialize_entity(ENTITY)==state
    with pytest.raises(ValueError,match='Mixed entity'):
        apply(model,[evidence(entity='asset:PLC-01')])


def test_model_rejects_raw_records_and_correlated_evidence():
    model=initialized(); event=EventGenerator().generate('S2',1)[0]
    for batch in (event,event.to_dict(),[event],[event.to_dict()]):
        with pytest.raises(TypeError): apply(model,batch)
    with pytest.raises(ValueError,match='correlation'):
        apply(model,attach_audit_correlation([evidence()],event_id=event.event_id,sequence_number=1))
    with pytest.raises(ValueError,match='HISTORY'):
        apply(model,[evidence(dimension='HISTORY')])
    with pytest.raises(TypeError):
        model.update(ENTITY,[evidence()],delivery_token='new',observation_number=1,ground_truth='BENIGN')


@pytest.mark.parametrize('scenario',['S2','S3','S5'])
def test_deterministic_scenario_trajectories_and_hidden_label_mutation(scenario):
    def trajectory(change):
        model=TrustModel(); extractor=TrustEvidenceExtractor(); result=[]
        for ordinal,event in enumerate(EventGenerator().generate(scenario,10),1):
            if change:
                event.ground_truth='OTHER'; event.expected_safe_action='OTHER'; event.provenance=None
                event.scenario_id='OTHER'; event.event_id='OTHER'
                event.contextual_features['anomaly_score']=999
                event.contextual_features['compromise_phase']=True
            records=extractor.extract(runtime_observation(event)); entity=records[0].entity_id
            model.initialize_entity(entity)
            result.append(model.update(entity,records,delivery_token=str(ordinal),observation_number=ordinal).to_dict())
        return result
    first=trajectory(False)
    assert first==trajectory(False)==trajectory(True)
    assert first[5]['composite_trust'] >= first[4]['composite_trust']
    assert json.loads(json.dumps(first)) == first
