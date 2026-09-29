from agentic.contracts import AgenticInput,ValidationStatus
from agentic.mock_llm import MockLLM,MockMode
from agentic.validator import validate
from agentic.adapter import resolve_advisory
def ctx():return AgenticInput(observation={'source_id':'PLC-01'},semantics={},authorization_status='AUTHORIZED',trust_summary={},threat_summary={},risk_summary={},drift_summary={},adaptation_summary={},assured_actions=('ALLOW',),planner_candidates=('ALLOW',),evidence_references=('a',))
def test_allowlist_has_no_evaluator_fields():assert 'ground_truth' not in ctx().to_dict()['observation']
def test_valid_and_deterministic_mock():
 a=ctx(); assert MockLLM().reason(a)==MockLLM().reason(a); assert validate(MockLLM().reason(a),a)[0]==ValidationStatus.VALID
def test_invalid_actions_and_payload_rejected():
 a=ctx(); assert validate(MockLLM(MockMode.UNKNOWN_ACTION).reason(a),a)[0]==ValidationStatus.INVALID_ACTION; raw=MockLLM().reason(a);raw['payload']={};assert validate(raw,a)[0]==ValidationStatus.PROHIBITED_CONTENT
def test_failure_modes_are_explicit():
 a=ctx();assert validate(MockLLM(MockMode.MALFORMED_OUTPUT).reason(a),a)[0]!=ValidationStatus.VALID
def test_outside_duplicate_confidence_reason_and_fallback():
 a=ctx(); raw=MockLLM().reason(a);raw['ranked_candidate_actions']=['ALLOW','ALLOW'];assert validate(raw,a)[0]==ValidationStatus.DUPLICATE_CANDIDATES
 raw=MockLLM().reason(a);raw['confidence']=2;assert validate(raw,a)[0]==ValidationStatus.INVALID_CONFIDENCE
 raw=MockLLM().reason(a);raw['reason_codes']=['UNKNOWN'];assert validate(raw,a)[0]==ValidationStatus.PROHIBITED_CONTENT
 deterministic=object();status,fallback,reason=resolve_advisory(a,deterministic,MockLLM(MockMode.TIMEOUT));assert status==ValidationStatus.TIMEOUT and fallback is deterministic and reason=='TIMEOUT'
def test_nested_evaluator_labels_never_enter_input():
 a=ctx(); assert set(a.to_dict()['observation'])=={'source_id'}

def test_executable_text_and_unbounded_output_are_rejected():
 a=ctx(); raw=MockLLM().reason(a);raw['rationale']='execute command now';assert validate(raw,a)[0]==ValidationStatus.PROHIBITED_CONTENT
 raw=MockLLM().reason(a);raw['rationale']='x'*513;assert validate(raw,a)[0]==ValidationStatus.INVALID_SCHEMA
 raw=MockLLM().reason(a);raw['ranked_candidate_actions']='ALLOW';assert validate(raw,a)[0]==ValidationStatus.INVALID_SCHEMA
