from agentic.working_memory import WorkingMemory
from core.taios_pipeline import TAIOSPipeline
from environment.event_generator import EventGenerator
from environment.industrial_environment import IndustrialState

def test_working_memory_is_bounded_sanitized_and_deterministic():
 g=EventGenerator(42,observable_state=True); r=g.create_run('S2',10); events=g.generate('S2',10,r)
 def build():
  p=TAIOSPipeline(); m=WorkingMemory(2); state=IndustrialState()
  for event in events[:3]: row=p.process_event(event,state);state=row.state_after;m.append_result(row)
  return m
 a,b=build(),build(); assert len(a.snapshot())==2 and a.semantic_fingerprint==b.semantic_fingerprint
 assert all(not hasattr(x,'ground_truth') for x in a.snapshot())

def test_working_memory_retrieval_is_bounded_and_deterministic():
 from agentic.working_memory import WorkingMemoryEntry,retrieve
 memory=WorkingMemory(4)
 memory._entries.extend((WorkingMemoryEntry('a','ALLOW','APPROVED','SUCCEEDED','INSUFFICIENT_HISTORY'),WorkingMemoryEntry('b','REQUEST_APPROVAL','APPROVAL_REQUIRED','PENDING_APPROVAL','UNEXPLAINED_PERSISTENT_DRIFT')))
 assert [x.event_reference for x in retrieve(memory,decision='REQUEST_APPROVAL',limit=1)]==['b']
 assert retrieve(memory,drift='UNEXPLAINED_PERSISTENT_DRIFT')==retrieve(memory,drift='UNEXPLAINED_PERSISTENT_DRIFT')
