"""Deterministic structural diagnostics for the integrated Day-5A pipeline."""
import argparse
import json
from collections import Counter
from pathlib import Path

from core.taios_pipeline import PIPELINE_VERSION, TAIOSPipeline
from environment.event_generator import EventGenerator

SEEDS = (42, 123, 456, 789, 2026)
SCENARIOS = tuple(f'S{i}' for i in range(1, 7))


def _trace(result):
    observation = dict(result.observable_input)
    validity = result.decision_context.capabilities.operational_validity
    trust = result.trust_assessment
    risk = result.risk_assessment
    proposal = result.proposed_decision
    governance = result.governance_decision
    execution = result.execution_result
    return {
        'sequence_number': result.sequence_number,
        'pipeline_fingerprint': result.pipeline_fingerprint,
        'what_happened': {
            'event_reference': result.event_reference,
            'source_id': observation['source_id'], 'target_id': observation['target_id'],
            'operation': observation['operation'],
            'requested_value': observation['requested_value'],
            'contextual_features': dict(observation['contextual_features']),
        },
        'what_taios_knew': {
            'trust_before': trust.previous_composite_trust,
            'trust_after': trust.composite_trust,
            'trust_state_version': trust.trust_state_version,
            'risk_score': risk.risk_score, 'risk_coverage': risk.coverage,
            'authorization': result.authorization_assessment.status.value,
            'authority': result.authority_assessment.to_dict()['action_authority'],
            'operational_validity': validity.to_dict(),
        },
        'what_it_considered': [candidate.action.value
                               for candidate in result.planning_result.candidates],
        'what_it_proposed': {
            'action': proposal.selected_action.value,
            'reason': proposal.primary_reason,
            'proposal_reference': proposal.reference,
        },
        'what_governance_did': {
            'status': governance.status.value,
            'checks': dict(governance.policy_checks),
            'reason': governance.reason,
            'governance_reference': governance.reference,
        },
        'what_execution_did': {
            'status': execution.execution_status.value,
            'applied_value': execution.applied_value,
            'mutation_applied': execution.mutation_applied,
            'reason': execution.reason,
            'execution_reference': execution.execution_id,
            'state_version_before': execution.state_version_before,
            'state_version_after': execution.state_version_after,
        },
        'state_continuity': {
            'input_state_reference': result.input_state_reference,
            'state_before_reference': execution.state_before_reference,
            'state_after_reference': execution.state_after_reference,
            'regime_transition_applied': result.regime_transition_applied,
        },
    }


def evaluate(events_per_run=10):
    proposal_counts, governance_counts, execution_counts = Counter(), Counter(), Counter()
    runs = []
    for scenario in SCENARIOS:
        for seed in SEEDS:
            generator = EventGenerator(seed, observable_state=True)
            experiment = generator.create_run(scenario, events_per_run)
            events = generator.generate(scenario, events_per_run, experiment)
            episode = TAIOSPipeline().run_episode(
                events, scenario_reference=experiment.experiment_id, seed=seed)
            summary = episode.to_dict()['structural_summary']
            proposal_counts.update(summary['proposals'])
            governance_counts.update(summary['governance_statuses'])
            execution_counts.update(summary['execution_statuses'])
            runs.append({
                'scenario': scenario, 'seed': seed,
                'experiment_id': experiment.experiment_id,
                'initial_state_reference': episode.initial_state_reference,
                'final_state_reference': episode.final_state_reference,
                'episode_fingerprint': episode.episode_fingerprint,
                'structural_summary': summary,
                'trace': [_trace(result) for result in episode.pipeline_results],
            })
    return {
        'pipeline_version': PIPELINE_VERSION,
        'seeds': list(SEEDS), 'scenarios': list(SCENARIOS),
        'events_per_run': events_per_run,
        'total_events': sum(len(run['trace']) for run in runs),
        'structural_distribution': {
            'proposals': dict(sorted(proposal_counts.items())),
            'governance_statuses': dict(sorted(governance_counts.items())),
            'execution_statuses': dict(sorted(execution_counts.items())),
        },
        'runs': runs,
        'interpretation': 'Structural integration behavior only; not accuracy or security effectiveness.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', type=int, default=10)
    parser.add_argument('--output', type=Path,
                        default=Path('results/day5a-end-to-end.json'))
    args = parser.parse_args()
    result = evaluate(args.events)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n',
        encoding='utf-8')
    print(f'Processed {result["total_events"]} events; saved {args.output}')


if __name__ == '__main__':
    main()
