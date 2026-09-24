from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest

from core.operational_semantics import OperationalSemanticAssessment, SemanticStatus
from core.runtime_inputs import runtime_observation
from core.taios_pipeline import TAIOSPipeline
from environment.event_generator import EventGenerator
from environment.industrial_environment import IndustrialState
from intelligence.operational_semantic_model import (
    OperationalSemanticModel, OperationalSemanticRegistry,
)


def events(scenario='S2', seed=42):
    generator = EventGenerator(seed, observable_state=True)
    run = generator.create_run(scenario, 10)
    return generator.generate(scenario, 10, run)


def assessment(scenario='S2', index=0):
    return OperationalSemanticModel().assess(runtime_observation(events(scenario)[index]))


def test_model_and_registry_construction_and_fingerprint():
    registry = OperationalSemanticRegistry()
    model = OperationalSemanticModel(registry)
    assert model.registry.fingerprint == OperationalSemanticRegistry().fingerprint
    assert set(registry.rules) == {'set_speed', 'write_register'}


def test_assessment_is_immutable_and_deterministic():
    first, second = assessment(), assessment()
    assert type(first) is OperationalSemanticAssessment
    assert first.to_dict() == second.to_dict()
    assert first.reference == second.reference
    with pytest.raises(FrozenInstanceError):
        first.operation = 'changed'


def test_normal_set_speed_validity_uses_canonical_limits():
    result = assessment('S2', 4)
    assert result.semantic_status == SemanticStatus.SUPPORTED_VALID
    assert result.operational_validity == 'WITHIN_LIMIT'
    assert dict(result.known_constraints)['minimum'] == 20
    assert dict(result.known_constraints)['maximum'] == 80


def test_high_output_set_speed_validity_uses_current_mode():
    result = assessment('S5', 5)
    assert result.semantic_status == SemanticStatus.SUPPORTED_VALID
    assert dict(result.known_constraints)['operating_mode'] == 'HIGH_OUTPUT'
    assert (result.known_constraints['minimum'], result.known_constraints['maximum']) == (60, 95)


def test_invalid_set_speed_is_explicit():
    result = assessment('S2', 5)
    assert result.semantic_status == SemanticStatus.SUPPORTED_INVALID
    assert result.operational_validity == 'OUTSIDE_LIMIT'


def test_write_register_is_recognized_but_underspecified():
    result = assessment('S3', 5)
    assert result.semantic_status == SemanticStatus.UNDERSPECIFIED
    assert result.applicable_semantic_rule_ids == ('OPS-WRITE_REGISTER',)
    assert result.operational_validity == 'UNKNOWN'
    assert any('register_address' in item for item in result.unresolved_semantic_requirements)


def test_unknown_operation_is_unsupported():
    observation = runtime_observation(events()[0])
    observation['operation'] = 'unknown_operation'
    result = OperationalSemanticModel().assess(observation)
    assert result.semantic_status == SemanticStatus.UNSUPPORTED


def test_semantic_coverage_for_all_scenarios():
    statuses = []
    for scenario in (f'S{i}' for i in range(1, 7)):
        statuses.extend(OperationalSemanticModel().assess(runtime_observation(event)).semantic_status
                        for event in events(scenario))
    assert statuses.count(SemanticStatus.UNDERSPECIFIED) == 17
    assert statuses.count(SemanticStatus.UNSUPPORTED) == 4
    assert sum(status in (SemanticStatus.SUPPORTED_VALID, SemanticStatus.SUPPORTED_INVALID)
               for status in statuses) == 39


def test_leakage_and_audit_invariance():
    event = events('S3')[5]
    before = OperationalSemanticModel().assess(runtime_observation(event))
    changed = deepcopy(event)
    changed.ground_truth = 'BENIGN'
    changed.expected_safe_action = 'ALLOW'
    changed.scenario_id = 'OTHER'
    changed.event_id = 'OTHER'
    changed.sequence_number = 999
    changed.provenance = None
    changed.contextual_features.update(
        anomaly_score=999, transition='OTHER', causal_tags=['OTHER'],
        formal_evaluation_value=1.0)
    after = OperationalSemanticModel().assess(runtime_observation(changed))
    assert before.to_dict() == after.to_dict()


def test_pipeline_and_decision_context_propagate_exact_assessment():
    result = TAIOSPipeline().process_event(events()[0], IndustrialState())
    assert result.operational_semantic_assessment is result.decision_context.operational_semantic_assessment
    assert result.to_dict()['operational_semantic_assessment']['semantic_status'] == 'SUPPORTED_VALID'


def test_s2_and_s5_pipeline_regressions():
    s2 = TAIOSPipeline().run_episode(events('S2'), seed=42)
    assert all(row.operational_semantic_assessment.semantic_status == SemanticStatus.SUPPORTED_INVALID
               for row in s2.pipeline_results[5:])
    assert all(row.execution_result.execution_status.value == 'PENDING_APPROVAL'
               for row in s2.pipeline_results[5:])
    s5 = TAIOSPipeline().run_episode(events('S5'), seed=42)
    assert all(row.operational_semantic_assessment.semantic_status == SemanticStatus.SUPPORTED_VALID
               for row in s5.pipeline_results)
    assert all(row.execution_result.execution_status.value == 'SUCCEEDED'
               for row in s5.pipeline_results)


def test_s3_behavior_remains_review_without_fabricated_register_semantics():
    episode = TAIOSPipeline().run_episode(events('S3'), seed=42)
    assert all(row.operational_semantic_assessment.semantic_status == SemanticStatus.UNDERSPECIFIED
               for row in episode.pipeline_results)
    assert episode.structural_summary['execution_statuses'] == {'PENDING_APPROVAL': 10}
