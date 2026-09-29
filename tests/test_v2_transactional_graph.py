import pytest
pytest.importorskip('langgraph')
from agentic.langgraph_workflow import build_transactional_runtime_workflow
from agentic.runtime import V2Runtime
from core.taios_pipeline import TAIOSPipeline
from environment.event_generator import EventGenerator
from environment.industrial_environment import IndustrialState

def test_transactional_graph_runs_canonical_event_to_terminal_state():
 g=EventGenerator(42,observable_state=True);r=g.create_run('S2',10);event=g.generate('S2',10,r)[4]
 out=build_transactional_runtime_workflow(V2Runtime(TAIOSPipeline())).invoke({'event':event,'industrial_state':IndustrialState()})
 assert out['terminal_state']=='COMPLETED' and out['visited_nodes']==('transaction_begin','transactional_runtime')
