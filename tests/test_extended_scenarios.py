from core.experiment import event_stream_fingerprint
from core.runtime_inputs import runtime_observation
from core.taios_pipeline import TAIOSPipeline
from environment.event_generator import EventGenerator
from environment.operational_limits import OperationalLimits


def _events(scenario, seed=42, count=50):
    generator = EventGenerator(seed, observable_state=True)
    run = generator.create_run(scenario, count)
    return generator.generate(scenario, count, run)


def test_s7_is_deterministic_valid_authorized_and_leak_free():
    events = _events('S7')
    assert event_stream_fingerprint(events) == event_stream_fingerprint(_events('S7'))
    limits = OperationalLimits()
    assert all(event.authentication_status and event.expected_safe_action for event in events)
    assert all(limits.check_operational_limit(event.target_id, event.operation, event.requested_value,
               event.contextual_features['operating_mode']).within_limit for event in events)
    observed = runtime_observation(events[-1])
    assert 'phase' not in observed and 'ground_truth' not in observed and 'expected_safe_action' not in observed
    episode = TAIOSPipeline().run_episode(events)
    assert all(row.authorization_assessment.status.value == 'AUTHORIZED' for row in episode.pipeline_results)
    assert all(row.operational_semantic_assessment.semantic_status.value == 'SUPPORTED_VALID' for row in episode.pipeline_results)
    assert any(row.assurance_assessment.status.value == 'AUTONOMY_RESTRICTED' for row in episode.pipeline_results)


def test_s8_is_explained_valid_negative_control():
    events = _events('S8')
    episode = TAIOSPipeline().run_episode(events)
    assert all(row.operational_semantic_assessment.semantic_status.value == 'SUPPORTED_VALID' for row in episode.pipeline_results)
    assert any(row.drift_assessment.status.value == 'KNOWN_REGIME_CHANGE' for row in episode.pipeline_results)
    assert not any(row.assurance_assessment.status.value == 'AUTONOMY_RESTRICTED' for row in episode.pipeline_results)


def test_s9_has_recovery_phase_and_same_objects_can_be_reused():
    events = _events('S9')
    assert events[-1].provenance.phase == 'RECOVERY'
    static = TAIOSPipeline().run_episode(events)
    adaptive = TAIOSPipeline().run_episode(events)
    assert [row.event_reference for row in static.pipeline_results] == [row.event_reference for row in adaptive.pipeline_results]
