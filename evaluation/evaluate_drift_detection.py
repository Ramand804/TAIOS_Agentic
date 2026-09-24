"""Deterministic diagnostics for Milestone-7C observable drift detection."""
import argparse
import json
from collections import Counter
from pathlib import Path

from core.taios_pipeline import TAIOSPipeline
from environment.event_generator import EventGenerator
from evaluation.formal_evaluator import TAIOSEvaluator
from evaluation.run_formal_evaluation import SCENARIOS, SEEDS
from intelligence.drift_detector import DRIFT_MODEL_VERSION


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
    statuses, categories, scores = Counter(), Counter(), Counter()
    proposals, governance, execution = Counter(), Counter(), Counter()
    scenario_results = {}
    completed = []
    numeric_scopes, unsupported_scopes = set(), set()
    s2_seed42, s3_seed42, s5_seed42, s6_seed42 = [], [], [], []
    configuration_fingerprint = None

    for scenario in SCENARIOS:
        scenario_statuses, scenario_categories = Counter(), Counter()
        scenario_scores = []
        for seed in SEEDS:
            generator = EventGenerator(seed, observable_state=True)
            experiment = generator.create_run(scenario, events_per_run)
            events = generator.generate(scenario, events_per_run, experiment)
            episode = TAIOSPipeline().run_episode(
                events, scenario_reference=experiment.experiment_id, seed=seed)
            completed.append((episode, events))
            for result in episode.pipeline_results:
                drift = result.drift_assessment
                semantics = result.operational_semantic_assessment
                observation = result.observable_input
                configuration_fingerprint = drift.configuration_fingerprint
                statuses[drift.status.value] += 1
                scenario_statuses[drift.status.value] += 1
                categories.update(item.category for item in drift.evidence)
                scenario_categories.update(item.category for item in drift.evidence)
                scores[f'{drift.change_score:.12g}'] += 1
                scenario_scores.append(drift.change_score)
                if drift.status.value == 'INSUFFICIENT_SEMANTIC_SCOPE':
                    unsupported_scopes.add(drift.scope)
                else:
                    numeric_scopes.add(drift.scope)
                proposals[result.proposed_decision.selected_action.value] += 1
                governance[result.governance_decision.status.value] += 1
                execution[result.execution_result.execution_status.value] += 1
                row = {
                    'sequence_number': result.sequence_number,
                    'source_id': observation['source_id'],
                    'target_id': observation['target_id'],
                    'operation': observation['operation'],
                    'requested_value': observation['requested_value'],
                    'operating_mode': observation['contextual_features'].get('operating_mode'),
                    'production_state': observation['contextual_features'].get('production_state'),
                    'semantic_status': semantics.semantic_status.value,
                    'local_threat_status': result.threat_assessment.status.value,
                    'drift_status': drift.status.value,
                    'change_score': drift.change_score,
                    'persistence_count': drift.persistence_count,
                    'history_count': drift.history_count,
                    'context_explanation': drift.context_explanation,
                    'evidence_categories': [item.category for item in drift.evidence],
                    'drift_reference': drift.reference,
                }
                if seed == 42:
                    {'S2': s2_seed42, 'S3': s3_seed42,
                     'S5': s5_seed42, 'S6': s6_seed42}.get(scenario, []).append(row)
        scenario_results[scenario] = {
            'events': sum(scenario_statuses.values()),
            'statuses': dict(sorted(scenario_statuses.items())),
            'evidence_categories': dict(sorted(scenario_categories.items())),
            'change_score': {
                'minimum': min(scenario_scores),
                'mean': sum(scenario_scores) / len(scenario_scores),
                'maximum': max(scenario_scores),
            },
        }

    total = sum(statuses.values())
    structure = {
        'proposals': dict(sorted(proposals.items())),
        'governance_statuses': dict(sorted(governance.items())),
        'execution_statuses': dict(sorted(execution.items())),
    }
    formal = TAIOSEvaluator().evaluate_experiment(completed).to_dict()['overall_results']
    formal_current = {key: formal[key] for key in BASELINE_FORMAL}
    return {
        'evaluation_version': 'milestone7c-drift-detection-v1',
        'drift_model_version': DRIFT_MODEL_VERSION,
        'configuration_fingerprint': configuration_fingerprint,
        'seeds': list(SEEDS), 'scenarios': list(SCENARIOS),
        'events_per_run': events_per_run, 'total_events': total,
        'status_distribution': dict(sorted(statuses.items())),
        'evidence_category_counts': dict(sorted(categories.items())),
        'change_score_distribution': dict(
            sorted(scores.items(), key=lambda item: float(item[0]))),
        'history_coverage': {
            'numeric_scopes_assessed': len(numeric_scopes),
            'unsupported_or_underspecified_scopes': len(unsupported_scopes),
            'insufficient_history_events': statuses['INSUFFICIENT_HISTORY'],
            'insufficient_semantic_scope_events': statuses['INSUFFICIENT_SEMANTIC_SCOPE'],
            'context_explained_events': statuses['KNOWN_REGIME_CHANGE'],
            'unexplained_persistent_events': statuses['UNEXPLAINED_PERSISTENT_DRIFT'],
        },
        'by_scenario': scenario_results,
        's2_full_trajectory_seed42': s2_seed42,
        's3_semantic_limitation_seed42': s3_seed42,
        's5_full_transition_trajectory_seed42': s5_seed42,
        's6_local_only_seed42': s6_seed42,
        'regressions': {
            'risk': {'changed': False, 'verification': 'Unchanged 6C diagnostic compared separately.'},
            'correlation': {'changed': False, 'verification': 'Unchanged 6D diagnostic compared separately.'},
            'experience': {'changed': False, 'verification': 'Unchanged 7A diagnostic compared separately.'},
            'feedback': {'changed': False, 'verification': 'Unchanged 7B diagnostic compared separately.'},
        },
        'structural_replay': {
            'before_milestone7c': BASELINE_STRUCTURE,
            'after_milestone7c': structure,
            'changed': structure != BASELINE_STRUCTURE,
        },
        'post_freeze_formal_evaluation': {
            'before_milestone7c': BASELINE_FORMAL,
            'after_milestone7c': formal_current,
            'changed': formal_current != BASELINE_FORMAL,
            'note': 'Evaluator labels were joined only after drift detection and inference completed.',
        },
        'score_semantics': ('change_score is deterministic normalized magnitude, not probability '
                            'of drift, regime change, malicious behavior, or attack.'),
        'limitations': [
            'Ten-event episodes support only a simple proof-of-concept detector.',
            'The first three comparable observations form a fixed provisional reference window.',
            'write_register lacks register identity and is not numerically compared.',
            'Known context explains change only when current-mode semantics are valid.',
            'Drift is audit-only and does not trigger adaptation or action.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', type=int, default=10)
    parser.add_argument('--output', type=Path,
                        default=Path('results/milestone7c-drift-detection.json'))
    args = parser.parse_args()
    result = evaluate(args.events)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(f'Assessed {result["total_events"]} events; saved {args.output}')


if __name__ == '__main__':
    main()
