from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json
import pytest
import yaml

from core.actions import Action
from core.decision_contracts import CandidateAction, ProposedDecision, GovernanceDecision, ExecutionResult
from core.decision_context import (AuthorizationStatus, PolicyContext, PolicyDefinition,
                                   OperationalValidity, load_policy_definitions)
from core.runtime_inputs import runtime_observation
from core.trust_assessment import AuditCorrelation
from environment.industrial_environment import IndustrialState, OperatingMode
from environment.event import VALID_ACTIONS
from environment.event_generator import EventGenerator
from agents.trust_agent import TrustAgent
from agents.risk_agent import RiskAgent
from evaluation.evaluate_risk import assess_observations
from intelligence.decision_context_builder import build_decision_context


def build_run(scenario='S2'):
    events=EventGenerator(42,observable_state=True).generate(scenario,10)
    trusts,risks=assess_observations(events,TrustAgent(),RiskAgent())
    contexts=[build_decision_context(runtime_observation(e),t,r) for e,t,r in zip(events,trusts,risks)]
    return events,trusts,risks,contexts


def candidate(**changes):
    values=dict(action=Action.BLOCK,payload={'target':'fixture'},rationale='Fixture',safety_effect='Unknown',
        operational_impact='Denial impact requires review',reversibility='Unknown',requires_approval=True,
        policy_constraints=('fixture',),evidence_basis=('observable',),unresolved_prerequisites=('review',),
        capability_reference='cap-ref',planning_policy_version='fixture-v1')
    values.update(changes)
    return CandidateAction(**values)


def test_canonical_actions_match_frozen_representations():
    from core.decision_record import VALID_ACTIONS as recorded
    from pathlib import Path
    system=yaml.safe_load((Path(__file__).resolve().parents[1]/'config/system.yaml').read_text())
    assert {a.value for a in Action}==VALID_ACTIONS==recorded==set(system['system']['decision_actions'])
    assert len(Action)==6


@pytest.mark.parametrize('scenario',['S1','S2','S3','S5'])
def test_context_determinism_immutability_and_coverage(scenario):
    events,trusts,risks,contexts=build_run(scenario)
    repeated=build_run(scenario)[3]
    assert [c.to_dict() for c in contexts]==[c.to_dict() for c in repeated]
    for event,t,r,c in zip(events,trusts,risks,contexts):
        assert c.trust_assessment==t and c.risk_assessment==r
        assert c.risk_assessment.coverage==.45
        assert c.authorization_status==AuthorizationStatus.UNKNOWN
        assert c.trust_assessment.evidence_coverage==t.evidence_coverage
        assert c.risk_assessment.trust_state_version==t.trust_state_version
        assert json.dumps(c.to_dict(),sort_keys=True,allow_nan=False)
        assert c.reference==build_decision_context(runtime_observation(event),t,r).reference
        with pytest.raises(FrozenInstanceError): c.state_version=9
        with pytest.raises(TypeError): c.observation['requested_value']=9
        with pytest.raises(TypeError): c.observation['contextual_features']['operating_mode']='x'
        exported=c.to_dict();exported['observation']['source_id']='x'
        assert c.source_id==event.source_id


def test_capabilities_and_current_mode():
    s2=build_run()[3]
    for c in s2:
        cap=c.capabilities
        assert Action.LIMIT in cap.supported_actions
        assert cap.operational_validity.check.minimum==20 and cap.operational_validity.check.maximum==80
        assert cap.to_dict()['isolation_capability']=='UNKNOWN'
        assert Action.ISOLATE not in cap.supported_actions
        assert not cap.to_dict()['execution_implemented']
        assert not cap.to_dict()['external_approval_integration']
    assert s2[4].capabilities.operational_validity.status=='WITHIN_LIMIT'
    assert all(c.capabilities.operational_validity.status=='OUTSIDE_LIMIT' for c in s2[5:8])
    assert s2[5].observation['requested_value']==97  # No clamping.
    s5=build_run('S5')[3]
    assert s5[4].capabilities.operational_validity.check.maximum==80
    for c in s5[5:7]:
        assert c.capabilities.operational_validity.check.minimum==60
        assert c.capabilities.operational_validity.check.maximum==95
        assert c.capabilities.operational_validity.status=='WITHIN_LIMIT'
    for scenario in ('S1','S3'):
        c=build_run(scenario)[3][5]
        assert Action.LIMIT not in c.capabilities.supported_actions
        assert c.capabilities.operational_validity.status=='UNKNOWN'
        assert set(c.capabilities.supported_actions)=={Action.ALLOW,Action.MONITOR,Action.REQUEST_APPROVAL,Action.BLOCK}
        assert c.observation['authentication_status'] is True
        assert c.authorization_status==AuthorizationStatus.UNKNOWN


def test_state_consistency_and_preservation():
    events,t,r,_=build_run('S5');o=runtime_observation(events[5])
    state=IndustrialState();state.set_operating_mode(OperatingMode.HIGH_OUTPUT)
    c=build_decision_context(o,t[5],r[5],industrial_state=state)
    assert c.state_version==state.state_version==1
    before=state.to_dict()
    assert build_decision_context(o,t[5],r[5],industrial_state=state.snapshot()).to_dict()==c.to_dict()
    assert state.to_dict()==before
    with pytest.raises(ValueError,match='state'): build_decision_context(o,t[5],r[5],industrial_state=IndustrialState())
    state.set_operating_mode(OperatingMode.NORMAL)
    assert c.observation['contextual_features']['operating_mode']=='HIGH_OUTPUT'


def test_assessment_pairing_and_capability_binding():
    events,t,r,c=build_run();o=runtime_observation(events[5])
    for trust,risk in [(t[4],r[5]),(t[5],r[4]),(build_run('S5')[1][5],r[5]),(t[5],build_run('S3')[2][5])]:
        with pytest.raises(ValueError): build_decision_context(o,trust,risk)
    with pytest.raises(ValueError): build_decision_context(o,t[5],replace(r[5],operation='different'))
    with pytest.raises(ValueError): build_decision_context(o,t[5],r[5],capability_context=c[4].capabilities)
    with pytest.raises(ValueError): build_decision_context(o,t[5],r[5],policy_context=c[4].policy_context)
    with pytest.raises(ValueError): build_decision_context(dict(o,asset_criticality=.92),t[5],r[5])
    # Assessments do not contain requested_value; content freshness cannot be proved.
    other=dict(o,requested_value=98)
    changed=build_decision_context(other,t[5],r[5])
    assert changed.reference!=c[5].reference


def test_audit_separation_and_mismatch():
    events,t,r,c=build_run();o=runtime_observation(events[0]);audit=AuditCorrelation('opaque',1)
    after=build_decision_context(o,replace(t[0],audit=audit),replace(r[0],audit=audit))
    assert after.to_dict()==c[0].to_dict()
    assert 'audit' not in after.to_dict()['trust_assessment']
    assert 'audit' not in after.to_dict()['risk_assessment']
    with pytest.raises(ValueError,match='correlation'):
        build_decision_context(o,replace(t[0],audit=audit),replace(r[0],audit=AuditCorrelation('other',1)))


@pytest.mark.parametrize('scenario',['S1','S2','S3','S5'])
def test_hidden_label_mutation(scenario):
    events,_,_,original=build_run(scenario)
    for e in events:
        e.ground_truth='MALICIOUS';e.expected_safe_action='ISOLATE';e.scenario_id='OTHER'
        e.provenance=replace(e.provenance,phase='OTHER',transition_type='OTHER',causal_tags=('OTHER',))
        e.contextual_features.update(anomaly_score=1,simulated_attack_probability=1,compromise_phase=True)
    t,r=assess_observations(events,TrustAgent(),RiskAgent())
    changed=[build_decision_context(runtime_observation(e),a,b) for e,a,b in zip(events,t,r)]
    assert [c.to_dict() for c in changed]==[c.to_dict() for c in original]
    assert [c.capabilities.to_dict() for c in changed]==[c.capabilities.to_dict() for c in original]
    assert [c.policy_context.to_dict() for c in changed]==[c.policy_context.to_dict() for c in original]


def test_reject_raw_and_invalid_inputs():
    e,t,r,_=build_run()
    for raw in (e[0],e[0].to_dict(),dict(runtime_observation(e[0]),ground_truth='BENIGN')):
        with pytest.raises(ValueError): build_decision_context(raw,t[0],r[0])
    with pytest.raises(ValueError): build_decision_context(runtime_observation(e[0]),t[0].to_dict(),r[0])
    with pytest.raises(ValueError): build_decision_context(runtime_observation(e[0]),t[0],r[0].to_dict())


def test_prose_policies_are_not_permissions(tmp_path):
    c=build_run('S3')[3][5]
    assert [p.policy_id for p in c.policy_context.policies]==['P01','P02','P03']
    assert all(p['applicability']=='UNKNOWN' and not p['executable'] for p in c.policy_context.to_dict()['policy_facts'].values())
    assert c.policy_context.to_dict()['approval_requirement']=='UNKNOWN'
    with pytest.raises(ValueError): PolicyDefinition(policy_id='x',name='x',description='x',enabled='yes')
    path=tmp_path/'policies.yaml';path.write_text('policies:\n  - id: x\n    grants: all\n')
    with pytest.raises(ValueError): load_policy_definitions(path)
    with pytest.raises(ValueError): replace(c.policy_context,policies=c.policy_context.policies*2)


@pytest.mark.parametrize('change',[{'action':'OTHER'},{'requires_approval':1},{'reversibility':''},{'payload':{'x':float('nan')}},{'policy_constraints':'x'}])
def test_candidate_validation(change):
    with pytest.raises(ValueError): candidate(**change)


def test_candidate_and_proposal_contracts():
    payload={'value':[1,2]};c=candidate(payload=payload);payload['value'].append(3)
    assert c.to_dict()['payload']=={'value':[1,2]}
    with pytest.raises(TypeError): c.payload['x']=2
    with pytest.raises(FrozenInstanceError): c.action=Action.ALLOW
    p=ProposedDecision(selected_action=c.action,selected_candidate_reference=c.reference,candidate_actions=[c],
        primary_reason='fixture',evidence_summary=['observed'],trust_basis='supplied',risk_basis='supplied',
        uncertainty=['unknown'],policy_basis=['review'],alternatives_considered=[],context_reference='ctx',decision_policy_version='fixture')
    assert p.status=='PROPOSED' and p.to_dict()['candidate_actions'][0]==c.to_dict()
    with pytest.raises(ValueError): replace(p,selected_action=Action.ALLOW)
    with pytest.raises(ValueError): replace(p,selected_action=None)
    assert replace(p,selected_action=None,selected_candidate_reference=None,candidate_actions=()).status=='NO_ADMISSIBLE_ACTION'


def governance(**changes):
    values=dict(status='APPROVED',proposed_action=Action.BLOCK,authorized_action=Action.BLOCK,authorized_payload={},
        policy_checks={'fixture':'PASS'},violations=(),reason='fixture',context_reference='ctx',proposal_reference='p',
        authorization_reference='grant',governance_policy_version='fixture')
    values.update(changes)
    return GovernanceDecision(**values)


@pytest.mark.parametrize('change',[{'status':'OTHER'},{'status':'VETOED'},{'status':'APPROVAL_REQUIRED'},
    {'authorized_action':None},{'policy_checks':{'fixture':'UNKNOWN'}},{'violations':['failed']},{'status':'OVERRIDDEN'}])
def test_governance_contradictions(change):
    with pytest.raises(ValueError): governance(**change)


def test_governance_and_execution_records_only():
    g=governance();assert g.to_dict()['status']=='APPROVED'
    with pytest.raises(TypeError): g.policy_checks['fixture']='FAIL'
    v=governance(status='VETOED',authorized_action=None,authorized_payload=None,authorization_reference=None)
    assert v.authorized_action is None
    result=ExecutionResult(requested_action=Action.BLOCK,authorized_action=Action.BLOCK,execution_status='DENIED',
        state_before_reference='same',state_after_reference='same',reason='fixture',governance_reference=g.reference,execution_policy_version='fixture')
    assert result.to_dict()['execution_status']=='DENIED'
    with pytest.raises(ValueError): replace(result,execution_status='SUCCEEDED',governance_reference=None)
    with pytest.raises(ValueError): replace(result,authorized_action=Action.ALLOW)
    with pytest.raises(FrozenInstanceError): result.reason='other'
