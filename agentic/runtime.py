"""V2 mode dispatch over the shared transaction-safe runner."""
from agentic.adapter import ExecutionMode, resolve_advisory
from agentic.bounded_selector import BoundedAgenticSelector
from agentic.contracts import AgenticInput
from agentic.mock_llm import MockLLM
from agentic.transactional_runner import V2TransactionalRunner
from agentic.langgraph_workflow import build_full_mock_lifecycle_workflow
from agentic.provider import ProviderReasoner, UnavailableProvider

class V2Runtime:
 def __init__(self,pipeline,*,mode=ExecutionMode.DETERMINISTIC_V1,reasoner=None,memory_enabled=True):
  self.pipeline=pipeline; self.mode=ExecutionMode(mode); self.reasoner=reasoner; self.memory_enabled=memory_enabled; self.selector=BoundedAgenticSelector(); self._workflow=None
 def _selector(self,context,plan,baseline,assurance,authority,assured_authority):
  allowed=tuple(k for k,v in assured_authority.action_authority.items() if v=='PERMITTED')
  inp=AgenticInput(observation={'source_id':context.source_id,'target_id':context.target_id,'operation':context.observation['operation']},semantics=context.operational_semantic_assessment.to_dict(),authorization_status=context.authorization_status.value,trust_summary=context.trust_assessment.to_inference_dict(),threat_summary={},risk_summary=context.risk_assessment.to_inference_dict(),drift_summary={},adaptation_summary={},assured_actions=allowed,planner_candidates=tuple(c.action.value for c in plan.candidates),evidence_references=(context.reference,assurance.reference),baseline_action=(baseline.selected_action.value if baseline.selected_action else None))
  status,proposal,_=resolve_advisory(inp,baseline,self.reasoner)
  return self.selector.select(context,plan,proposal,assurance,authority,status)[0]
 def process_event(self,event,state):
  if self.mode==ExecutionMode.DETERMINISTIC_V1:return self.pipeline.process_event(event,state)
  if self.mode==ExecutionMode.AGENTIC_MOCK:
   if self._workflow is None:self._workflow=build_full_mock_lifecycle_workflow(self.pipeline,self.reasoner or MockLLM(),mode='AGENTIC_MOCK',memory_enabled=self.memory_enabled)
   output=self._workflow.invoke({'event':event,'industrial_state':state})
   self.last_graph_output=output
   return output['result']
  provider=self.reasoner if self.reasoner is not None else UnavailableProvider()
  reasoner=provider if isinstance(provider, ProviderReasoner) else ProviderReasoner(provider)
  if self._workflow is None:self._workflow=build_full_mock_lifecycle_workflow(self.pipeline,reasoner,mode='AGENTIC_LLM',memory_enabled=self.memory_enabled)
  output=self._workflow.invoke({'event':event,'industrial_state':state})
  self.last_graph_output=output
  return output['result']
