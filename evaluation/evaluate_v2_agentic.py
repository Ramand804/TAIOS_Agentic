"""V2 comparison harness. It never joins evaluator labels into agentic inference."""
from collections import Counter
from time import perf_counter
from dataclasses import asdict
from core.experiment import event_stream_fingerprint, fingerprint
from core.taios_pipeline import TAIOSPipeline
from core.ablation_configuration import AblationConfiguration, create_ablation_pipeline
from environment.event_generator import EventGenerator
from environment.industrial_environment import IndustrialState
from agentic.runtime import V2Runtime
from agentic.adapter import ExecutionMode

HARNESS_VERSION='v2-agentic-harness-1'
CONFIGURATIONS={
 'DETERMINISTIC_V1':(ExecutionMode.DETERMINISTIC_V1,None,True),
 'AGENTIC_MOCK':(ExecutionMode.AGENTIC_MOCK,None,True),
 'AGENTIC_LLM':(ExecutionMode.AGENTIC_LLM,None,True),
 'NO_AGENTIC_REASONING':(ExecutionMode.DETERMINISTIC_V1,None,True),
 'NO_MEMORY':(ExecutionMode.AGENTIC_MOCK,None,False),
 'NO_TRUST':(ExecutionMode.AGENTIC_MOCK,AblationConfiguration.NO_TRUST,True),
 'NO_DRIFT':(ExecutionMode.AGENTIC_MOCK,AblationConfiguration.NO_DRIFT,True),
 'NO_ADAPTATION':(ExecutionMode.AGENTIC_MOCK,AblationConfiguration.NO_ADAPT,True),
}

def _run(events, mode, ablation, memory_enabled):
    pipeline=create_ablation_pipeline(ablation) if ablation else TAIOSPipeline()
    runtime=V2Runtime(pipeline,mode=mode,memory_enabled=memory_enabled); state=IndustrialState(); rows=[]
    for event in events:
        started=perf_counter()
        result=runtime.process_event(event,state); state=result.state_after
        graph=getattr(runtime,'last_graph_output',{})
        selection=graph.get('selection_provenance')
        selected=result.proposed_decision.selected_action.value
        candidates=tuple(item.action.value for item in result.planning_result.candidates)
        assured=tuple(getattr(selection,'assured_permitted_actions',())) if selection else candidates
        authority=tuple(action for action,status in result.authority_assessment.action_authority.items() if status=='PERMITTED')
        rows.append({'action':result.proposed_decision.selected_action.value,
          'governance':result.governance_decision.status.value,
          'execution':result.execution_result.execution_status.value,
          'trust':result.trust_assessment.composite_trust,
          'drift':result.drift_assessment.status.value,
          'validation':(graph.get('validation_status').value if graph.get('validation_status') else None),
          'fallback':graph.get('fallback_reason'),
          'memory_retrieved':(graph.get('memory_retrieval',{}).get('retrieved_count',0)),
          'memory_used':(graph.get('memory_retrieval',{}).get('included_in_reasoning',False)),
          'baseline_action':(getattr(selection,'deterministic_v1_action',selected)),
          'agentic_accepted':bool(getattr(selection,'selection_accepted',False)),
          'candidate_compliant':selected in candidates,
          'assurance_compliant':selected in assured,
          'authority_compliant':selected in authority,
          'latency_seconds':perf_counter()-started})
    n=len(rows); actions=Counter(x['action'] for x in rows); governance=Counter(x['governance'] for x in rows)
    return {'events':n,'actions':dict(actions),'governance':dict(governance),
      'autonomous_action_rate':sum(x['execution']=='SUCCEEDED' for x in rows)/n,
      'human_review_rate':sum(x['execution']=='PENDING_APPROVAL' for x in rows)/n,
      'proposal_validation_rate':sum(x['validation']=='VALID' for x in rows)/n if any(x['validation'] for x in rows) else None,
      'fallback_rate':sum(x['fallback'] is not None for x in rows)/n if any(x['validation'] for x in rows) else None,
      'memory_retrieval_use_rate':sum(x['memory_used'] for x in rows)/n,
      'v1_agentic_agreement_rate':sum(x['action']==x['baseline_action'] for x in rows)/n,
      'agentic_divergence_rate':sum(x['action']!=x['baseline_action'] for x in rows)/n,
      'accepted_agentic_recommendations':sum(x['agentic_accepted'] for x in rows),
      'candidate_compliance_violations':sum(not x['candidate_compliant'] for x in rows),
      'assurance_compliance_violations':sum(not x['assurance_compliant'] for x in rows),
      'authority_compliance_violations':sum(not x['authority_compliant'] for x in rows),
      'mean_end_to_end_latency_seconds':sum(x['latency_seconds'] for x in rows)/n,
      'trust_trajectory':[x['trust'] for x in rows], 'drift_behavior':[x['drift'] for x in rows],
      'event_rows':rows}

def evaluate(*, scenarios=('S2',), seeds=(42,), events=10):
    streams={}
    for scenario in scenarios:
      for seed in seeds:
       generator=EventGenerator(seed,observable_state=True); run=generator.create_run(scenario,events); stream=generator.generate(scenario,events,run)
       streams[(scenario,seed)]=(run,stream)
    results={}
    for name,(mode,ablation,memory_enabled) in CONFIGURATIONS.items():
      for (scenario,seed),(run,stream) in streams.items():
       results[f'{name}|{scenario}|{seed}']={'stream_fingerprint':event_stream_fingerprint(stream),'experiment_id':run.experiment_id,'metrics':_run(stream,mode,ablation,memory_enabled)}
    return {'harness_version':HARNESS_VERSION,'configurations':{k:{'mode':v[0].value,'ablation':(v[1].value if v[1] else None),'memory_enabled':v[2]} for k,v in CONFIGURATIONS.items()},
      'live_llm_status':'NOT_RUN_NO_CREDENTIAL','governance_ablation':{'valid':False,'reason':'Governance is mandatory for execution integrity.'},
      'results':results,'limitations':['No live-provider result is generated without a credential.','Evaluator labels are not supplied to agentic inference.','Runtime harness reports operational comparisons; post-inference evaluator joins may be added separately.']}
