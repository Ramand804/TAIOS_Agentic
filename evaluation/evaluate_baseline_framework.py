"""Milestone-8A controlled four-configuration comparison diagnostic."""
import argparse
import json
from pathlib import Path

from core.experimental_configuration import ExperimentalConfiguration
from core.experiment import event_stream_fingerprint
from environment.event_generator import EventGenerator
from evaluation.baseline_framework import CONFIGURATION_SPECS, create_pipeline
from evaluation.formal_evaluator import EVALUATION_VERSION, TAIOSEvaluator
from evaluation.run_formal_evaluation import SCENARIOS, SEEDS


PRIMARY = ('exact_action_agreement', 'unsafe_action_rate', 'false_intervention_rate',
           'proposal_review_burden', 'autonomous_execution_rate')


def _events(events_per_run):
    matrix = {}
    for scenario in SCENARIOS:
        for seed in SEEDS:
            generator = EventGenerator(seed, observable_state=True)
            run = generator.create_run(scenario, events_per_run)
            matrix[(scenario, seed)] = (
                run, generator.generate(scenario, events_per_run, run))
    return matrix


def _metric_summary(metrics):
    return {
        'exact_action_agreement': {
            'numerator': metrics['exact_action_matches'],
            'denominator': metrics['event_count'], 'rate': metrics['exact_action_agreement']},
        'unsafe_action_rate': {
            'numerator': metrics['unsafe_action_count'],
            'denominator': metrics['unsafe_action_eligible_events'],
            'rate': metrics['unsafe_action_rate']},
        'false_intervention_rate': {
            'numerator': metrics['false_intervention_count'],
            'denominator': metrics['false_intervention_eligible_events'],
            'rate': metrics['false_intervention_rate']},
        'review_burden': {
            'numerator': metrics['proposal_review_count'],
            'denominator': metrics['event_count'], 'rate': metrics['proposal_review_burden']},
        'autonomous_execution_rate': {
            'numerator': metrics['successful_autonomous_executions'],
            'denominator': metrics['event_count'], 'rate': metrics['autonomous_execution_rate']},
    }


def evaluate(events_per_run=10):
    streams = _events(events_per_run)
    configuration_results = {}
    raw_references = []
    episode_summaries = []
    detail = {}
    for configuration in ExperimentalConfiguration:
        pairs, result_lookup = [], {}
        for scenario in SCENARIOS:
            for seed in SEEDS:
                run, events = streams[(scenario, seed)]
                pipeline = create_pipeline(configuration)
                episode = pipeline.run_episode(
                    events, scenario_reference=run.experiment_id, seed=seed)
                pairs.append((episode, events))
                result_lookup[(scenario, seed)] = (episode, pipeline)
                episode_summaries.append({
                    'configuration': configuration.value, 'scenario': scenario,
                    'seed': seed, 'experiment_id': run.experiment_id,
                    'event_stream_fingerprint': event_stream_fingerprint(events),
                    'episode_fingerprint': episode.episode_fingerprint,
                    'pipeline_version': episode.pipeline_version,
                    'initial_state_reference': episode.initial_state_reference,
                })
                for row in episode.pipeline_results:
                    raw_references.append({
                        'configuration': configuration.value, 'scenario': scenario,
                        'seed': seed, 'sequence_number': row.sequence_number,
                        'event_id': row.event_id, 'event_reference': row.event_reference,
                        'pipeline_fingerprint': row.pipeline_fingerprint,
                    })
        evaluated = TAIOSEvaluator().evaluate_experiment(pairs).to_dict()
        overall = evaluated['overall_results']
        spec = CONFIGURATION_SPECS[configuration]
        configuration_results[configuration.value] = {
            'definition': {**spec.to_dict(),
                           'configuration_fingerprint': spec.configuration_fingerprint},
            'aggregate_metrics': _metric_summary(overall),
            'proposal_distribution': overall['proposal_distribution'],
            'governance_distribution': overall['governance_distribution'],
            'execution_distribution': overall['execution_distribution'],
            'seed_level_aggregation': overall['seed_level_aggregation'],
            'per_seed_metrics': evaluated['per_seed_results'],
            'per_scenario_metrics': evaluated['per_scenario_results'],
            'evaluator_version': evaluated['evaluation_version'],
            'evaluator_fingerprint': evaluated['configuration_fingerprint'],
        }
        for scenario in ('S2', 'S5'):
            episode, pipeline = result_lookup[(scenario, 42)]
            evaluations = next(
                item for item in evaluated['scenario_runs']
                if item['scenario_id'] == scenario and item['seed'] == 42)['events']
            rows = []
            baseline_version = None
            for result, evaluated_event in zip(episode.pipeline_results, evaluations):
                decision = result.adaptation_decision
                if decision.status.value == 'APPLIED':
                    baseline_version = 1 if baseline_version is None else baseline_version + 1
                rows.append({
                    'event': result.sequence_number,
                    'event_reference': result.event_reference,
                    'mode': result.observable_input['contextual_features'].get('operating_mode'),
                    'value': result.observable_input['requested_value'],
                    'action': result.proposed_decision.selected_action.value,
                    'governance': result.governance_decision.status.value,
                    'execution': result.execution_result.execution_status.value,
                    'trust': result.trust_assessment.composite_trust,
                    'risk': result.risk_assessment.risk_score,
                    'drift': result.drift_assessment.status.value,
                    'adaptation': decision.status.value,
                    'reference_version': baseline_version,
                    'adapted_reference_used': result.behavioral_reference_used is not None,
                    'exact_agreement': evaluated_event['exact_agreement'],
                    'unsafe_action': evaluated_event['unsafe_action'],
                })
            detail[(configuration.value, scenario)] = rows

    static_seed = configuration_results['TAIOS_STATIC']['per_seed_metrics']
    paired = {}
    for name, result in configuration_results.items():
        paired[name] = {
            seed: {metric: result['per_seed_metrics'][seed][metric] - static_seed[seed][metric]
                   for metric in PRIMARY}
            for seed in sorted(static_seed, key=int)}
    table = []
    for configuration in ExperimentalConfiguration:
        metrics = configuration_results[configuration.value]['aggregate_metrics']
        table.append({
            'configuration': configuration.value,
            'exact_agreement': metrics['exact_action_agreement'],
            'unsafe_action_rate': metrics['unsafe_action_rate'],
            'false_intervention_rate': metrics['false_intervention_rate'],
            'review_burden': metrics['review_burden'],
            'autonomous_execution_rate': metrics['autonomous_execution_rate'],
        })
    return {
        'evaluation_version': 'milestone8a-baseline-framework-v1',
        'formal_evaluator_version': EVALUATION_VERSION,
        'matrix': {'configurations': 4, 'scenarios': 6, 'seeds': 5,
                   'episodes': 120, 'events_per_episode': events_per_run,
                   'event_level_evaluations': 1200,
                   'replication_unit': 'seed'},
        'configuration_results': configuration_results,
        'comparison_table': table,
        'paired_seed_differences_from_taios_static': paired,
        'episode_summaries': episode_summaries,
        'event_level_references': raw_references,
        's2_detailed_comparison_seed42': {
            name: detail[(name, 'S2')] for name in configuration_results},
        's5_static_adaptive_comparison_seed42': {
            name: detail[(name, 'S5')]
            for name in ('TAIOS_STATIC', 'TAIOS_ADAPTIVE')},
        'fairness_controls': [
            'The same generated event objects and order are reused across configurations.',
            'Every episode starts with fresh pipeline, industrial, memory, and execution state.',
            'The frozen formal evaluator and annotations are shared across configurations.',
            'Evaluator labels are joined only after inference completes.',
        ],
        'limitations': [
            'Five seeds provide exploratory intervals only.',
            'Events are not statistically independent replication units.',
            'The rule baseline is deliberately minimal and was not tuned against labels.',
            'Fixed trust is an ablation, not a calibrated alternative trust model.',
            'Behavioral adaptation does not currently influence action policy.',
            'S3 register semantics and S6 coordinated-cause attribution remain unresolved.',
            'No significance test or domain-reviewed utility model is included.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', type=int, default=10)
    parser.add_argument('--output', type=Path,
                        default=Path('results/milestone8a-baseline-framework.json'))
    args = parser.parse_args()
    result = evaluate(args.events)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(f'Evaluated 120 episodes / 1200 events; saved {args.output}')


if __name__ == '__main__':
    main()
