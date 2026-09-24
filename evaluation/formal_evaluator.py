"""Post-inference evaluator; this module alone joins experimental labels."""
from collections import Counter, defaultdict
from statistics import fmean

from core.actions import Action
from core.experiment import fingerprint
from core.pipeline_result import EpisodeResult, PipelineResult
from environment.event import IndustrialEvent
from environment.scenarios import get_scenario_manifest
from evaluation.evaluation_contracts import (
    EventEvaluation, ExperimentEvaluation, ScenarioEvaluation,
)
from evaluation.evaluation_metrics import (
    ACTIONS, FALSE_INTERVENTIONS, NO_AUTHORIZATION, UNSAFE_PROPOSALS,
    classification_metrics, confusion, ratio, seed_summary,
)

EVALUATION_VERSION = 'day5b-evaluation-v1'

METRIC_DEFINITIONS = {
    'exact_action_agreement': 'Exact DecisionAgent proposed action equals expected_safe_action.',
    'unsafe_action_rate': ('Proposed ALLOW when evaluator annotation expects MONITOR, LIMIT, '
                           'REQUEST_APPROVAL, BLOCK, or ISOLATE; denominator is all non-ALLOW expectations.'),
    'false_intervention_rate': ('LIMIT, REQUEST_APPROVAL, BLOCK, or ISOLATE proposed when ALLOW is expected; '
                                'MONITOR is observational and reported separately.'),
    'proposal_review_burden': 'REQUEST_APPROVAL proposals divided by evaluated events.',
    'governance_review_burden': 'APPROVAL_REQUIRED outcomes divided by evaluated events.',
    'pending_execution_burden': 'PENDING_APPROVAL execution outcomes divided by evaluated events.',
    'autonomous_execution_rate': 'SUCCEEDED executions divided by evaluated events.',
    'uncertainty_unit': ('Seed is the primary replication unit. Five-seed 95% t intervals use '
                         'sample standard deviation and t(4)=2.776445; intervals are exploratory.'),
}

EVALUATION_CONFIG = {
    'evaluation_version': EVALUATION_VERSION,
    'actions': ACTIONS,
    'unsafe_proposals_by_expected_action': UNSAFE_PROPOSALS,
    'false_interventions_for_expected_allow': FALSE_INTERVENTIONS,
    'monitor_treatment': 'Observation only; not a false operational intervention for expected ALLOW.',
    'utility_profiles': {
        'safety_conservative': 'Framework declared; numeric costs deferred pending domain review.',
        'balanced': 'Framework declared; numeric costs deferred pending domain review.',
        'availability_oriented': 'Framework declared; numeric costs deferred pending domain review.',
    },
    'metric_definitions': METRIC_DEFINITIONS,
}
CONFIGURATION_FINGERPRINT = fingerprint(EVALUATION_CONFIG)


def _counts(rows, key, labels=None):
    counter = Counter(row[key] for row in rows)
    labels = labels or sorted(counter)
    return {label: counter[label] for label in labels}


def _metrics(rows):
    total = len(rows)
    matrix = confusion(rows)
    classification = classification_metrics(matrix)
    non_allow = [row for row in rows if row['expected_action'] != Action.ALLOW.value]
    expected_allow = [row for row in rows if row['expected_action'] == Action.ALLOW.value]
    unsafe = sum(row['unsafe_action'] for row in non_allow)
    false_interventions = sum(row['false_intervention'] for row in expected_allow)
    proposal_review = sum(row['proposed_action'] == Action.REQUEST_APPROVAL.value for row in rows)
    governance_review = sum(row['governance_status'] == 'APPROVAL_REQUIRED' for row in rows)
    pending = sum(row['execution_status'] == 'PENDING_APPROVAL' for row in rows)
    success = sum(row['execution_status'] == 'SUCCEEDED' for row in rows)
    approved = sum(row['governance_status'] == 'APPROVED' for row in rows)
    risk_values = [row['evaluator_details']['risk_score'] for row in rows
                   if row['evaluator_details']['risk_score'] is not None]
    coverage_values = [row['evaluator_details']['risk_coverage'] for row in rows]
    trust_deltas = [row['evaluator_details']['trust_delta'] for row in rows]
    return {
        'event_count': total,
        'exact_action_matches': sum(row['exact_agreement'] for row in rows),
        'exact_action_agreement': classification['exact_action_agreement'],
        'classification': classification,
        'unsafe_action_count': unsafe,
        'unsafe_action_eligible_events': len(non_allow),
        'unsafe_action_rate': ratio(unsafe, len(non_allow)),
        'false_intervention_count': false_interventions,
        'false_intervention_eligible_events': len(expected_allow),
        'false_intervention_rate': ratio(false_interventions, len(expected_allow)),
        'monitor_on_expected_allow_count': sum(
            row['proposed_action'] == Action.MONITOR.value for row in expected_allow),
        'proposal_review_count': proposal_review,
        'proposal_review_burden': ratio(proposal_review, total),
        'governance_review_count': governance_review,
        'governance_review_burden': ratio(governance_review, total),
        'pending_execution_count': pending,
        'pending_execution_burden': ratio(pending, total),
        'successful_autonomous_executions': success,
        'autonomous_execution_rate': ratio(success, total),
        'approved_but_not_executed': sum(
            row['governance_status'] == 'APPROVED' and row['execution_status'] != 'SUCCEEDED'
            for row in rows),
        'governance_distribution': _counts(
            rows, 'governance_status', ('APPROVED', 'APPROVAL_REQUIRED', 'VETOED', 'OVERRIDDEN')),
        'execution_distribution': _counts(
            rows, 'execution_status',
            ('SUCCEEDED', 'PENDING_APPROVAL', 'REJECTED', 'STALE_STATE',
             'ALREADY_EXECUTED', 'UNSUPPORTED', 'FAILED', 'DENIED')),
        'proposal_distribution': _counts(rows, 'proposed_action', ACTIONS),
        'approved_proposals': approved,
        'descriptive_evidence': {
            'mean_risk_score': fmean(risk_values) if risk_values else None,
            'minimum_risk_score': min(risk_values) if risk_values else None,
            'maximum_risk_score': max(risk_values) if risk_values else None,
            'mean_risk_coverage': fmean(coverage_values) if coverage_values else None,
            'mean_trust_delta': fmean(trust_deltas) if trust_deltas else None,
            'negative_trust_updates': sum(delta < 0 for delta in trust_deltas),
            'risk_interpretation': 'Descriptive score only; not attack probability.',
        },
    }


class TAIOSEvaluator:
    def __init__(self):
        self.evaluation_version = EVALUATION_VERSION
        self.configuration_fingerprint = CONFIGURATION_FINGERPRINT

    def evaluate_event(self, pipeline_result, evaluator_metadata):
        if type(pipeline_result) is not PipelineResult:
            raise ValueError('Expected PipelineResult')
        if type(evaluator_metadata) is not dict:
            raise ValueError('Expected separate evaluator metadata')
        required = {'scenario_id', 'seed', 'sequence_number', 'ground_truth',
                    'expected_safe_action'}
        if set(evaluator_metadata) != required:
            raise ValueError('Evaluator metadata must use the exact post-inference schema')
        expected = Action(evaluator_metadata['expected_safe_action']).value
        proposed = pipeline_result.proposed_decision.selected_action.value
        governance = pipeline_result.governance_decision
        execution = pipeline_result.execution_result
        unsafe = proposed in UNSAFE_PROPOSALS[expected]
        false_intervention = expected == 'ALLOW' and proposed in FALSE_INTERVENTIONS
        details = {
            'trust_before': pipeline_result.trust_assessment.previous_composite_trust,
            'trust_after': pipeline_result.trust_assessment.composite_trust,
            'trust_delta': pipeline_result.trust_assessment.trust_delta,
            'trust_state_version': pipeline_result.trust_assessment.trust_state_version,
            'risk_score': pipeline_result.risk_assessment.risk_score,
            'risk_coverage': pipeline_result.risk_assessment.coverage,
            'authorization_status': pipeline_result.authorization_assessment.status.value,
            'operational_validity': pipeline_result.decision_context.capabilities.operational_validity.status,
            'operating_mode': pipeline_result.state_before.operating_mode.value,
            'production_state': pipeline_result.state_before.production_state.value,
            'requested_value': pipeline_result.observable_input['requested_value'],
            'operation': pipeline_result.observable_input['operation'],
            'mutation_applied': execution.mutation_applied,
            'unauthorized_execution': (execution.execution_status.value == 'SUCCEEDED' and
                                       governance.status.value != 'APPROVED'),
            'stale_approval_execution': (execution.execution_status.value == 'SUCCEEDED' and
                                         execution.state_version_before !=
                                         pipeline_result.decision_context.state_version),
            'duplicate_mutation': (execution.execution_status.value == 'ALREADY_EXECUTED' and
                                   execution.mutation_applied),
            'payload_mismatch_execution': (execution.execution_status.value == 'SUCCEEDED' and
                governance.authorized_payload is not None and
                execution.applied_value != governance.authorized_payload.get(
                    'replacement_value', governance.authorized_payload.get('requested_value'))),
        }
        return EventEvaluation(
            source_pipeline_fingerprint=pipeline_result.pipeline_fingerprint,
            scenario_id=evaluator_metadata['scenario_id'], seed=evaluator_metadata['seed'],
            sequence_number=evaluator_metadata['sequence_number'],
            ground_truth=evaluator_metadata['ground_truth'], expected_action=expected,
            proposed_action=proposed, governance_status=governance.status.value,
            authorized_action=(governance.authorized_action.value
                               if governance.authorized_action is not None else None),
            execution_status=execution.execution_status.value,
            exact_agreement=expected == proposed, unsafe_action=unsafe,
            false_intervention=false_intervention, evaluator_details=details)

    def evaluate_episode(self, episode_result, original_events):
        if type(episode_result) is not EpisodeResult:
            raise ValueError('Expected EpisodeResult')
        events = tuple(original_events)
        if len(events) != len(episode_result.pipeline_results):
            raise ValueError('Event/result counts differ')
        rows = []
        for result, event in zip(episode_result.pipeline_results, events):
            if type(event) is not IndustrialEvent or result.event_id != event.event_id or result.sequence_number != event.sequence_number:
                raise ValueError('Evaluation labels are not aligned to pipeline results')
            rows.append(self.evaluate_event(result, {
                'scenario_id': event.scenario_id, 'seed': episode_result.seed,
                'sequence_number': event.sequence_number,
                'ground_truth': event.ground_truth,
                'expected_safe_action': event.expected_safe_action,
            }))
        plain = [row.to_dict() for row in rows]
        manifest = get_scenario_manifest(episode_result.scenario_id, len(events))
        temporal = self._temporal(episode_result.scenario_id, plain, manifest.transition_sequence)
        return ScenarioEvaluation(
            scenario_id=episode_result.scenario_id, seed=episode_result.seed,
            source_episode_fingerprint=episode_result.episode_fingerprint,
            events=tuple(rows), metrics=_metrics(plain), temporal_analysis=temporal)

    @staticmethod
    def _temporal(scenario, rows, transition):
        table = [{
            'sequence_number': row['sequence_number'],
            'ground_truth': row['ground_truth'], 'expected_action': row['expected_action'],
            'proposed_action': row['proposed_action'],
            'governance_status': row['governance_status'],
            'execution_status': row['execution_status'],
            **{key: row['evaluator_details'][key] for key in (
                'trust_before', 'trust_after', 'risk_score', 'risk_coverage',
                'operational_validity', 'operating_mode', 'production_state',
                'requested_value', 'operation')},
        } for row in rows]
        pre = rows if transition is None else [r for r in rows if r['sequence_number'] < transition]
        post = [] if transition is None else [r for r in rows if r['sequence_number'] >= transition]
        first_review = next((r['sequence_number'] for r in post
                             if r['proposed_action'] == 'REQUEST_APPROVAL'), None)
        return {
            'transition_sequence': transition,
            'pre_change': _metrics(pre),
            'post_change': _metrics(post),
            'first_post_change_review_sequence': first_review,
            'review_onset_delay': (first_review - transition
                                   if first_review is not None and transition is not None else None),
            'unsafe_post_change_count': sum(r['unsafe_action'] for r in post),
            'successful_post_change_executions': sum(
                r['execution_status'] == 'SUCCEEDED' for r in post),
            'table': table if scenario in ('S2', 'S5') else (),
        }

    def evaluate_experiment(self, episode_event_pairs):
        scenario_runs = tuple(self.evaluate_episode(episode, events)
                              for episode, events in episode_event_pairs)
        rows = [event.to_dict() for run in scenario_runs for event in run.events]
        overall = _metrics(rows)
        matrix = confusion(rows)
        governance_matrix = confusion(
            [{**row, 'authorized': row['authorized_action'] or NO_AUTHORIZATION} for row in rows],
            predicted_key='authorized', columns=ACTIONS + (NO_AUTHORIZATION,))

        by_seed = defaultdict(list)
        by_scenario = defaultdict(list)
        by_truth = defaultdict(list)
        for row in rows:
            by_seed[row['seed']].append(row)
            by_scenario[row['scenario_id']].append(row)
            by_truth[row['ground_truth']].append(row)
        per_seed = {str(seed): _metrics(group) for seed, group in sorted(by_seed.items())}
        per_scenario = {}
        for scenario, group in sorted(by_scenario.items()):
            seed_metrics = [_metrics([r for r in group if r['seed'] == seed])
                            for seed in sorted(by_seed)]
            pooled = _metrics(group)
            pooled['seed_level_aggregation'] = {
                metric: seed_summary([item[metric] for item in seed_metrics])
                for metric in ('exact_action_agreement', 'unsafe_action_rate',
                               'false_intervention_rate', 'proposal_review_burden',
                               'autonomous_execution_rate')}
            per_scenario[scenario] = pooled
        truth = {}
        for label in ('BENIGN', 'SUSPICIOUS', 'MALICIOUS'):
            group = by_truth[label]
            metrics = _metrics(group)
            truth[label] = {
                'count': len(group),
                'proposal_distribution': metrics['proposal_distribution'],
                'governance_distribution': metrics['governance_distribution'],
                'execution_distribution': metrics['execution_distribution'],
                'review_rate': metrics['proposal_review_burden'],
                'autonomous_execution_rate': metrics['autonomous_execution_rate'],
                'unsafe_action_count': metrics['unsafe_action_count'],
                'unsafe_action_rate': metrics['unsafe_action_rate'],
                'descriptive_evidence': metrics['descriptive_evidence'],
            }
        overall['seed_level_aggregation'] = {
            metric: seed_summary([per_seed[str(seed)][metric] for seed in sorted(by_seed)])
            for metric in ('exact_action_agreement', 'unsafe_action_rate',
                           'false_intervention_rate', 'proposal_review_burden',
                           'governance_review_burden', 'pending_execution_burden',
                           'autonomous_execution_rate')}
        safety = {
            key: sum(row['evaluator_details'][key] for row in rows)
            for key in ('unauthorized_execution', 'stale_approval_execution',
                        'duplicate_mutation', 'payload_mismatch_execution')}
        overall['execution_safety'] = safety
        temporal = {
            scenario: [run.to_dict()['temporal_analysis'] for run in scenario_runs
                       if run.scenario_id == scenario]
            for scenario in ('S2', 'S5')}
        return ExperimentEvaluation(
            evaluation_version=EVALUATION_VERSION,
            configuration_fingerprint=CONFIGURATION_FINGERPRINT,
            metric_definitions=METRIC_DEFINITIONS,
            source_episode_fingerprints=tuple(run.source_episode_fingerprint for run in scenario_runs),
            scenario_runs=scenario_runs, overall_results=overall,
            per_seed_results=per_seed, per_scenario_results=per_scenario,
            ground_truth_stratification=truth, action_confusion_matrix=matrix,
            governance_confusion_matrix=governance_matrix,
            temporal_analyses=temporal,
            utility_framework=EVALUATION_CONFIG['utility_profiles'],
            limitations=(
                'Expected-safe-action labels are simulator annotations, not observed physical outcomes.',
                'Unsafe/false-intervention mappings are explicit evaluator assumptions, not inference policy.',
                'Five seeds provide exploratory uncertainty only; events are not independent replicates.',
                'Risk is descriptive and is not interpreted as attack probability.',
                'Numeric utility is deferred because no domain-reviewed cost matrix is frozen.',
                'No baseline, ablation, significance test, calibration, or causal effectiveness claim is included.',
            ))
