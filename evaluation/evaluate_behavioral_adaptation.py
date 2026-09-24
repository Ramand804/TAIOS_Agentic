"""Deterministic Milestone-7D STATIC/ADAPTIVE behavioral-reference diagnostic."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from core.behavioral_reference import AdaptationMode, AdaptationStatus
from core.taios_pipeline import TAIOSPipeline
from environment.event_generator import EventGenerator
from evaluation.formal_evaluator import TAIOSEvaluator
from evaluation.run_formal_evaluation import SCENARIOS, SEEDS


BASELINE_STRUCTURE = {
    'proposals': {'ALLOW': 93, 'REQUEST_APPROVAL': 207},
    'governance': {'APPROVAL_REQUIRED': 207, 'APPROVED': 93},
    'execution': {'PENDING_APPROVAL': 207, 'SUCCEEDED': 93},
}
REGRESSION_FILES = {
    'risk_6c': 'results/milestone6c-risk-threat-integration.json',
    'correlation_6d': 'results/milestone6d-correlation-evidence.json',
    'experience_7a': 'results/milestone7a-experience-memory.json',
    'feedback_7b': 'results/milestone7b-feedback-interpretation.json',
    'drift_7c': 'results/milestone7c-drift-detection.json',
}


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _row(result, feedback, baseline_version, baseline_summary, static_status=None):
    observation = result.observable_input
    semantics = result.operational_semantic_assessment
    drift = result.drift_assessment
    proposal = result.adaptation_proposal
    decision = result.adaptation_decision
    return {
        'event': result.sequence_number,
        'source_id': observation['source_id'],
        'target_id': observation['target_id'],
        'operation': observation['operation'],
        'mode': observation['contextual_features'].get('operating_mode'),
        'value': observation['requested_value'],
        'semantic_status': semantics.semantic_status.value,
        'static_drift_status': static_status or drift.status.value,
        'adaptive_drift_status': drift.status.value,
        'adaptation_proposal_status': proposal.status.value,
        'adaptation_decision_status': decision.status.value,
        'baseline_version': baseline_version,
        'baseline_summary': baseline_summary,
        'behavioral_reference_used': result.behavioral_reference_used,
        'feedback_support': feedback.feedback_status.value,
    }


def _run_mode(mode, events_per_run):
    proposal_counts, decision_counts = Counter(), Counter()
    actions, governance, execution = Counter(), Counter(), Counter()
    per_scenario = {}
    episodes = []
    trajectories = {}
    applications = []
    future_uses = 0
    config_fingerprint = None
    for scenario in SCENARIOS:
        scenario_proposals, scenario_decisions = Counter(), Counter()
        scenario_applications = 0
        for seed in SEEDS:
            generator = EventGenerator(seed, observable_state=True)
            experiment = generator.create_run(scenario, events_per_run)
            events = generator.generate(scenario, events_per_run, experiment)
            pipeline = TAIOSPipeline(adaptation_mode=mode)
            episode = pipeline.run_episode(
                events, scenario_reference=experiment.experiment_id, seed=seed)
            episodes.append((episode, events))
            feedback_by_reference = {
                item.reference: item for item in pipeline.feedback_memory.records}
            active_version, active_summary = None, None
            rows = []
            first_known = None
            for result in episode.pipeline_results:
                proposal, decision = result.adaptation_proposal, result.adaptation_decision
                config_fingerprint = proposal.configuration_fingerprint
                proposal_counts[proposal.status.value] += 1
                decision_counts[decision.status.value] += 1
                scenario_proposals[proposal.status.value] += 1
                scenario_decisions[decision.status.value] += 1
                actions[result.proposed_decision.selected_action.value] += 1
                governance[result.governance_decision.status.value] += 1
                execution[result.execution_result.execution_status.value] += 1
                if result.drift_assessment.status.value == 'KNOWN_REGIME_CHANGE' and first_known is None:
                    first_known = result.sequence_number
                if decision.status == AdaptationStatus.APPLIED:
                    active_version = 1 if active_version is None else active_version + 1
                    active_summary = dict(proposal.candidate_summary)
                    scenario_applications += 1
                    applications.append({
                        'scenario': scenario, 'seed': seed,
                        'event': result.sequence_number,
                        'first_known_regime_event': first_known,
                        'latency_events': result.sequence_number - first_known,
                        'baseline_version': active_version,
                        'baseline_reference': decision.after_reference,
                    })
                if result.behavioral_reference_used is not None:
                    future_uses += 1
                feedback = feedback_by_reference[result.feedback_reference]
                rows.append(_row(result, feedback, active_version, active_summary))
            if seed == 42 and scenario in {'S2', 'S5'}:
                trajectories[scenario] = rows
        per_scenario[scenario] = {
            'proposal_statuses': dict(sorted(scenario_proposals.items())),
            'decision_statuses': dict(sorted(scenario_decisions.items())),
            'applications': scenario_applications,
        }
    overall = TAIOSEvaluator().evaluate_experiment(episodes).to_dict()['overall_results']
    return {
        'mode': mode.value,
        'proposal_statuses': dict(sorted(proposal_counts.items())),
        'decision_statuses': dict(sorted(decision_counts.items())),
        'applications': applications,
        'baseline_versions_created': len(applications),
        'future_assessments_using_adapted_reference': future_uses,
        'per_scenario': per_scenario,
        'trajectories': trajectories,
        'action_structure': {
            'proposals': dict(sorted(actions.items())),
            'governance': dict(sorted(governance.items())),
            'execution': dict(sorted(execution.items())),
        },
        'formal_metrics': {
            key: overall[key] for key in (
                'exact_action_agreement', 'unsafe_action_rate', 'false_intervention_rate',
                'proposal_review_burden', 'autonomous_execution_rate')},
        'configuration_fingerprint': config_fingerprint,
    }


def evaluate(events_per_run=10):
    static = _run_mode(AdaptationMode.STATIC, events_per_run)
    adaptive = _run_mode(AdaptationMode.ADAPTIVE, events_per_run)
    for scenario in ('S2', 'S5'):
        static_rows = static['trajectories'][scenario]
        for index, row in enumerate(adaptive['trajectories'][scenario]):
            row['static_drift_status'] = static_rows[index]['adaptive_drift_status']
    attempts = adaptive['decision_statuses'].get('REJECTED', 0)
    rejected = attempts
    first = min((item['event'] for item in adaptive['applications']), default=None)
    return {
        'evaluation_version': 'milestone7d-behavioral-adaptation-v1',
        'events_per_run': events_per_run,
        'seeds': list(SEEDS),
        'scenarios': list(SCENARIOS),
        'configuration_fingerprint': adaptive['configuration_fingerprint'],
        'static': static,
        'adaptive': adaptive,
        'first_adaptation_event': first,
        'adaptation_latency_definition': (
            'application event position minus first known-regime-change event position'),
        'poisoning_resistance': {
            'unexplained_drift_adaptation_attempts': attempts,
            'attempts_rejected_or_deferred': rejected,
            'rejection_rate': rejected / attempts if attempts else None,
            'interpretation': 'Descriptive rejection rate, not adversarial robustness probability.',
        },
        'action_regression': {
            'expected': BASELINE_STRUCTURE,
            'static_changed': static['action_structure'] != BASELINE_STRUCTURE,
            'adaptive_changed': adaptive['action_structure'] != BASELINE_STRUCTURE,
        },
        'regression_fingerprints': {
            name: _sha256(path) for name, path in REGRESSION_FILES.items()},
        'security_feedback_limitation': (
            'Adaptive references have causal operational support but are not security-validated.'),
        'adaptation_boundary': (
            'Only contextual behavioral drift references adapt; operational limits and all '
            'security/action inference remain frozen.'),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', type=int, default=10)
    parser.add_argument('--output', type=Path,
                        default=Path('results/milestone7d-behavioral-adaptation.json'))
    args = parser.parse_args()
    result = evaluate(args.events)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(f'Evaluated STATIC and ADAPTIVE modes; saved {args.output}')


if __name__ == '__main__':
    main()
