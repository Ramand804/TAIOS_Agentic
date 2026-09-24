"""Structural, label-free diagnostics for Milestone-6B threat evidence."""
import argparse
import json
from collections import Counter
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
    'exact_action_agreement': 143 / 300, 'unsafe_action_rate': 0.0,
    'false_intervention_rate': 72 / 165, 'proposal_review_burden': 207 / 300,
    'autonomous_execution_rate': 93 / 300,
}


def _group_increment(groups, key, assessment):
    group = groups.setdefault(key, {'events': 0, 'statuses': Counter(), 'categories': Counter()})
    group['events'] += 1
    group['statuses'][assessment.status.value] += 1
    group['categories'].update(item.evidence_type for item in assessment.evidence)


def _export_groups(groups):
    return {key: {'events': value['events'],
                  'statuses': dict(sorted(value['statuses'].items())),
                  'categories': dict(sorted(value['categories'].items()))}
            for key, value in sorted(groups.items())}


def evaluate(events_per_run=10):
    statuses, categories, scores = Counter(), Counter(), Counter()
    scenarios, operations, source_types = {}, {}, {}
    proposals, governance, execution = Counter(), Counter(), Counter()
    completed, s2, s3, s4, s5, s6 = [], [], [], [], [], []
    configuration_fingerprint = None
    for scenario in SCENARIOS:
        for seed in SEEDS:
            generator = EventGenerator(seed, observable_state=True)
            experiment = generator.create_run(scenario, events_per_run)
            events = generator.generate(scenario, events_per_run, experiment)
            episode = TAIOSPipeline().run_episode(
                events, scenario_reference=experiment.experiment_id, seed=seed)
            completed.append((episode, events))
            for result in episode.pipeline_results:
                threat = result.threat_assessment
                configuration_fingerprint = threat.configuration_fingerprint
                statuses[threat.status.value] += 1
                categories.update(item.evidence_type for item in threat.evidence)
                scores[f'{threat.security_signal_score:.12g}'] += 1
                observation = result.observable_input
                _group_increment(scenarios, scenario, threat)
                _group_increment(operations, observation['operation'], threat)
                _group_increment(source_types, observation['source_type'], threat)
                proposals[result.proposed_decision.selected_action.value] += 1
                governance[result.governance_decision.status.value] += 1
                execution[result.execution_result.execution_status.value] += 1
                row = {
                    'seed': seed, 'sequence_number': result.sequence_number,
                    'source_id': observation['source_id'],
                    'operation': observation['operation'],
                    'requested_value': observation['requested_value'],
                    'operating_mode': result.state_before.operating_mode.value,
                    'semantic_status': result.operational_semantic_assessment.semantic_status.value,
                    'authorization_status': result.authorization_assessment.status.value,
                    'trust': result.trust_assessment.composite_trust,
                    'status': threat.status.value,
                    'security_signal_score': threat.security_signal_score,
                    'evidence_categories': [item.evidence_type for item in threat.evidence],
                    'prior_operational_violation_count': threat.prior_operational_violation_count,
                    'evidence_coverage': threat.evidence_coverage,
                }
                if seed == 42:
                    {'S2': s2, 'S3': s3, 'S4': s4, 'S5': s5, 'S6': s6}.get(
                        scenario, []).append(row)
    total = sum(statuses.values())
    direct = statuses['DIRECT_EVIDENCE']
    uncertainty = statuses['UNCERTAINTY_ONLY']
    current_structure = {
        'proposals': dict(sorted(proposals.items())),
        'governance_statuses': dict(sorted(governance.items())),
        'execution_statuses': dict(sorted(execution.items())),
    }
    formal = TAIOSEvaluator().evaluate_experiment(completed).to_dict()['overall_results']
    current_formal = {key: formal[key] for key in BASELINE_FORMAL}
    return {
        'threat_model_version': 'milestone6b-threat-evidence-v1',
        'configuration_fingerprint': configuration_fingerprint,
        'seeds': list(SEEDS), 'scenarios': list(SCENARIOS),
        'events_per_run': events_per_run, 'total_events': total,
        'assessment_status_distribution': dict(sorted(statuses.items())),
        'evidence_category_counts': dict(sorted(categories.items())),
        'security_signal_distribution': dict(sorted(scores.items(), key=lambda item: float(item[0]))),
        'coverage': {
            'direct_security_evidence_events': direct,
            'direct_security_evidence_rate': direct / total if total else None,
            'uncertainty_only_events': uncertainty,
            'uncertainty_only_rate': uncertainty / total if total else None,
            'no_security_evidence_events': statuses['NO_SECURITY_EVIDENCE'],
            'no_security_evidence_rate': statuses['NO_SECURITY_EVIDENCE'] / total if total else None,
            'interpretation': 'Evidence coverage only; not attack-detection accuracy.',
        },
        'by_scenario': _export_groups(scenarios),
        'by_operation': _export_groups(operations),
        'by_source_type': _export_groups(source_types),
        's2_temporal_trajectory_seed42': s2,
        's3_uncertainty_seed42': s3,
        's4_evidence_decomposition_seed42': s4,
        's5_regression_seed42': s5,
        's6_local_only_seed42': s6,
        'coordination_capability': 'NOT_IMPLEMENTED',
        'structural_replay': {
            'before_milestone6b': BASELINE_STRUCTURE,
            'after_milestone6b': current_structure,
            'changed': current_structure != BASELINE_STRUCTURE,
        },
        'post_freeze_formal_evaluation': {
            'before_milestone6b': BASELINE_FORMAL,
            'after_milestone6b': current_formal,
            'changed': current_formal != BASELINE_FORMAL,
            'note': 'Labels were joined only after threat evidence implementation was frozen.',
        },
        'score_semantics': ('security_signal_score is an uncalibrated maximum effective direct '
                            'evidence strength, not attack probability.'),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', type=int, default=10)
    parser.add_argument('--output', type=Path,
                        default=Path('results/milestone6b-threat-evidence.json'))
    args = parser.parse_args()
    result = evaluate(args.events)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(f'Assessed {result["total_events"]} events; saved {args.output}')


if __name__ == '__main__':
    main()
