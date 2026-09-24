from dataclasses import replace
import pytest
from agents.planning_agent import PlanningAgent
from agents.trust_agent import TrustAgent
from agents.risk_agent import RiskAgent
from core.authorization import PermissionPolicy
from core.runtime_inputs import runtime_observation
from core.trust_assessment import AuditCorrelation
from evaluation.evaluate_risk import assess_observations
from evaluation.replay_authorization_planning import replay
from intelligence.authorization_engine import AuthorizationEngine
from intelligence.decision_context_builder import build_decision_context
from tests.test_decision_context import build_run


def setup(scenario='S2', index=4):
    e, t, r, _ = build_run(scenario)
    o = runtime_observation(e[index])
    engine = AuthorizationEngine()
    return o, t[index], r[index], engine.assess(o), engine.policy


def test_structured_integration_and_legacy_fallback():
    o,t,r,a,p = setup()
    c = build_decision_context(o,t,r,a,permission_policy=p)
    assert c.authorization_assessment == a
    assert c.authorization_status == 'AUTHORIZED'
    assert c.authorization_policy_version == p.policy_version
    assert c.to_dict()['authorization_assessment']['matched_rule_ids'] == list(a.matched_rule_ids)
    assert c.reference == build_decision_context(o,t,r,a,permission_policy=p).reference
    old = build_decision_context(o,t,r)
    assert old.authorization_status == 'UNKNOWN'
    assert old.to_dict()['authorization_basis'] == 'LEGACY_UNKNOWN'
    assert old.reference != c.reference
    assert old.trust_assessment == c.trust_assessment and old.risk_assessment == c.risk_assessment


@pytest.mark.parametrize('field,value', [('source_id','PLC-01'),('target_id','PUMP-01'),
    ('identity_id','operator-01'),('operation','write_register'),('request_reference','wrong'),
    ('permission_policy_reference','wrong'),('matched_rule_ids',('MISSING',))])
def test_mismatched_assessment_rejected(field,value):
    o,t,r,a,p=setup()
    with pytest.raises(ValueError,match='Authorization'):
        build_decision_context(o,t,r,replace(a,**{field:value}),permission_policy=p)


def test_authentication_binding_and_failure_semantics():
    o,t,r,a,p=setup()
    o['authentication_status']=False
    with pytest.raises(ValueError,match='request reference'):
        build_decision_context(o,t,r,a,permission_policy=p)
    failed=AuthorizationEngine().assess(o)
    assert build_decision_context(o,t,r,failed).authorization_status == 'UNAUTHORIZED'
    o,t,r,a,p=setup('S3',5)
    assert o['authentication_status'] is True
    assert build_decision_context(o,t,r,a).authorization_status == 'UNKNOWN'


def test_policy_and_status_affect_identity_without_engine_in_builder(monkeypatch):
    o,t,r,a,p=setup()
    changed=PermissionPolicy(rules=())
    other=AuthorizationEngine(changed).assess(o)
    # Explicit upstream computation has finished; neither assembly nor planning
    # may run inference again.
    def forbidden(*args,**kwargs): raise AssertionError('Hidden authorization inference')
    monkeypatch.setattr(AuthorizationEngine,'assess',forbidden)
    first=build_decision_context(o,t,r,a,permission_policy=p)
    second=build_decision_context(o,t,r,other,permission_policy=changed)
    assert first.reference != second.reference
    assert second.authorization_status == 'UNKNOWN'
    assert PlanningAgent().plan(first) == PlanningAgent().plan(first)
    with pytest.raises(ValueError,match='policy reference'):
        build_decision_context(o,t,r,other,permission_policy=p)
    with pytest.raises(ValueError): replace(a,authorization_policy_version='unsupported')


def test_registry_binding_detects_stale_reference(monkeypatch):
    from environment.assets import ASSET_REGISTRY
    o,t,r,a,p=setup()
    asset=ASSET_REGISTRY[o['source_id']]
    monkeypatch.setitem(ASSET_REGISTRY,asset.asset_id,replace(asset,criticality=.1))
    with pytest.raises(ValueError,match='request reference'):
        build_decision_context(o,t,r,a,permission_policy=p)


@pytest.mark.parametrize('scenario',['S1','S2','S3','S4','S5','S6'])
def test_full_pipeline_leakage_and_audit_isolation(scenario):
    events,trusts,risks,_=build_run(scenario)
    engine=AuthorizationEngine()
    def results(es,ts,rs,audit=None):
        output=[]
        for e,t,r in zip(es,ts,rs):
            o=runtime_observation(e); a=engine.assess(o)
            if audit is not None: t,r=replace(t,audit=audit),replace(r,audit=audit)
            c=build_decision_context(o,t,r,a)
            output.append((a.to_dict(),c.to_dict(),PlanningAgent().plan(c).to_dict()))
        return output
    before=results(events,trusts,risks)
    for e in events:
        e.ground_truth='SUSPICIOUS';e.expected_safe_action='ISOLATE';e.scenario_id='OTHER'
        e.provenance=replace(e.provenance,phase='OTHER',transition_type='OTHER',causal_tags=('OTHER',))
        e.contextual_features.update(anomaly_score=999,simulated_attack_probability=-999,
                                    transition=999,compromise_phase=True,causal_tags=['OTHER'])
    t,r=assess_observations(events,TrustAgent(),RiskAgent())
    assert before==results(events,t,r,AuditCorrelation('different-audit',999))


def test_replay_scientific_invariants():
    report=replay()
    assert report==replay()
    rows=report['rows']
    for row in rows:
        assert row['old_authorization']=='UNKNOWN'
        assert row['old_candidates']==row['new_candidates']
        assert row['added_candidates']==row['removed_candidates']==[]
        assert row['risk_coverage']==.45
        assert 'ALLOW' not in row['new_candidates'] and 'ISOLATE' not in row['new_candidates']
        if row['new_authorization']=='AUTHORIZED':
            assert not any('operation permission is not established' in s for s in row['new_planning']['unresolved_constraints'])
    s2=[r for r in rows if r['scenario']=='S2']
    assert all(r['new_authorization']=='AUTHORIZED' for r in s2)
    assert s2[0]['operational_validity']['status']=='WITHIN_LIMIT'
    assert all(r['operational_validity']['status']=='OUTSIDE_LIMIT' for r in s2[1:])
    assert len({r['trust'] for r in s2})==len({r['risk'] for r in s2})==4
    for row in s2[1:]:
        payload=row['new_planning']['candidates'][0]['payload']
        assert (payload['allowed_min'],payload['allowed_max'])==(20,80)
        assert payload['replacement_value'] is None
    s5=[r for r in rows if r['scenario']=='S5']
    assert all(r['new_authorization']=='AUTHORIZED' and r['new_candidates']==['REQUEST_APPROVAL'] for r in s5)
    assert [r['operational_validity']['operating_mode'] for r in s5]==['NORMAL','HIGH_OUTPUT','HIGH_OUTPUT']
    assert [r['operational_validity']['check']['maximum'] for r in s5]==[80,95,95]
