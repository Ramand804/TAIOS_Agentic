from copy import deepcopy

import pytest

from core.taios_pipeline import TAIOSPipeline
from environment.event_generator import EventGenerator
from evaluation.evaluation_contracts import ExperimentEvaluation
from evaluation.evaluation_metrics import (
    ACTIONS, classification_metrics, confusion, seed_summary,
)
from evaluation.formal_evaluator import (
    CONFIGURATION_FINGERPRINT, EVALUATION_CONFIG, TAIOSEvaluator,
)
from evaluation.run_formal_evaluation import run_evaluation


def completed(scenario='S2', seed=42):
    generator = EventGenerator(seed, observable_state=True)
    experiment = generator.create_run(scenario, 10)
    events = generator.generate(scenario, 10, experiment)
    episode = TAIOSPipeline().run_episode(
        events, scenario_reference=experiment.experiment_id, seed=seed)
    return episode, events


@pytest.fixture(scope='module')
def evaluation():
    return run_evaluation()


def test_evaluator_construction_and_configuration_fingerprint():
    evaluator = TAIOSEvaluator()
    assert evaluator.configuration_fingerprint == CONFIGURATION_FINGERPRINT
    assert CONFIGURATION_FINGERPRINT == __import__(
        'core.experiment', fromlist=['fingerprint']).fingerprint(EVALUATION_CONFIG)


def test_hard_inference_evaluation_separation():
    episode, events = completed()
    inference = episode.pipeline_results[0].to_dict()
    serialized = str(inference)
    assert 'ground_truth' not in serialized
    assert 'expected_safe_action' not in serialized
    evaluated = TAIOSEvaluator().evaluate_episode(episode, events)
    assert evaluated.events[0].ground_truth == events[0].ground_truth


def test_exact_action_agreement_and_confusion_matrix(evaluation):
    overall = evaluation.to_dict()['overall_results']
    assert overall['exact_action_matches'] == 143
    assert overall['exact_action_agreement'] == pytest.approx(143 / 300)
    matrix = evaluation.to_dict()['action_confusion_matrix']
    assert matrix['ALLOW']['ALLOW'] == 93
    assert matrix['ALLOW']['REQUEST_APPROVAL'] == 72
    assert matrix['BLOCK']['REQUEST_APPROVAL'] == 50
    assert matrix['ISOLATE']['REQUEST_APPROVAL'] == 35


def test_per_action_metrics_and_zero_support_are_explicit(evaluation):
    metrics = evaluation.to_dict()['overall_results']['classification']
    assert metrics['per_action']['ALLOW']['precision'] == 1.0
    assert metrics['per_action']['LIMIT']['recall'] is None
    assert metrics['per_action']['LIMIT']['recall_status'] == 'UNDEFINED_ZERO_SUPPORT'
    assert metrics['macro_f1_zero_filled'] is not None


def test_unsafe_action_mapping_is_explicit_and_observed_rate_is_zero(evaluation):
    overall = evaluation.to_dict()['overall_results']
    assert EVALUATION_CONFIG['unsafe_proposals_by_expected_action']['BLOCK'] == ('ALLOW',)
    assert overall['unsafe_action_eligible_events'] == 135
    assert overall['unsafe_action_count'] == 0
    assert overall['unsafe_action_rate'] == 0.0


def test_false_intervention_mapping_and_rate(evaluation):
    overall = evaluation.to_dict()['overall_results']
    assert overall['false_intervention_count'] == 72
    assert overall['false_intervention_eligible_events'] == 165
    assert overall['false_intervention_rate'] == pytest.approx(72 / 165)


def test_review_burden_and_autonomous_execution(evaluation):
    overall = evaluation.to_dict()['overall_results']
    assert overall['proposal_review_burden'] == pytest.approx(207 / 300)
    assert overall['governance_review_burden'] == pytest.approx(207 / 300)
    assert overall['pending_execution_burden'] == pytest.approx(207 / 300)
    assert overall['autonomous_execution_rate'] == pytest.approx(93 / 300)


def test_execution_safety_metrics_are_calculated(evaluation):
    assert evaluation.to_dict()['overall_results']['execution_safety'] == {
        'unauthorized_execution': 0, 'stale_approval_execution': 0,
        'duplicate_mutation': 0, 'payload_mismatch_execution': 0}


def test_ground_truth_stratification(evaluation):
    truth = evaluation.to_dict()['ground_truth_stratification']
    assert truth['BENIGN']['count'] == 165
    assert truth['SUSPICIOUS']['count'] == 50
    assert truth['MALICIOUS']['count'] == 85
    assert truth['MALICIOUS']['review_rate'] == 1.0
    assert truth['MALICIOUS']['autonomous_execution_rate'] == 0.0


def test_scenario_stratification_and_s3_limitation(evaluation):
    scenarios = evaluation.to_dict()['per_scenario_results']
    assert scenarios['S3']['proposal_review_burden'] == 1.0
    assert scenarios['S3']['autonomous_execution_rate'] == 0.0
    assert scenarios['S4']['exact_action_agreement'] == 1.0
    assert scenarios['S5']['exact_action_agreement'] == 1.0


def test_s2_temporal_evaluation(evaluation):
    run = next(run for run in evaluation.scenario_runs
               if run.scenario_id == 'S2' and run.seed == 42)
    temporal = run.to_dict()['temporal_analysis']
    assert temporal['transition_sequence'] == 6
    assert temporal['first_post_change_review_sequence'] == 6
    assert temporal['review_onset_delay'] == 0
    assert temporal['unsafe_post_change_count'] == 0
    assert temporal['successful_post_change_executions'] == 0


def test_s5_temporal_evaluation(evaluation):
    run = next(run for run in evaluation.scenario_runs
               if run.scenario_id == 'S5' and run.seed == 42)
    temporal = run.to_dict()['temporal_analysis']
    assert temporal['transition_sequence'] == 6
    assert temporal['post_change']['false_intervention_count'] == 0
    assert temporal['post_change']['proposal_review_count'] == 0
    assert temporal['successful_post_change_executions'] == 5
    assert temporal['table'][5]['operating_mode'] == 'HIGH_OUTPUT'


def test_deterministic_evaluation_and_no_inference_mutation():
    episode, events = completed('S2')
    before_episode = episode.to_dict()
    before_events = [event.to_dict() for event in events]
    first = TAIOSEvaluator().evaluate_experiment(((episode, events),))
    second = TAIOSEvaluator().evaluate_experiment(((episode, events),))
    assert first.to_dict() == second.to_dict()
    assert episode.to_dict() == before_episode
    assert [event.to_dict() for event in events] == before_events


def test_event_order_alignment_is_enforced():
    episode, events = completed()
    reversed_events = list(reversed(events))
    with pytest.raises(ValueError, match='aligned'):
        TAIOSEvaluator().evaluate_episode(episode, reversed_events)


def test_five_seed_aggregation_uses_seed_replication(evaluation):
    aggregate = evaluation.to_dict()['overall_results']['seed_level_aggregation']
    exact = aggregate['exact_action_agreement']
    assert exact['replication_unit'] == 'seed'
    assert exact['defined_seeds'] == 5
    assert exact['exploratory_95_percent_t_interval'] is not None


def test_seed_summary_does_not_treat_events_as_replicates():
    result = seed_summary([0.1, 0.2, 0.3, 0.4, 0.5])
    assert result['defined_seeds'] == 5
    assert result['replication_unit'] == 'seed'


def test_classification_helper_retains_all_six_actions():
    rows = [{'expected_action': 'ALLOW', 'proposed_action': 'ALLOW'}]
    matrix = confusion(rows)
    assert tuple(matrix) == ACTIONS
    result = classification_metrics(matrix)
    assert set(result['per_action']) == set(ACTIONS)


def test_result_contract_is_immutable(evaluation):
    assert type(evaluation) is ExperimentEvaluation
    with pytest.raises(Exception):
        evaluation.evaluation_version = 'changed'


def test_utility_profiles_defer_numeric_claims(evaluation):
    framework = evaluation.to_dict()['utility_framework']
    assert set(framework) == {'safety_conservative', 'balanced', 'availability_oriented'}
    assert all('deferred' in description for description in framework.values())
