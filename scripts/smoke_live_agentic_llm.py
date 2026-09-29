"""One-request live TAIOS smoke test. Run manually from a credentialed terminal."""
import json
import os
from agentic.adapter import ExecutionMode
from agentic.openai_provider import OpenAIProvider
from agentic.runtime import V2Runtime
from core.taios_pipeline import TAIOSPipeline
from environment.event_generator import EventGenerator
from environment.industrial_environment import IndustrialState


def main():
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        raise SystemExit('LIVE_PROVIDER_BLOCKED_NO_CREDENTIAL')
    generator = EventGenerator(42, observable_state=True)
    run = generator.create_run('S2', 10)
    # Event five has a canonical ALLOW baseline and multiple planner candidates.
    event = generator.generate('S2', 10, run)[4]
    provider = OpenAIProvider(api_key=api_key)
    runtime = V2Runtime(TAIOSPipeline(), mode=ExecutionMode.AGENTIC_LLM,
                        reasoner=provider)
    result = runtime.process_event(event, IndustrialState())
    graph = runtime.last_graph_output
    selection = graph['selection_provenance']
    provenance = graph['llm_provenance']
    metadata = provider.last_metadata
    report = {
        'smoke_status': 'PASS' if selection.selection_accepted or graph['fallback_reason'] else 'FAIL',
        'live_requests_made': 1,
        'provider': provenance.llm_provider,
        'model': provenance.llm_model,
        'workflow_version': 'v2-2c-full-lifecycle-1',
        'prompt_version': provenance.prompt_version,
        'schema_version': provenance.response_schema_version,
        'validation_status': graph['validation_status'].value,
        'fallback_reason': graph['fallback_reason'],
        'planner_candidates': list(selection.planner_candidate_actions),
        'assurance_permitted_actions': list(selection.assured_permitted_actions),
        'authority_permitted_actions': [
            action for action, status in result.authority_assessment.action_authority.items()
            if status == 'PERMITTED'],
        'baseline_action': selection.deterministic_v1_action,
        'llm_recommended_action': selection.llm_recommended_action,
        'final_action': selection.selected_action,
        'candidate_compliant': selection.selected_action in selection.planner_candidate_actions,
        'assurance_compliant': selection.selected_action in selection.assured_permitted_actions,
        'authority_compliant': selection.selected_action in [
            action for action, status in result.authority_assessment.action_authority.items()
            if status == 'PERMITTED'],
        'governance_status': result.governance_decision.status.value,
        'execution_status': result.execution_result.execution_status.value,
        'direct_execution_by_llm': False,
        'latency_seconds': metadata.latency_seconds if metadata else None,
        'token_usage': metadata.token_usage if metadata else None,
        'request_hash': metadata.request_hash if metadata else None,
        'response_hash': metadata.response_hash if metadata else None,
    }
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
