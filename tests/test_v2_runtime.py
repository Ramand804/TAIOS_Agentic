from agentic.adapter import ExecutionMode
from agentic.mock_llm import MockLLM,MockMode
from agentic.runtime import V2Runtime
from core.taios_pipeline import TAIOSPipeline
from environment.event_generator import EventGenerator
from environment.industrial_environment import IndustrialState

def event():
 g=EventGenerator(42,observable_state=True); r=g.create_run('S2',10); return g.generate('S2',10,r)[4]
def test_mock_mode_matches_v1_when_mock_recommends_baseline():
 a=V2Runtime(TAIOSPipeline()).process_event(event(),IndustrialState())
 b=V2Runtime(TAIOSPipeline(),mode=ExecutionMode.AGENTIC_MOCK).process_event(event(),IndustrialState())
 assert a.proposed_decision==b.proposed_decision and a.governance_decision==b.governance_decision
def test_mock_failure_uses_v1_fallback():
 a=V2Runtime(TAIOSPipeline()).process_event(event(),IndustrialState())
 b=V2Runtime(TAIOSPipeline(),mode=ExecutionMode.AGENTIC_MOCK,reasoner=MockLLM(MockMode.TIMEOUT)).process_event(event(),IndustrialState())
 assert a.proposed_decision==b.proposed_decision

def test_agentic_llm_unavailable_provider_fails_closed_to_v1_baseline():
    baseline = V2Runtime(TAIOSPipeline()).process_event(event(), IndustrialState())
    runtime = V2Runtime(TAIOSPipeline(), mode=ExecutionMode.AGENTIC_LLM)
    result = runtime.process_event(event(), IndustrialState())
    assert result.proposed_decision == baseline.proposed_decision
    assert runtime.last_graph_output['validation_status'].value == 'MODEL_UNAVAILABLE'
    assert runtime.last_graph_output['fallback_reason'] == 'MODEL_UNAVAILABLE'

def test_runtime_retains_safe_working_memory_across_episode_events():
 g=EventGenerator(42,observable_state=True); run=g.create_run('S2',10); events=g.generate('S2',10,run)
 runtime=V2Runtime(TAIOSPipeline(),mode=ExecutionMode.AGENTIC_MOCK); first=runtime.process_event(events[0],IndustrialState()); runtime.process_event(events[1],first.state_after)
 assert runtime.last_graph_output['memory_retrieval']['retrieved_count']==1
 assert runtime.last_graph_output['memory_retrieval']['included_in_reasoning'] is True
