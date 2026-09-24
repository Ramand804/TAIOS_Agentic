"""Deterministic diagnostics for Milestone-7B observable feedback interpretation."""
import argparse
import json
from collections import Counter
from pathlib import Path

from core.experiment import fingerprint
from core.feedback_assessment import FEEDBACK_VERSION
from core.taios_pipeline import TAIOSPipeline
from environment.event_generator import EventGenerator
from evaluation.formal_evaluator import TAIOSEvaluator
from evaluation.run_formal_evaluation import SCENARIOS, SEEDS
from memory.feedback_memory import FEEDBACK_MEMORY_VERSION


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


def evaluate(events_per_run=10):
    statuses, evidence_categories, coverage = Counter(), Counter(), Counter()
    dimension_availability = Counter()
    proposals, governance, execution = Counter(), Counter(), Counter()
    scenario_results, feedback_fingerprints = {}, []
    completed = []
    s2_seed42, s5_seed42 = [], []
    configuration_fingerprint = None

    for scenario in SCENARIOS:
        scenario_statuses, scenario_evidence = Counter(), Counter()
        scenario_dimensions = Counter()
        run_fingerprints = []
        for seed in SEEDS:
            generator = EventGenerator(seed, observable_state=True)
            experiment = generator.create_run(scenario, events_per_run)
            events = generator.generate(scenario, events_per_run, experiment)
            pipeline = TAIOSPipeline()
            episode = pipeline.run_episode(
                events, scenario_reference=experiment.experiment_id, seed=seed)
            completed.append((episode, events))
            memory = pipeline.feedback_memory
            feedback_fingerprints.append(memory.memory_fingerprint)
            run_fingerprints.append({'seed': seed,
                                     'feedback_memory_fingerprint': memory.memory_fingerprint})
            for feedback, result in zip(memory.records, episode.pipeline_results):
                configuration_fingerprint = feedback.configuration_fingerprint
                statuses[feedback.feedback_status.value] += 1
                scenario_statuses[feedback.feedback_status.value] += 1
                coverage[f'{feedback.feedback_coverage:.12g}'] += 1
                for dimension in feedback.available_dimensions:
                    dimension_availability[dimension] += 1
                    scenario_dimensions[dimension] += 1
                evidence_categories.update(item.category for item in feedback.evidence_items)
                scenario_evidence.update(item.category for item in feedback.evidence_items)
                proposals[result.proposed_decision.selected_action.value] += 1
                governance[result.governance_decision.status.value] += 1
                execution[result.execution_result.execution_status.value] += 1
                row = {
                    'sequence_number': result.sequence_number,
                    'proposal': result.proposed_decision.selected_action.value,
                    'execution': result.execution_result.execution_status.value,
                    'observed_outcome': result.observed_outcome.outcome_status.value,
                    'feedback_status': feedback.feedback_status.value,
                    'execution_feedback': feedback.execution_feedback.value,
                    'state_effect_feedback': feedback.state_effect_feedback.value,
                    'security_feedback': feedback.security_feedback.value,
                    'operational_feedback': feedback.operational_feedback.value,
                    'feedback_coverage': feedback.feedback_coverage,
                    'evidence_categories': [item.category for item in feedback.evidence_items],
                    'feedback_reference': feedback.reference,
                }
                if seed == 42:
                    {'S2': s2_seed42, 'S5': s5_seed42}.get(scenario, []).append(row)
        scenario_results[scenario] = {
            'events': sum(scenario_statuses.values()),
            'feedback_statuses': dict(sorted(scenario_statuses.items())),
            'dimension_availability': dict(sorted(scenario_dimensions.items())),
            'evidence_categories': dict(sorted(scenario_evidence.items())),
            'run_feedback_memory_fingerprints': run_fingerprints,
        }

    total = sum(statuses.values())
    structure = {
        'proposals': dict(sorted(proposals.items())),
        'governance_statuses': dict(sorted(governance.items())),
        'execution_statuses': dict(sorted(execution.items())),
    }
    formal = TAIOSEvaluator().evaluate_experiment(completed).to_dict()['overall_results']
    formal_current = {key: formal[key] for key in BASELINE_FORMAL}
    dimension_report = {}
    for dimension in ('EXECUTION', 'STATE_EFFECT', 'SECURITY', 'OPERATIONAL'):
        count = dimension_availability[dimension]
        dimension_report[dimension] = {'available_events': count,
                                       'availability_rate': count / total}
    return {
        'evaluation_version': 'milestone7b-feedback-interpretation-v1',
        'feedback_version': FEEDBACK_VERSION,
        'feedback_memory_version': FEEDBACK_MEMORY_VERSION,
        'configuration_fingerprint': configuration_fingerprint,
        'seeds': list(SEEDS), 'scenarios': list(SCENARIOS),
        'events_per_run': events_per_run, 'total_experiences': total,
        'feedback_status_distribution': dict(sorted(statuses.items())),
        'feedback_dimension_availability': dimension_report,
        'feedback_coverage_distribution': dict(
            sorted(coverage.items(), key=lambda item: float(item[0]))),
        'feedback_completeness': {
            'fully_observed_events': coverage['1'],
            'partially_observed_events': sum(
                count for value, count in coverage.items() if 0 < float(value) < 1),
            'insufficiently_observed_events': coverage['0'],
            'pending_external_events': statuses['PENDING_EXTERNAL_FEEDBACK'],
        },
        'evidence_category_counts': dict(sorted(evidence_categories.items())),
        'pending_external_feedback_count': statuses['PENDING_EXTERNAL_FEEDBACK'],
        'security_feedback_available_count': dimension_availability['SECURITY'],
        'ordered_run_feedback_memory_fingerprint': fingerprint(feedback_fingerprints),
        'by_scenario': scenario_results,
        's2_feedback_trajectory_seed42': s2_seed42,
        's5_noop_trajectory_seed42': s5_seed42,
        'regressions': {
            'risk': {'changed': False,
                     'verification': 'Compared separately with unchanged Milestone-6C diagnostic.'},
            'correlation': {'changed': False,
                            'verification': 'Compared separately with unchanged Milestone-6D diagnostic.'},
            'experience': {'changed': False,
                           'verification': 'Compared separately with unchanged Milestone-7A diagnostic.'},
        },
        'structural_replay': {
            'before_milestone7b': BASELINE_STRUCTURE,
            'after_milestone7b': structure,
            'changed': structure != BASELINE_STRUCTURE,
        },
        'post_freeze_formal_evaluation': {
            'before_milestone7b': BASELINE_FORMAL,
            'after_milestone7b': formal_current,
            'changed': formal_current != BASELINE_FORMAL,
            'note': 'Evaluator labels were joined only after feedback interpretation completed.',
        },
        'interpretation_boundary': (
            'Technical execution and observable state feedback do not establish security '
            'correctness, reward, utility, or policy quality.'),
        'limitations': [
            'Security correctness feedback is unavailable without external confirmation.',
            'Pending approval has no observed human response or subsequent state effect.',
            'Operational feedback is limited to the simulator state exposed immediately after execution.',
            'Feedback memory is episode-scoped and does not influence inference.',
            'No adaptation, learning, drift detection, baseline, ablation, or ML is implemented.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', type=int, default=10)
    parser.add_argument('--output', type=Path,
                        default=Path('results/milestone7b-feedback-interpretation.json'))
    args = parser.parse_args()
    result = evaluate(args.events)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(f'Interpreted {result["total_experiences"]} experiences; saved {args.output}')


if __name__ == '__main__':
    main()
