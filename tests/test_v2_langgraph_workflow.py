import pytest
pytest.importorskip('langgraph')
from agentic.contracts import AgenticInput, ValidationStatus
from agentic.graph_state import PROHIBITED_GRAPH_FIELDS
from agentic.langgraph_workflow import WORKFLOW_VERSION, build_mock_workflow
from agentic.mock_llm import MockLLM, MockMode

def _input():
    return AgenticInput(observation={'source_id': 'PLC-01'}, semantics={}, authorization_status='AUTHORIZED', trust_summary={}, threat_summary={}, risk_summary={}, drift_summary={}, adaptation_summary={}, assured_actions=('ALLOW',), planner_candidates=('ALLOW',), evidence_references=('evidence-1',))
def _state(**extra):
    state={'agentic_input':_input(),'deterministic_proposal':'v1-proposal'}; state.update(extra); return state

def test_graph_compiles_and_runs_with_mock_llm():
    output=build_mock_workflow(MockLLM()).invoke(_state())
    assert output['validation_status'] is ValidationStatus.VALID
    assert output['agentic_mode']=='AGENTIC_MOCK' and output['visited_nodes']==('agentic_advisory',)
    assert output['workflow_version']==WORKFLOW_VERSION

def test_graph_mock_execution_is_deterministic():
    graph=build_mock_workflow(MockLLM()); assert graph.invoke(_state())==graph.invoke(_state())

@pytest.mark.parametrize('mode,status',[(MockMode.MALFORMED_OUTPUT,ValidationStatus.MISSING_REQUIRED_FIELD),(MockMode.TIMEOUT,ValidationStatus.TIMEOUT),(MockMode.PROVIDER_ERROR,ValidationStatus.PROVIDER_ERROR),(MockMode.UNKNOWN_ACTION,ValidationStatus.INVALID_ACTION)])
def test_graph_invalid_or_failed_advice_uses_exact_v1_fallback(mode,status):
    output=build_mock_workflow(MockLLM(mode)).invoke(_state())
    assert output['validation_status'] is status and output['resolved_proposal']=='v1-proposal'
    assert output['fallback_reason'] and 'validated_advisory' not in output

def test_graph_advisory_does_not_overwrite_deterministic_assessments_or_authority():
    snapshots={'trust':'t','risk':'r','drift':'d'}
    output=build_mock_workflow(MockLLM()).invoke(_state(deterministic_assessments=snapshots,authority_state='authority',assurance_state='restricted',governance_state='rejected',execution_state='not-run'))
    assert output['deterministic_assessments']==snapshots and output['authority_state']=='authority'
    assert output['assurance_state']=='restricted' and output['governance_state']=='rejected' and output['execution_state']=='not-run'

def test_graph_state_excludes_evaluator_metadata():
    assert 'ground_truth' in PROHIBITED_GRAPH_FIELDS
    assert 'ground_truth' not in AgenticInput.__dataclass_fields__
    assert 'expected_safe_action' not in AgenticInput.__dataclass_fields__
    assert 'scenario_id' not in AgenticInput.__dataclass_fields__

def test_graph_records_separated_agentic_provenance():
    output=build_mock_workflow(MockLLM()).invoke(_state())
    assert output['llm_provenance'].validated_proposal==output['validated_advisory']
    assert output['llm_provenance'].llm_provider=='mock' and output['llm_provenance'].raw_response_hash
