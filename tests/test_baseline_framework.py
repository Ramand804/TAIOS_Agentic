from dataclasses import FrozenInstanceError, replace

import pytest

from agents.fixed_neutral_trust_agent import FixedNeutralTrustAgent
from agents.rule_based_decision_agent import RuleBasedDecisionAgent
from core.experimental_configuration import ExperimentalConfiguration
from environment.event_generator import EventGenerator
from evaluation.baseline_framework import CONFIGURATION_SPECS, create_pipeline
from evaluation.evaluate_baseline_framework import evaluate
from evaluation.formal_evaluator import TAIOSEvaluator


def stream(scenario='S2', seed=42):
    generator = EventGenerator(seed, observable_state=True)
    run = generator.create_run(scenario, 10)
    return run, generator.generate(scenario, 10, run)


def test_configuration_contract_is_complete_immutable_and_deterministic():
    assert set(CONFIGURATION_SPECS) == set(ExperimentalConfiguration)
    assert len({spec.configuration_fingerprint for spec in CONFIGURATION_SPECS.values()}) == 4
    spec = CONFIGURATION_SPECS[ExperimentalConfiguration.RULE_BASED]
    assert spec.configuration_fingerprint == CONFIGURATION_SPECS[spec.configuration].configuration_fingerprint
    with pytest.raises(FrozenInstanceError):
        spec.version = 'changed'


def test_rule_baseline_is_deterministic_and_uses_explicit_adapter():
    run, events = stream('S2')
    first = create_pipeline(ExperimentalConfiguration.RULE_BASED)
    second = create_pipeline(ExperimentalConfiguration.RULE_BASED)
    assert type(first.decision_agent) is RuleBasedDecisionAgent
    a = first.run_episode(events, scenario_reference=run.experiment_id, seed=42)
    b = second.run_episode(events, scenario_reference=run.experiment_id, seed=42)
    assert [r.proposed_decision.reference for r in a.pipeline_results] == [
        r.proposed_decision.reference for r in b.pipeline_results]


def test_rule_baseline_does_not_consume_evaluator_or_scenario_reference():
    _, events = stream('S5')
    a = create_pipeline('RULE_BASED').run_episode(events, scenario_reference='label-a', seed=42)
    b = create_pipeline('RULE_BASED').run_episode(events, scenario_reference='label-b', seed=42)
    assert [r.proposed_decision.reference for r in a.pipeline_results] == [
        r.proposed_decision.reference for r in b.pipeline_results]


def test_no_trust_is_fixed_at_documented_prior_but_preserves_evidence_coverage():
    _, events = stream('S2')
    pipeline = create_pipeline('TAIOS_NO_TRUST')
    assert type(pipeline.trust_agent) is FixedNeutralTrustAgent
    result = pipeline.run_episode(events, seed=42)
    assert {r.trust_assessment.composite_trust for r in result.pipeline_results} == {0.8}
    assert all(r.trust_assessment.trust_delta == 0 for r in result.pipeline_results)
    assert any('POSITIVE' in signs
               for signs in result.pipeline_results[0].trust_assessment.evidence_coverage.values())


def test_no_trust_preserves_authorization_and_semantics():
    _, events = stream('S2')
    static = create_pipeline('TAIOS_STATIC').run_episode(events, seed=42)
    no_trust = create_pipeline('TAIOS_NO_TRUST').run_episode(events, seed=42)
    assert [r.authorization_assessment for r in static.pipeline_results] == [
        r.authorization_assessment for r in no_trust.pipeline_results]
    assert [r.operational_semantic_assessment for r in static.pipeline_results] == [
        r.operational_semantic_assessment for r in no_trust.pipeline_results]


def test_identical_event_input_and_fresh_state_across_configurations():
    _, events = stream('S1')
    references = []
    for configuration in ExperimentalConfiguration:
        episode = create_pipeline(configuration).run_episode(events, seed=42)
        references.append([r.event_reference for r in episode.pipeline_results])
        assert episode.pipeline_results[0].state_before.state_version == 0
    assert all(item == references[0] for item in references)


def test_pipeline_factory_isolates_memory_and_execution_state():
    _, events = stream('S5')
    first = create_pipeline('TAIOS_ADAPTIVE')
    first.run_episode(events, seed=42)
    second = create_pipeline('TAIOS_ADAPTIVE')
    assert second.memory.count == 0
    assert second.feedback_memory.count == 0
    assert second.behavioral_adapter.store.snapshots == ()
    a = first.run_episode(events, seed=42)
    b = second.run_episode(events, seed=42)
    assert a.episode_fingerprint == b.episode_fingerprint


def test_static_and_adaptive_preserve_frozen_s5_behavior():
    _, events = stream('S5')
    static = create_pipeline('TAIOS_STATIC').run_episode(events, seed=42)
    adaptive = create_pipeline('TAIOS_ADAPTIVE').run_episode(events, seed=42)
    assert [r.drift_assessment.status.value for r in static.pipeline_results[5:]] == [
        'KNOWN_REGIME_CHANGE'] * 5
    assert adaptive.pipeline_results[5].adaptation_decision.status.value == 'DEFERRED'
    assert adaptive.pipeline_results[6].adaptation_decision.status.value == 'APPLIED'
    assert [r.drift_assessment.status.value for r in adaptive.pipeline_results[7:]] == [
        'NO_CHANGE'] * 3
    assert [r.proposed_decision.selected_action for r in static.pipeline_results] == [
        r.proposed_decision.selected_action for r in adaptive.pipeline_results]


@pytest.mark.parametrize('scenario', ('S1', 'S2', 'S3', 'S4', 'S5', 'S6'))
def test_all_scenarios_use_common_evaluator(scenario):
    _, events = stream(scenario)
    for configuration in ExperimentalConfiguration:
        episode = create_pipeline(configuration).run_episode(events, seed=42)
        evaluated = TAIOSEvaluator().evaluate_episode(episode, events)
        assert len(evaluated.events) == 10


@pytest.fixture(scope='module')
def matrix_result():
    return evaluate()


def test_matrix_denominators_seed_aggregation_and_event_counts(matrix_result):
    assert matrix_result['matrix']['episodes'] == 120
    assert matrix_result['matrix']['event_level_evaluations'] == 1200
    assert len(matrix_result['episode_summaries']) == 120
    assert len(matrix_result['event_level_references']) == 1200
    for result in matrix_result['configuration_results'].values():
        metrics = result['aggregate_metrics']
        assert metrics['exact_action_agreement']['denominator'] == 300
        assert metrics['unsafe_action_rate']['denominator'] == 135
        assert metrics['false_intervention_rate']['denominator'] == 165
        assert metrics['review_burden']['denominator'] == 300
        assert metrics['autonomous_execution_rate']['denominator'] == 300
        assert len(result['per_seed_metrics']) == 5
        assert all(item['replication_unit'] == 'seed'
                   for item in result['seed_level_aggregation'].values())


def test_matrix_actions_and_paired_differences_are_observed_not_tuned(matrix_result):
    rows = matrix_result['comparison_table']
    assert len(rows) == 4
    assert all(row['exact_agreement']['numerator'] == 143 for row in rows)
    assert all(row['unsafe_action_rate']['numerator'] == 0 for row in rows)
    for configuration, seeds in matrix_result['paired_seed_differences_from_taios_static'].items():
        assert set(seeds) == {'42', '123', '456', '789', '2026'}
        assert all(all(value == 0 for value in metrics.values()) for metrics in seeds.values())


def test_s2_no_trust_changes_scores_not_actions_and_s5_changes_drift(matrix_result):
    s2 = matrix_result['s2_detailed_comparison_seed42']
    assert [r['trust'] for r in s2['TAIOS_NO_TRUST']] == [0.8] * 10
    assert [r['risk'] for r in s2['TAIOS_NO_TRUST']] != [r['risk'] for r in s2['TAIOS_STATIC']]
    assert [r['action'] for r in s2['TAIOS_NO_TRUST']] == [r['action'] for r in s2['TAIOS_STATIC']]
    s5 = matrix_result['s5_static_adaptive_comparison_seed42']
    assert [r['drift'] for r in s5['TAIOS_STATIC'][7:]] == ['KNOWN_REGIME_CHANGE'] * 3
    assert [r['drift'] for r in s5['TAIOS_ADAPTIVE'][7:]] == ['NO_CHANGE'] * 3
