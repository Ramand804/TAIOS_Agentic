"""Deterministic diagnostics for Milestone-6D cross-entity correlation evidence."""
import argparse
import json
from collections import Counter
from pathlib import Path

from core.experiment import fingerprint
from core.taios_pipeline import TAIOSPipeline
from environment.event_generator import EventGenerator
from evaluation.formal_evaluator import TAIOSEvaluator
from evaluation.run_formal_evaluation import SCENARIOS, SEEDS
from intelligence.correlation_evidence_model import CORRELATION_MODEL_VERSION


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


def _export_counter(counter):
    return dict(sorted(counter.items()))


def evaluate(events_per_run=10):
    statuses, categories = Counter(), Counter()
    participants, supporting_counts = Counter(), Counter()
    scenarios = {}
    proposals, governance, execution = Counter(), Counter(), Counter()
    completed, all_risks = [], []
    s6_seed42 = []
    configuration_fingerprint = None

    for scenario in SCENARIOS:
        scenario_statuses, scenario_categories = Counter(), Counter()
        for seed in SEEDS:
            generator = EventGenerator(seed, observable_state=True)
            experiment = generator.create_run(scenario, events_per_run)
            events = generator.generate(scenario, events_per_run, experiment)
            episode = TAIOSPipeline().run_episode(
                events, scenario_reference=experiment.experiment_id, seed=seed)
            completed.append((episode, events))
            for result in episode.pipeline_results:
                assessment = result.correlation_assessment
                threat = result.threat_assessment
                configuration_fingerprint = assessment.configuration_fingerprint
                statuses[assessment.status.value] += 1
                scenario_statuses[assessment.status.value] += 1
                categories.update(item.category for item in assessment.evidence)
                scenario_categories.update(item.category for item in assessment.evidence)
                participants[len(assessment.participating_entities)] += 1
                supporting_counts[len(assessment.supporting_event_references)] += 1
                proposals[result.proposed_decision.selected_action.value] += 1
                governance[result.governance_decision.status.value] += 1
                execution[result.execution_result.execution_status.value] += 1
                all_risks.append(result.risk_assessment.to_dict())
                if scenario == 'S6' and seed == 42:
                    observation = result.observable_input
                    s6_seed42.append({
                        'sequence_number': result.sequence_number,
                        'source_id': observation['source_id'],
                        'target_id': observation['target_id'],
                        'identity_id': observation['identity_id'],
                        'local_threat_status': threat.status.value,
                        'local_evidence_categories': [item.evidence_type for item in threat.evidence],
                        'correlation_status': assessment.status.value,
                        'correlation_evidence_categories': [item.category for item in assessment.evidence],
                        'participating_entities': list(assessment.participating_entities),
                        'supporting_prior_event_references': list(
                            assessment.supporting_event_references),
                        'coordination_signal_score': assessment.coordination_signal_score,
                        'evidence_coverage': assessment.evidence_coverage,
                        'history_version': assessment.history_version,
                    })
        scenarios[scenario] = {
            'events': sum(scenario_statuses.values()),
            'statuses': _export_counter(scenario_statuses),
            'category_counts': _export_counter(scenario_categories),
            'direct_correlation_events': scenario_statuses['DIRECT_EVIDENCE'],
            'uncertainty_events': scenario_statuses['UNCERTAINTY_ONLY'],
            'no_correlation_events': scenario_statuses['NO_CORRELATION_EVIDENCE'],
        }

    total = sum(statuses.values())
    structure = {
        'proposals': _export_counter(proposals),
        'governance_statuses': _export_counter(governance),
        'execution_statuses': _export_counter(execution),
    }
    formal = TAIOSEvaluator().evaluate_experiment(completed).to_dict()['overall_results']
    formal_current = {key: formal[key] for key in BASELINE_FORMAL}
    first_s6 = next((row for row in s6_seed42
                     if row['correlation_status'] != 'NO_CORRELATION_EVIDENCE'), None)
    first_s6_direct = next((row for row in s6_seed42
                            if row['correlation_status'] == 'DIRECT_EVIDENCE'), None)
    return {
        'evaluation_version': 'milestone6d-correlation-evidence-v1',
        'correlation_model_version': CORRELATION_MODEL_VERSION,
        'configuration_fingerprint': configuration_fingerprint,
        'seeds': list(SEEDS), 'scenarios': list(SCENARIOS),
        'events_per_run': events_per_run, 'total_events': total,
        'score_semantics': ('coordination_signal_score is uncalibrated evidence severity, not '
                            'probability of coordination, compromise, or attack.'),
        'coverage': {
            'direct_correlation_events': statuses['DIRECT_EVIDENCE'],
            'direct_correlation_rate': statuses['DIRECT_EVIDENCE'] / total,
            'correlation_uncertainty_events': statuses['UNCERTAINTY_ONLY'],
            'correlation_uncertainty_rate': statuses['UNCERTAINTY_ONLY'] / total,
            'no_correlation_evidence_events': statuses['NO_CORRELATION_EVIDENCE'],
            'no_correlation_evidence_rate': statuses['NO_CORRELATION_EVIDENCE'] / total,
            'interpretation': 'Evidence availability only; not attack-detection accuracy.',
        },
        'status_distribution': _export_counter(statuses),
        'category_counts': _export_counter(categories),
        'participating_entity_count_distribution': {
            str(key): value for key, value in sorted(participants.items())},
        'supporting_event_count_distribution': {
            str(key): value for key, value in sorted(supporting_counts.items())},
        'by_scenario': scenarios,
        'negative_controls': {scenario: scenarios[scenario]
                              for scenario in ('S1', 'S2', 'S3', 'S5')},
        's6_full_trajectory_seed42': s6_seed42,
        's6_first_cross_entity_evidence_seed42': first_s6,
        's6_first_direct_correlation_evidence_seed42': first_s6_direct,
        'risk_regression': {
            'assessment_count': len(all_risks),
            'risk_assessments_fingerprint': fingerprint(all_risks),
            'risk_model_or_weights_modified_by_6d': False,
            'verification': 'Compared separately with unchanged Milestone-6C diagnostic.',
        },
        'structural_replay': {
            'before_milestone6d': BASELINE_STRUCTURE,
            'after_milestone6d': structure,
            'changed': structure != BASELINE_STRUCTURE,
        },
        'post_freeze_formal_evaluation': {
            'before_milestone6d': BASELINE_FORMAL,
            'after_milestone6d': formal_current,
            'changed': formal_current != BASELINE_FORMAL,
            'note': 'Labels were joined only after all inference completed.',
        },
        'limitations': [
            'Positive correlation requires direct local evidence for current and prior entities.',
            'Uncertainty relationships remain uncertainty with signal zero.',
            'The history window is five causal event positions and resets per episode.',
            'Cross-zone inference is deferred because no authoritative zone policy exists.',
            'Correlation is audit-only and is not integrated into risk or action policy.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', type=int, default=10)
    parser.add_argument('--output', type=Path,
                        default=Path('results/milestone6d-correlation-evidence.json'))
    args = parser.parse_args()
    result = evaluate(args.events)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(f'Assessed {result["total_events"]} events; saved {args.output}')


if __name__ == '__main__':
    main()
