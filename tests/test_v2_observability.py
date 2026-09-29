from agentic.observability import WorkflowObservability
def test_observability_excludes_duration_from_semantics():
 o=WorkflowObservability(); t=o.start('trust');o.finish(t,'OK'); assert o.semantic_view()==(('trust','OK'),);assert 'duration_seconds' in o.events[0]
