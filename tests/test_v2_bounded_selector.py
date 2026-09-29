from dataclasses import replace
from agents.decision_agent import DecisionAgent
from core.actions import Action
from core.assurance_assessment import AssuranceStatus
from evaluation.evaluate_decision_agent import inference_rows
from agentic.bounded_selector import BoundedAgenticSelector
from agentic.contracts import AgenticProposal, ValidationStatus

def fixture():
    context, plan, _ = inference_rows('S2')[4][1:]
    class Assurance: assured_permitted_actions=('ALLOW','MONITOR')
    class Authority: action_authority={'ALLOW':'PERMITTED','MONITOR':'PERMITTED'}
    proposal=AgenticProposal(recommended_action='MONITOR', ranked_candidate_actions=('MONITOR',), reason_codes=('MOCK',), rationale='Mock selects a permitted alternative.', confidence=.5, uncertainty='mock', evidence_references=('x',))
    return context,plan,Assurance(),Authority(),proposal

def test_selector_accepts_valid_agentic_alternative_and_returns_canonical_decision():
    context,plan,assurance,authority,proposal=fixture()
    decision,meta=BoundedAgenticSelector().select(context,plan,proposal,assurance,authority)
    assert decision.selected_action is Action.MONITOR
    assert decision.selected_candidate_reference == next(x.reference for x in plan.candidates if x.action is Action.MONITOR)
    assert meta.deterministic_v1_action == 'ALLOW' and meta.selection_source == 'AGENTIC_VALIDATED'

def test_selector_rejects_outside_assurance_and_uses_v1_decision():
    context,plan,assurance,authority,proposal=fixture(); assurance.assured_permitted_actions=('ALLOW',)
    decision,meta=BoundedAgenticSelector().select(context,plan,proposal,assurance,authority)
    assert decision == DecisionAgent().decide(context,plan)
    assert meta.fallback_used and meta.selected_action == 'ALLOW'

def test_selector_rejects_authority_and_invalid_advice_without_mutating_context():
    context,plan,assurance,authority,proposal=fixture(); authority.action_authority['MONITOR']='NOT_PERMITTED'
    before=context.to_dict(); decision,meta=BoundedAgenticSelector().select(context,plan,proposal,assurance,authority,ValidationStatus.INVALID_ACTION)
    assert decision == DecisionAgent().decide(context,plan) and meta.fallback_used
    assert context.to_dict()==before

def test_selector_cannot_create_governance_or_execution_artifacts():
    context,plan,assurance,authority,proposal=fixture(); decision,meta=BoundedAgenticSelector().select(context,plan,proposal,assurance,authority)
    assert not hasattr(meta,'authorization_reference') and not hasattr(meta,'execution_id')
    assert tuple(x.action.value for x in decision.candidate_actions)==('ALLOW','MONITOR')

def test_langgraph_bounded_selection_records_controlled_divergence():
    __import__('pytest').importorskip('langgraph')
    from agentic.langgraph_workflow import build_bounded_selection_workflow
    from agentic.mock_llm import MockLLM
    from agentic.llm_input import build_agentic_input
    context,plan,assurance,authority,proposal=fixture()
    from agentic.contracts import AgenticInput
    advisory_input=AgenticInput(observation={'source_id':'PLC-07'},semantics={},authorization_status='AUTHORIZED',trust_summary={},threat_summary={},risk_summary={},drift_summary={},adaptation_summary={},assured_actions=('ALLOW','MONITOR'),planner_candidates=('ALLOW','MONITOR'),evidence_references=('x',))
    class PreferMonitor:
        def reason(self, _): return {'recommended_action':'MONITOR','ranked_candidate_actions':['MONITOR'],'reason_codes':['MOCK'],'rationale':'bounded mock','confidence':.5,'uncertainty':'mock','evidence_references':['x']}
    output=build_bounded_selection_workflow(PreferMonitor(),BoundedAgenticSelector()).invoke({'agentic_input':advisory_input,'deterministic_proposal':DecisionAgent().decide(context,plan),'decision_context':context,'planning_result':plan,'assurance_result':assurance,'authority_state':authority})
    assert output['selected_decision'].selected_action is Action.MONITOR
    assert output['selection_provenance'].selection_source=='AGENTIC_VALIDATED'

def test_governed_workflow_keeps_governance_and_execution_independent():
    __import__('pytest').importorskip('langgraph')
    from agentic.langgraph_workflow import build_governed_mock_workflow
    from agents.governance_agent import GovernanceAgent
    from agents.execution_agent import ExecutionAgent
    from environment.industrial_environment import IndustrialState
    context,plan,assurance,authority,_=fixture()
    class PreferMonitor:
        def reason(self,_): return {'recommended_action':'MONITOR','ranked_candidate_actions':['MONITOR'],'reason_codes':['MOCK'],'rationale':'bounded mock','confidence':.5,'uncertainty':'mock','evidence_references':['x']}
    inp=__import__('agentic.contracts',fromlist=['AgenticInput']).AgenticInput(observation={'source_id':'PLC-07'},semantics={},authorization_status='AUTHORIZED',trust_summary={},threat_summary={},risk_summary={},drift_summary={},adaptation_summary={},assured_actions=('ALLOW','MONITOR'),planner_candidates=('ALLOW','MONITOR'),evidence_references=('x',))
    out=build_governed_mock_workflow(PreferMonitor(),BoundedAgenticSelector(),GovernanceAgent(),ExecutionAgent()).invoke({'agentic_input':inp,'deterministic_proposal':DecisionAgent().decide(context,plan),'decision_context':context,'planning_result':plan,'assurance_result':assurance,'authority_state':authority,'industrial_state':IndustrialState()})
    assert out['governance_state'].proposal_reference==out['selected_decision'].reference
    assert out['execution_state'].governance_reference==out['governance_state'].reference
