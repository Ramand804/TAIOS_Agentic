from dataclasses import FrozenInstanceError, replace
import json
import pytest

from agents.base_agent import BaseAgent
from agents.planning_agent import PlanningAgent
from core.actions import Action
from core.decision_context import CapabilityEnvelope
from core.planning_result import PlanningResult, PLANNING_VERSION
from core.runtime_inputs import runtime_observation
from core.trust_assessment import AuditCorrelation
from agents.trust_agent import TrustAgent
from agents.risk_agent import RiskAgent
from evaluation.evaluate_risk import assess_observations
from intelligence.decision_context_builder import build_decision_context
from tests.test_decision_context import build_run


def actions(result): return tuple(c.action for c in result.candidates)


@pytest.mark.parametrize('scenario',['S1','S2','S3','S5'])
def test_stateless_determinism_binding_and_immutability(scenario):
    planner=PlanningAgent(); assert isinstance(planner,BaseAgent)
    for c in build_run(scenario)[3]:
        before=c.to_dict(); result=planner.plan(c)
        assert type(result) is PlanningResult
        assert result.context_fingerprint==c.reference
        assert result.planning_policy_version==PLANNING_VERSION
        assert actions(result)==tuple(a for a in Action if a in actions(result))
        assert len(actions(result))==len(set(actions(result)))
        assert json.dumps(result.to_dict(),sort_keys=True)==json.dumps(PlanningAgent().plan(c).to_dict(),sort_keys=True)
        assert planner.plan(c)==result and c.to_dict()==before
        for name in ('selected_action','recommended_action','best_action','preferred_action'):
            assert not hasattr(result,name) and not hasattr(planner,name) and name not in result.to_dict()
        with pytest.raises(FrozenInstanceError): result.context_version='other'
        with pytest.raises(TypeError): result.exclusions['ISOLATE']='allowed'
        for item in result.candidates:
            assert item.requires_approval and item.payload['execution_ready'] is False
            assert item.unresolved_prerequisites
            with pytest.raises(TypeError): item.payload['execution_ready']=True


def test_semantic_candidates_and_current_mode():
    planner=PlanningAgent()
    for scenario in ('S1','S3'):
        result=planner.plan(build_run(scenario)[3][5])
        assert actions(result)==(Action.REQUEST_APPROVAL,)
        assert 'ISOLATE' in result.exclusions and 'LIMIT' in result.exclusions
    s2=build_run('S2')[3]
    assert actions(planner.plan(s2[4]))==(Action.REQUEST_APPROVAL,)
    for c in s2[5:8]:
        result=planner.plan(c)
        assert actions(result)==(Action.LIMIT,Action.REQUEST_APPROVAL)
        limit=result.candidates[0]
        assert limit.payload['allowed_min']==20 and limit.payload['allowed_max']==80
        assert limit.payload['requested_value']==c.observation['requested_value']
        assert limit.payload['replacement_value'] is None
        assert 'outside current NORMAL' in limit.rationale
        assert 'BLOCK' in result.exclusions and 'denial-impact' in result.exclusions['BLOCK']
    for c in build_run('S5')[3][4:7]:
        assert actions(planner.plan(c))==(Action.REQUEST_APPROVAL,)
    c=build_run('S5')[3][5]
    evidence=' '.join(planner.plan(c).candidates[0].evidence_basis)
    assert 'HIGH_OUTPUT' in evidence and '[60,95]' in evidence and '[20,80]' not in evidence


def test_empty_and_unsupported_capability(monkeypatch):
    c=build_run()[3][5]
    # Isolated capability seam: frozen real contexts always have logical approval.
    monkeypatch.setattr(CapabilityEnvelope,'supported_actions',property(lambda self: ()))
    result=PlanningAgent().plan(c)
    assert result.candidates==() and result.status=='NO_ADMISSIBLE_CANDIDATES'
    assert len(result.exclusions)==6 and result.unresolved_constraints


def test_removed_limit_capability(monkeypatch):
    c=build_run()[3][5]
    monkeypatch.setattr(CapabilityEnvelope,'supported_actions',property(lambda self:(Action.REQUEST_APPROVAL,)))
    assert actions(PlanningAgent().plan(c))==(Action.REQUEST_APPROVAL,)


@pytest.mark.parametrize('scenario',['S1','S2','S3','S5'])
def test_label_and_audit_invariance(scenario):
    events,_,_,contexts=build_run(scenario)
    before=[PlanningAgent().plan(c).to_dict() for c in contexts]
    for e in events:
        e.ground_truth='MALICIOUS';e.expected_safe_action='ISOLATE';e.scenario_id='OTHER'
        e.provenance=replace(e.provenance,phase='OTHER',transition_type='OTHER',causal_tags=('OTHER',))
        e.contextual_features.update(anomaly_score=1,simulated_attack_probability=1,compromise_phase=True)
    trusts,risks=assess_observations(events,TrustAgent(),RiskAgent())
    after=[]
    for e,t,r in zip(events,trusts,risks):
        audit=AuditCorrelation('different',999)
        c=build_decision_context(runtime_observation(e),replace(t,audit=audit),replace(r,audit=audit))
        after.append(PlanningAgent().plan(c).to_dict())
    assert after==before


def test_scores_alone_do_not_change_membership():
    from core.risk_input import RiskConfig, COMPONENTS
    from intelligence.risk_input_builder import build_risk_input
    from intelligence.risk_model import RiskModel
    events,trusts,_,contexts=build_run('S3')
    observation=runtime_observation(events[5]); t=trusts[5]
    original=actions(PlanningAgent().plan(contexts[5]))
    for score in (0.,1.):
        changed=replace(t,composite_trust=score,trust_delta=score-t.previous_composite_trust)
        risk=RiskModel().evaluate(build_risk_input(observation,changed))
        c=build_decision_context(observation,changed,risk)
        assert actions(PlanningAgent().plan(c))==original
    # Different valid risk weighting, not canonical configuration tuning.
    for weights in ((0,1,0,0),(0,0,1,0),(1,0,0,0)):
        config=RiskConfig(dict(zip(COMPONENTS,weights)))
        risk=RiskModel().evaluate(build_risk_input(observation,t,config=config))
        c=build_decision_context(observation,t,risk)
        assert actions(PlanningAgent().plan(c))==original
    evidence=' '.join(PlanningAgent().plan(contexts[5]).candidates[0].evidence_basis)
    assert 'BEHAVIOR=INSUFFICIENT' in evidence and 'coverage: 0.45' in evidence


def test_raw_input_rejection_and_result_validation():
    e,t,r,contexts=build_run(); planner=PlanningAgent()
    for bad in (e[0],runtime_observation(e[0]),contexts[0].to_dict(),t[0],None):
        with pytest.raises(ValueError): planner.plan(bad)
    result=planner.plan(contexts[5])
    for change in ({'candidates':result.candidates*2}, {'candidates':tuple(reversed(result.candidates))},
                   {'context_fingerprint':''},{'planning_policy_version':'other'},{'exclusions':{}}):
        with pytest.raises(ValueError): replace(result,**change)
