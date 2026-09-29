import pytest
from core.taios_pipeline import TAIOSPipeline
from environment.event_generator import EventGenerator
from agentic.transaction import TAIOSTransactionContext

def test_transaction_context_restores_v1_checkpointed_state():
    pipeline=TAIOSPipeline(); tx=TAIOSTransactionContext(pipeline).begin()
    pipeline._entity_observations['PLC-01']=99; tx.stage_complete('trust'); tx.rollback('synthetic')
    assert pipeline._entity_observations['PLC-01']==0
    assert tx.failure_stage=='synthetic' and tx.completed_stages==['trust'] and not tx.committed

def test_sequential_runner_matches_v1_for_event_and_sequence():
    from agentic.transactional_runner import V2TransactionalRunner
    from agentic.semantic_fingerprint import fingerprint,pipeline_state_fingerprint
    from environment.industrial_environment import IndustrialState
    from environment.event_generator import EventGenerator
    for scenario in ('S2','S5'):
        g=EventGenerator(42,observable_state=True); run=g.create_run(scenario,10); events=g.generate(scenario,10,run)
        left,right=TAIOSPipeline(),TAIOSPipeline(); ls,rs=IndustrialState(),IndustrialState()
        for event in events:
            a=left.process_event(event,ls); b=V2TransactionalRunner(right).process_event(event,rs)
            assert fingerprint(a.to_dict())==fingerprint(b.to_dict())
            ls,rs=a.state_after,b.state_after
            assert pipeline_state_fingerprint(left)==pipeline_state_fingerprint(right)

def test_sequential_runner_failure_rolls_back_and_event_remains_retryable(monkeypatch):
    from agentic.transactional_runner import V2TransactionalRunner
    from agentic.semantic_fingerprint import pipeline_state_fingerprint
    from environment.event_generator import EventGenerator
    from environment.industrial_environment import IndustrialState
    from core.pipeline_result import PipelineProcessingError
    g=EventGenerator(42,observable_state=True); run=g.create_run('S2',10); event=g.generate('S2',10,run)[4]
    p=TAIOSPipeline(); runner=V2TransactionalRunner(p); before=pipeline_state_fingerprint(p)
    monkeypatch.setattr(p.risk_agent,'assess',lambda *_a,**_k: (_ for _ in ()).throw(ValueError('risk')))
    with pytest.raises(PipelineProcessingError): runner.process_event(event,IndustrialState())
    assert pipeline_state_fingerprint(p)==before and event.event_id not in p._processed_events

def test_sequential_runner_supports_bounded_agentic_divergence():
    from agentic.bounded_selector import BoundedAgenticSelector
    from agentic.contracts import AgenticProposal
    from agentic.transactional_runner import V2TransactionalRunner
    from environment.event_generator import EventGenerator
    from environment.industrial_environment import IndustrialState
    g=EventGenerator(42,observable_state=True); run=g.create_run('S2',10); event=g.generate('S2',10,run)[4]
    def select(context, plan, baseline, assurance, authority, assured_authority):
        proposal=AgenticProposal(recommended_action='MONITOR',ranked_candidate_actions=('MONITOR',),reason_codes=('MOCK',),rationale='bounded',confidence=.5,uncertainty='mock',evidence_references=('test',))
        return BoundedAgenticSelector().select(context,plan,proposal,assurance,authority)[0]
    result=V2TransactionalRunner(TAIOSPipeline()).process_event(event,IndustrialState(),decision_selector=select)
    assert result.proposed_decision.selected_action.value=='MONITOR'
    assert 'MONITOR' in [c.action.value for c in result.planning_result.candidates]
    assert result.governance_decision.proposal_reference==result.proposed_decision.reference

def test_agentic_failure_selector_preserves_v1_decision_and_governance_chain():
    from agentic.adapter import resolve_advisory
    from agentic.contracts import AgenticInput
    from agentic.mock_llm import MockLLM, MockMode
    from agentic.transactional_runner import V2TransactionalRunner
    from environment.event_generator import EventGenerator
    from environment.industrial_environment import IndustrialState
    g=EventGenerator(42,observable_state=True); run=g.create_run('S2',10); event=g.generate('S2',10,run)[4]
    def fallback_selector(context, plan, baseline, assurance, authority, assured_authority):
        safe=AgenticInput(observation={'source_id':context.source_id},semantics={},authorization_status=context.authorization_status.value,trust_summary={},threat_summary={},risk_summary={},drift_summary={},adaptation_summary={},assured_actions=tuple(k for k,v in assured_authority.action_authority.items() if v=='PERMITTED'),planner_candidates=tuple(c.action.value for c in plan.candidates),evidence_references=('test',))
        status, selected, reason=resolve_advisory(safe,baseline,MockLLM(MockMode.TIMEOUT))
        assert reason=='TIMEOUT'
        return selected
    baseline=TAIOSPipeline().process_event(event,IndustrialState())
    result=V2TransactionalRunner(TAIOSPipeline()).process_event(event,IndustrialState(),decision_selector=fallback_selector)
    assert result.proposed_decision==baseline.proposed_decision
    assert result.governance_decision.to_dict()==baseline.governance_decision.to_dict()

def test_transaction_rejects_lifecycle_stage_replay():
    pipeline = TAIOSPipeline()
    transaction = TAIOSTransactionContext(pipeline).begin()
    transaction.stage_complete('trust')
    with pytest.raises(RuntimeError, match='stage replayed'):
        transaction.stage_complete('trust')
    transaction.rollback('synthetic')
