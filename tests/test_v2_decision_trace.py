from core.taios_pipeline import TAIOSPipeline
from environment.event_generator import EventGenerator
from environment.industrial_environment import IndustrialState
from agentic.decision_trace import build_decision_trace

def test_trace_separates_deterministic_and_agentic_sections():
 g=EventGenerator(42,observable_state=True); run=g.create_run('S2',10); event=g.generate('S2',10,run)[4]
 trace=build_decision_trace(TAIOSPipeline().process_event(event,IndustrialState()))
 assert 'trust' in trace['deterministic_assessments'] and trace['agentic_reasoning'] is None
 assert trace['governance']['proposed_action']==trace['decision']['selected_action']
 assert 'ground_truth' not in trace['observation']
