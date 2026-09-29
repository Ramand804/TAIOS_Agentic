from evaluation.evaluate_v2_agentic import evaluate

def test_harness_uses_identical_streams_and_preserves_governance():
 r=evaluate(scenarios=('S2',),seeds=(42,),events=10)
 rows=r['results']; streams={v['stream_fingerprint'] for v in rows.values()}
 assert len(streams)==1 and r['live_llm_status']=='NOT_RUN_NO_CREDENTIAL'
 assert r['governance_ablation']['valid'] is False
 assert rows['AGENTIC_MOCK|S2|42']['metrics']['proposal_validation_rate']==1.0
 assert rows['AGENTIC_LLM|S2|42']['metrics']['fallback_rate']==1.0

def test_no_memory_ablation_disables_retrieval():
 r=evaluate(scenarios=('S2',),seeds=(42,),events=10)
 assert r['results']['NO_MEMORY|S2|42']['metrics']['memory_retrieval_use_rate']==0.0
 assert r['results']['AGENTIC_MOCK|S2|42']['metrics']['memory_retrieval_use_rate']>0.0
