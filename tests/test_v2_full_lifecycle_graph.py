import pytest
pytest.importorskip('langgraph')

from agentic.langgraph_workflow import build_full_mock_lifecycle_workflow
from agentic.mock_llm import MockLLM, MockMode
from agentic.semantic_fingerprint import fingerprint, pipeline_state_fingerprint
from core.pipeline_result import PipelineProcessingError
from core.taios_pipeline import TAIOSPipeline
from environment.event_generator import EventGenerator
from environment.industrial_environment import IndustrialState


def _event(index=4):
    generator = EventGenerator(42, observable_state=True)
    run = generator.create_run('S2', 10)
    return generator.generate('S2', 10, run)[index]


def test_full_lifecycle_graph_matches_v1_result_and_scientific_state():
    event = _event()
    v1_pipeline, graph_pipeline = TAIOSPipeline(), TAIOSPipeline()
    v1 = v1_pipeline.process_event(event, IndustrialState())
    graph = build_full_mock_lifecycle_workflow(graph_pipeline)
    output = graph.invoke({'event': event, 'industrial_state': IndustrialState()})
    assert fingerprint(v1.to_dict()) == fingerprint(output['result'].to_dict())
    assert pipeline_state_fingerprint(v1_pipeline) == pipeline_state_fingerprint(graph_pipeline)
    assert output['visited_nodes'] == (
        'transaction_begin', 'context', 'semantics', 'drift', 'authorization',
        'threat', 'correlation', 'trust', 'risk', 'decision_context', 'planning',
        'decision', 'memory_retrieval', 'llm_planning', 'bounded_selection', 'governance', 'execution',
        'outcome', 'experience', 'feedback_interpretation', 'feedback_commit',
        'adaptation', 'result', 'transaction_commit', 'trace')
    assert output['decision_trace']['decision'] == output['result'].proposed_decision.to_dict()
    assert 'ground_truth' not in output['decision_trace']['observation']


def test_full_graph_malformed_advice_uses_exact_v1_fallback():
    event = _event()
    baseline = TAIOSPipeline().process_event(event, IndustrialState())
    output = build_full_mock_lifecycle_workflow(
        TAIOSPipeline(), MockLLM(MockMode.MALFORMED_OUTPUT)).invoke(
            {'event': event, 'industrial_state': IndustrialState()})
    assert output['result'].proposed_decision == baseline.proposed_decision
    assert output['result'].governance_decision.to_dict() == baseline.governance_decision.to_dict()
    assert output['fallback_reason']


def test_full_graph_permitted_divergence_changes_only_bounded_decision():
    class MonitorReasoner:
        def reason(self, input):
            return {
                'recommended_action': 'MONITOR', 'ranked_candidate_actions': ['MONITOR'],
                'reason_codes': ['MOCK'], 'rationale': 'Deterministic permitted alternative.',
                'confidence': .5, 'uncertainty': 'mock',
                'evidence_references': list(input.evidence_references),
            }

    output = build_full_mock_lifecycle_workflow(TAIOSPipeline(), MonitorReasoner()).invoke(
        {'event': _event(), 'industrial_state': IndustrialState()})
    result, provenance = output['result'], output['selection_provenance']
    assert result.proposed_decision.selected_action.value == 'MONITOR'
    assert provenance.selection_accepted and provenance.selection_source == 'AGENTIC_VALIDATED'
    assert provenance.llm_recommended_action in provenance.planner_candidate_actions
    assert provenance.llm_recommended_action in provenance.assured_permitted_actions
    assert result.governance_decision.proposal_reference == result.proposed_decision.reference
    assert result.execution_result.requested_action == result.proposed_decision.selected_action


def test_full_graph_failure_rolls_back_and_remains_retryable(monkeypatch):
    pipeline = TAIOSPipeline()
    before = pipeline_state_fingerprint(pipeline)
    monkeypatch.setattr(pipeline.risk_agent, 'assess', lambda *_a, **_k: (_ for _ in ()).throw(ValueError('risk')))
    with pytest.raises(PipelineProcessingError):
        build_full_mock_lifecycle_workflow(pipeline).invoke(
            {'event': _event(), 'industrial_state': IndustrialState()})
    assert pipeline_state_fingerprint(pipeline) == before
    assert _event().event_id not in pipeline._processed_events


def test_full_graph_replay_does_not_repeat_scientific_commits():
    pipeline = TAIOSPipeline()
    graph = build_full_mock_lifecycle_workflow(pipeline)
    first = graph.invoke({'event': _event(), 'industrial_state': IndustrialState()})
    after_first = pipeline_state_fingerprint(pipeline)
    replay = graph.invoke({'event': _event(), 'industrial_state': first['result'].state_after})
    assert replay['visited_nodes'] == ('transaction_begin', 'replay')
    assert pipeline_state_fingerprint(pipeline) == after_first

@pytest.mark.parametrize('scenario', ('S2', 'S5'))
def test_full_graph_matches_v1_across_sequence_and_adaptive_state(scenario):
    generator = EventGenerator(42, observable_state=True)
    run = generator.create_run(scenario, 10)
    events = generator.generate(scenario, 10, run)
    v1_pipeline, graph_pipeline = TAIOSPipeline(), TAIOSPipeline()
    graph = build_full_mock_lifecycle_workflow(graph_pipeline)
    v1_state, graph_state = IndustrialState(), IndustrialState()
    for event in events:
        expected = v1_pipeline.process_event(event, v1_state)
        actual = graph.invoke({'event': event, 'industrial_state': graph_state})['result']
        assert fingerprint(expected.to_dict()) == fingerprint(actual.to_dict())
        v1_state, graph_state = expected.state_after, actual.state_after
        assert pipeline_state_fingerprint(v1_pipeline) == pipeline_state_fingerprint(graph_pipeline)

@pytest.mark.parametrize('mode', (MockMode.TIMEOUT, MockMode.PROVIDER_ERROR, MockMode.UNKNOWN_ACTION))
def test_full_graph_llm_failures_fail_closed_to_baseline(mode):
    event = _event()
    baseline = TAIOSPipeline().process_event(event, IndustrialState())
    output = build_full_mock_lifecycle_workflow(TAIOSPipeline(), MockLLM(mode)).invoke(
        {'event': event, 'industrial_state': IndustrialState()})
    assert output['result'].proposed_decision == baseline.proposed_decision
    assert output['selection_provenance'].fallback_used

def test_later_agentic_decision_receives_safe_retrieved_memory():
    from agentic.working_memory import WorkingMemory
    generator=EventGenerator(42,observable_state=True); run=generator.create_run('S2',10); events=generator.generate('S2',10,run)
    memory=WorkingMemory(); pipeline=TAIOSPipeline(); graph=build_full_mock_lifecycle_workflow(pipeline,working_memory=memory)
    first=graph.invoke({'event':events[0],'industrial_state':IndustrialState()})['result']
    second=graph.invoke({'event':events[1],'industrial_state':first.state_after})
    assert second['memory_retrieval']['retrieved_count']==1
    assert second['memory_retrieval']['included_in_reasoning'] is True
    assert second['agentic_input'].memory_context[0]['event_reference']==first.event_reference
    assert 'ground_truth' not in second['agentic_input'].memory_context[0]
