from copy import deepcopy

import pytest

from agents.planning_agent import PlanningAgent
from core.experiment import fingerprint
from core.pipeline_result import EpisodeResult, PipelineProcessingError, PipelineResult
from core.taios_pipeline import PIPELINE_VERSION, TAIOSPipeline
from environment.event_generator import EventGenerator
from environment.industrial_environment import IndustrialState, OperatingMode


def generated(scenario='S2', seed=42, n=10):
    generator = EventGenerator(seed, observable_state=True)
    run = generator.create_run(scenario, n)
    return generator.generate(scenario, n, run)


def episode(scenario='S2', seed=42, n=10):
    return TAIOSPipeline().run_episode(generated(scenario, seed, n), seed=seed)


def test_pipeline_construction_and_single_event_complete_chain():
    pipeline = TAIOSPipeline()
    event = generated()[0]
    result = pipeline.process_event(event, IndustrialState())
    assert type(result) is PipelineResult
    assert result.pipeline_version == PIPELINE_VERSION
    assert result.decision_context.observation == result.observable_input
    assert result.planning_result.context_fingerprint == result.decision_context.reference
    assert result.proposed_decision.planning_reference == result.planning_result.reference
    assert result.governance_decision.proposal_reference == result.proposed_decision.reference
    assert result.execution_result.governance_reference == result.governance_decision.reference


def test_state_and_trust_are_continuous_through_s2():
    result = episode('S2')
    assert type(result) is EpisodeResult
    rows = result.pipeline_results
    for previous, current in zip(rows, rows[1:]):
        assert current.input_state_reference == fingerprint(previous.state_after.to_dict())
    for row in rows:
        trust = row.trust_assessment
        assert trust.previous_composite_trust + trust.trust_delta == pytest.approx(
            trust.composite_trust)
    assert [row.trust_assessment.trust_state_version for row in rows] == list(range(1, 11))
    assert all(row.execution_result.execution_status.value == 'PENDING_APPROVAL'
               for row in rows[5:8])
    assert all(not row.execution_result.mutation_applied for row in rows[5:8])


def test_successful_allow_mutates_and_pending_approval_carries_state():
    rows = episode('S2').pipeline_results
    allow = rows[4]
    pending = rows[5]
    assert allow.execution_result.execution_status.value == 'SUCCEEDED'
    assert allow.execution_result.applied_value == 48
    assert allow.execution_result.mutation_applied
    assert pending.execution_result.execution_status.value == 'PENDING_APPROVAL'
    assert pending.state_before.to_dict() == pending.state_after.to_dict()


def test_s5_regime_and_version_continuity():
    rows = episode('S5').pipeline_results
    assert rows[4].state_after.operating_mode == OperatingMode.NORMAL
    assert rows[5].regime_transition_applied
    assert rows[5].state_before.operating_mode == OperatingMode.HIGH_OUTPUT
    assert rows[5].state_before.state_version == rows[4].state_after.state_version + 1
    assert rows[5].execution_result.execution_status.value == 'SUCCEEDED'
    assert rows[5].decision_context.capabilities.operational_validity.check.minimum == 60
    assert rows[5].decision_context.capabilities.operational_validity.check.maximum == 95
    for previous, current in zip(rows, rows[1:]):
        assert current.input_state_reference == fingerprint(previous.state_after.to_dict())
    assert not any(row.execution_result.execution_status.value == 'STALE_STATE' for row in rows)


def test_deterministic_pipeline_and_episode_fingerprints_and_order_sensitivity():
    events = generated('S2')
    first = TAIOSPipeline().run_episode(events, seed=42)
    second = TAIOSPipeline().run_episode(events, seed=42)
    assert first.to_dict() == second.to_dict()
    assert first.episode_fingerprint == second.episode_fingerprint
    reordered = deepcopy(events)
    reordered[0], reordered[1] = reordered[1], reordered[0]
    third = TAIOSPipeline().run_episode(reordered, seed=42)
    assert third.episode_fingerprint != first.episode_fingerprint


class FailingPlanner(PlanningAgent):
    def plan(self, decision_context):
        raise ValueError('synthetic planning failure')


def test_pipeline_failure_is_structured_and_state_and_trust_are_transactional():
    event = generated()[0]
    state = IndustrialState()
    pipeline = TAIOSPipeline(planning_agent=FailingPlanner())
    before = state.to_dict()
    with pytest.raises(PipelineProcessingError) as caught:
        pipeline.process_event(event, state)
    assert caught.value.failure.stage == 'planning'
    assert state.to_dict() == before
    pipeline.planning_agent = PlanningAgent()
    recovered = pipeline.process_event(event, state)
    fresh = TAIOSPipeline().process_event(event, state)
    assert recovered.trust_assessment.to_inference_dict() == fresh.trust_assessment.to_inference_dict()


def test_execution_idempotency_is_preserved_for_complete_event_replay():
    event = generated()[4]
    pipeline = TAIOSPipeline()
    first = pipeline.process_event(event, IndustrialState())
    replay = pipeline.process_event(event, first.state_after)
    assert first.execution_result.execution_status.value == 'SUCCEEDED'
    assert replay.execution_result.execution_status.value == 'ALREADY_EXECUTED'
    assert replay.execution_result.execution_id == first.execution_result.execution_id
    assert not replay.execution_result.mutation_applied


def test_integration_leakage_and_audit_isolation():
    event = deepcopy(generated('S2')[4])
    event.provenance = None
    event.experiment_id = None
    baseline = TAIOSPipeline().process_event(event, IndustrialState())
    changed = deepcopy(event)
    changed.ground_truth = 'SUSPICIOUS'
    changed.expected_safe_action = 'ISOLATE'
    changed.scenario_id = 'OTHER'
    changed.contextual_features.update(
        anomaly_score=999, simulated_attack_probability=-999,
        transition=999, causal_tags=['OTHER'])
    changed.event_id = 'AUDIT-ONLY-ID'
    changed.sequence_number = 999
    observed = TAIOSPipeline().process_event(changed, IndustrialState())
    assert observed.pipeline_fingerprint == baseline.pipeline_fingerprint
    assert observed.decision_context.to_dict() == baseline.decision_context.to_dict()
    assert observed.execution_result.to_dict() == baseline.execution_result.to_dict()


@pytest.mark.parametrize('scenario', [f'S{i}' for i in range(1, 7)])
def test_full_scenario_episode_is_complete(scenario):
    result = episode(scenario)
    assert len(result.pipeline_results) == 10
    assert result.structural_summary['total_events'] == 10
    assert result.final_state_reference == fingerprint(result.final_state.to_dict())


def test_s3_preserves_unresolved_write_register_semantics():
    result = episode('S3')
    assert result.structural_summary['proposals'] == {'REQUEST_APPROVAL': 10}
    assert result.structural_summary['execution_statuses'] == {'PENDING_APPROVAL': 10}
    assert result.structural_summary['state_mutations'] == 0


def test_five_seed_reproducibility():
    def run():
        return {
            (scenario, seed): episode(scenario, seed).to_dict()
            for scenario in (f'S{i}' for i in range(1, 7))
            for seed in (42, 123, 456, 789, 2026)
        }
    assert run() == run()
