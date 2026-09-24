"""Deterministic, label-separated diagnostics for Milestone-6C risk integration."""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from agents.risk_agent import RiskAgent
from core.experiment import fingerprint
from core.risk_input import RiskConfig
from core.runtime_inputs import runtime_observation
from core.taios_pipeline import TAIOSPipeline
from environment.event_generator import EventGenerator
from evaluation.formal_evaluator import TAIOSEvaluator
from evaluation.run_formal_evaluation import SCENARIOS, SEEDS
from intelligence.risk_model import THREAT_INTEGRATION_MODEL_VERSION


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


def _summary(rows):
    old = [row['old_risk'] for row in rows]
    new = [row['new_risk'] for row in rows]
    delta = [row['risk_delta'] for row in rows]
    return {
        'events': len(rows),
        'old_risk': {'minimum': min(old), 'mean': sum(old) / len(old), 'maximum': max(old)},
        'new_risk': {'minimum': min(new), 'mean': sum(new) / len(new), 'maximum': max(new)},
        'risk_delta': {'minimum': min(delta), 'mean': sum(delta) / len(delta),
                       'maximum': max(delta)},
    }


def _group_summaries(groups):
    return {key: _summary(value) for key, value in sorted(groups.items())}


def evaluate(events_per_run=10):
    rows = []
    completed = []
    grouped = {name: defaultdict(list) for name in
               ('scenario', 'threat_status', 'semantic_status', 'ground_truth')}
    availability_reasons = Counter()
    coverage = Counter()
    proposals, governance, execution = Counter(), Counter(), Counter()
    trajectories = {f'S{i}': [] for i in range(1, 7)}
    risk_config = RiskConfig.load()

    for scenario in SCENARIOS:
        for seed in SEEDS:
            generator = EventGenerator(seed, observable_state=True)
            experiment = generator.create_run(scenario, events_per_run)
            events = generator.generate(scenario, events_per_run, experiment)
            episode = TAIOSPipeline().run_episode(
                events, scenario_reference=experiment.experiment_id, seed=seed)
            completed.append((episode, events))
            for result, event in zip(episode.pipeline_results, events):
                integrated = result.risk_assessment
                old = RiskAgent(config=risk_config).assess(
                    runtime_observation(event), result.trust_assessment,
                    expected_trust_state_version=result.trust_assessment.trust_state_version)
                threat = result.threat_assessment
                row = {
                    'scenario_id': scenario, 'seed': seed,
                    'sequence_number': result.sequence_number,
                    'event_id': result.event_id,
                    'trust': result.trust_assessment.composite_trust,
                    'distrust': integrated.distrust_score,
                    'criticality': integrated.criticality_score,
                    'threat_status': threat.status.value,
                    'threat_signal': threat.security_signal_score,
                    'threat_available': integrated.threat_available,
                    'threat_unavailable_reason': integrated.threat_unavailable_reason,
                    'threat_evidence_coverage': threat.evidence_coverage,
                    'risk_coverage': integrated.coverage,
                    'old_risk': old.risk_score,
                    'new_risk': integrated.risk_score,
                    'risk_delta': integrated.risk_score - old.risk_score,
                    'component_values': {
                        'THREAT': integrated.threat_signal,
                        'TRUST': integrated.distrust_score,
                        'CRITICALITY': integrated.criticality_score,
                        'ANOMALY': integrated.anomaly_score,
                    },
                    'component_availability': dict(integrated.component_availability),
                    'effective_weights': dict(integrated.effective_weights),
                    'semantic_status': result.operational_semantic_assessment.semantic_status.value,
                    'proposal': result.proposed_decision.selected_action.value,
                    'governance': result.governance_decision.status.value,
                    'execution': result.execution_result.execution_status.value,
                    # Joined only after inference has completed.
                    'ground_truth': event.ground_truth,
                }
                rows.append(row)
                grouped['scenario'][scenario].append(row)
                grouped['threat_status'][row['threat_status']].append(row)
                grouped['semantic_status'][row['semantic_status']].append(row)
                grouped['ground_truth'][row['ground_truth']].append(row)
                coverage[f'{integrated.coverage:.12g}'] += 1
                if not integrated.threat_available:
                    availability_reasons[integrated.threat_unavailable_reason] += 1
                proposals[row['proposal']] += 1
                governance[row['governance']] += 1
                execution[row['execution']] += 1
                if seed == 42:
                    trajectories[scenario].append(row)

    total = len(rows)
    available = sum(row['threat_available'] for row in rows)
    structure = {
        'proposals': dict(sorted(proposals.items())),
        'governance_statuses': dict(sorted(governance.items())),
        'execution_statuses': dict(sorted(execution.items())),
    }
    formal = TAIOSEvaluator().evaluate_experiment(completed).to_dict()['overall_results']
    formal_current = {key: formal[key] for key in BASELINE_FORMAL}
    configuration = {
        'risk_configuration_fingerprint': risk_config.fingerprint,
        'risk_model_version': THREAT_INTEGRATION_MODEL_VERSION,
        'threat_availability_policy': {
            'DIRECT_EVIDENCE': 'AVAILABLE_EXACT_SECURITY_SIGNAL',
            'UNCERTAINTY_ONLY': 'UNAVAILABLE',
            'NO_SECURITY_EVIDENCE': 'AVAILABLE_ZERO_ONLY_WHEN_EVIDENCE_COVERAGE_IS_COMPLETE',
        },
        'anomaly_policy': 'UNCHANGED_UNAVAILABLE',
    }
    return {
        'evaluation_version': 'milestone6c-risk-threat-integration-v1',
        'configuration': configuration,
        'configuration_fingerprint': fingerprint(configuration),
        'seeds': list(SEEDS), 'scenarios': list(SCENARIOS),
        'events_per_run': events_per_run, 'total_events': total,
        'score_semantics': ('security_signal_score is direct evidence severity, not calibrated '
                            'attack probability.'),
        'availability': {
            'threat_available_events': available,
            'threat_available_rate': available / total,
            'threat_unavailable_events': total - available,
            'threat_unavailable_reasons': dict(sorted(availability_reasons.items())),
        },
        'risk_weight_coverage_distribution': dict(
            sorted(coverage.items(), key=lambda item: float(item[0]))),
        'before_after': {
            'overall': _summary(rows),
            'by_scenario': _group_summaries(grouped['scenario']),
            'by_threat_status': _group_summaries(grouped['threat_status']),
            'by_semantic_status': _group_summaries(grouped['semantic_status']),
            'by_ground_truth_post_inference': _group_summaries(grouped['ground_truth']),
        },
        'trajectories_seed42': trajectories,
        's2_trajectory_seed42': trajectories['S2'],
        's3_uncertainty_seed42': trajectories['S3'],
        's4_trajectory_seed42': trajectories['S4'],
        's5_high_output_regression_seed42': trajectories['S5'],
        's6_local_only_seed42': trajectories['S6'],
        'structural_replay': {
            'before_milestone6c': BASELINE_STRUCTURE,
            'after_milestone6c': structure,
            'changed': structure != BASELINE_STRUCTURE,
        },
        'post_freeze_formal_evaluation': {
            'before_milestone6c': BASELINE_FORMAL,
            'after_milestone6c': formal_current,
            'changed': formal_current != BASELINE_FORMAL,
            'note': 'Labels were joined only after all inference completed.',
        },
        'limitations': [
            'Threat and distrust can share operational evidence and are not statistically independent.',
            'Recurrence is consumed only through the frozen maximum-aggregated threat signal.',
            'Anomaly remains unavailable.',
            'Threat evidence is event-local; coordinated risk reasoning is not implemented.',
            'Risk scores are uncalibrated and are not attack probabilities.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', type=int, default=10)
    parser.add_argument('--output', type=Path,
                        default=Path('results/milestone6c-risk-threat-integration.json'))
    args = parser.parse_args()
    result = evaluate(args.events)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(f'Assessed {result["total_events"]} events; saved {args.output}')


if __name__ == '__main__':
    main()
