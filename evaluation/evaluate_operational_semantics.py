"""Structural coverage diagnostic for Milestone-6A operational semantics."""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from core.taios_pipeline import TAIOSPipeline
from environment.event_generator import EventGenerator
from evaluation.formal_evaluator import TAIOSEvaluator
from evaluation.run_formal_evaluation import SEEDS, SCENARIOS

BASELINE_STRUCTURE = {
    'proposals': {'ALLOW': 93, 'REQUEST_APPROVAL': 207},
    'governance_statuses': {'APPROVAL_REQUIRED': 207, 'APPROVED': 93},
    'execution_statuses': {'PENDING_APPROVAL': 207, 'SUCCEEDED': 93},
}
BASELINE_FORMAL = {
    'exact_action_agreement': 143 / 300,
    'unsafe_action_rate': 0.0,
    'false_intervention_rate': 72 / 165,
    'proposal_review_burden': 207 / 300,
    'autonomous_execution_rate': 93 / 300,
}


def _increment(group, key, status):
    group.setdefault(key, Counter())[status] += 1


def evaluate(events_per_run=10):
    status = Counter()
    operations, targets, scenarios = {}, {}, {}
    unresolved = Counter()
    proposals, governance, execution = Counter(), Counter(), Counter()
    completed = []
    registry = None
    for scenario in SCENARIOS:
        for seed in SEEDS:
            generator = EventGenerator(seed, observable_state=True)
            experiment = generator.create_run(scenario, events_per_run)
            events = generator.generate(scenario, events_per_run, experiment)
            episode = TAIOSPipeline().run_episode(
                events, scenario_reference=experiment.experiment_id, seed=seed)
            completed.append((episode, events))
            for result in episode.pipeline_results:
                assessment = result.operational_semantic_assessment
                registry = assessment.semantic_policy_fingerprint
                name = assessment.semantic_status.value
                status[name] += 1
                _increment(operations, assessment.operation, name)
                _increment(targets, assessment.target_type, name)
                _increment(scenarios, scenario, name)
                unresolved.update(assessment.unresolved_semantic_requirements)
                proposals[result.proposed_decision.selected_action.value] += 1
                governance[result.governance_decision.status.value] += 1
                execution[result.execution_result.execution_status.value] += 1
    total = sum(status.values())
    established = status['SUPPORTED_VALID'] + status['SUPPORTED_INVALID']
    current_structure = {
        'proposals': dict(sorted(proposals.items())),
        'governance_statuses': dict(sorted(governance.items())),
        'execution_statuses': dict(sorted(execution.items())),
    }
    formal = TAIOSEvaluator().evaluate_experiment(completed).to_dict()['overall_results']
    current_formal = {key: formal[key] for key in BASELINE_FORMAL}
    return {
        'semantic_policy_version': 'milestone6a-operational-semantics-v1',
        'semantic_configuration_fingerprint': registry,
        'seeds': list(SEEDS), 'scenarios': list(SCENARIOS),
        'events_per_run': events_per_run, 'total_events': total,
        'semantic_status_distribution': dict(sorted(status.items())),
        'semantic_coverage': {
            'fully_established_events': established,
            'fully_established_rate': established / total if total else None,
            'underspecified_events': status['UNDERSPECIFIED'],
            'underspecified_rate': status['UNDERSPECIFIED'] / total if total else None,
            'unsupported_events': status['UNSUPPORTED'],
            'unsupported_rate': status['UNSUPPORTED'] / total if total else None,
            'interpretation': 'Semantic coverage only; not decision accuracy or security effectiveness.',
        },
        'by_operation': {key: dict(sorted(value.items())) for key, value in sorted(operations.items())},
        'by_target_type': {key: dict(sorted(value.items())) for key, value in sorted(targets.items())},
        'by_scenario': {key: dict(sorted(value.items())) for key, value in sorted(scenarios.items())},
        'unresolved_requirements': dict(sorted(unresolved.items())),
        'structural_replay': {
            'before_milestone6a': BASELINE_STRUCTURE,
            'after_milestone6a': current_structure,
            'changed': current_structure != BASELINE_STRUCTURE,
        },
        'post_freeze_formal_evaluation': {
            'before_milestone6a': BASELINE_FORMAL,
            'after_milestone6a': current_formal,
            'changed': current_formal != BASELINE_FORMAL,
            'note': 'Descriptive comparison performed only after semantic implementation was frozen.',
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', type=int, default=10)
    parser.add_argument('--output', type=Path,
                        default=Path('results/milestone6a-operational-semantics.json'))
    args = parser.parse_args()
    result = evaluate(args.events)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n',
        encoding='utf-8')
    print(f'Assessed {result["total_events"]} events; saved {args.output}')


if __name__ == '__main__':
    main()
