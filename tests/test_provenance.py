from dataclasses import replace
import json

import pytest

from core.event_manager import EventManager
from core.orchestrator import Orchestrator
from environment.event import IndustrialEvent
from environment.event_generator import EventGenerator
from environment.provenance import EventProvenance, ProvenanceIntegrityError, validate_event_provenance
from environment.scenarios import ScenarioManifest, get_scenario_manifest


@pytest.mark.parametrize('scenario', [f'S{i}' for i in range(1, 7)])
def test_manifest_and_complete_provenance(scenario):
    generator = EventGenerator()
    run = generator.create_run(scenario, 10)
    manifest = get_scenario_manifest(scenario, 10)
    assert ScenarioManifest(**manifest.to_dict()) == manifest
    assert json.dumps(manifest.to_dict(), sort_keys=True) == json.dumps(get_scenario_manifest(scenario, 10).to_dict(), sort_keys=True)
    for event in generator.generate(scenario, 10, run):
        p = event.provenance
        assert isinstance(p, EventProvenance)
        assert p.experiment_id == event.experiment_id == run.experiment_id
        assert p.sequence_number == event.sequence_number
        assert p.phase == manifest.phase_at(event.sequence_number)
        assert p.generator_version == run.generator_version
        assert p.scenario_version == manifest.scenario_version
        assert validate_event_provenance(event, manifest, run)
        assert IndustrialEvent(**event.to_dict()).to_dict() == event.to_dict()
        assert 'ground_truth' not in p.to_dict()
        assert 'expected_safe_action' not in p.to_dict()


@pytest.mark.parametrize('scenario,transition,pre,post', [
    ('S2', 6, 'PRE_COMPROMISE', 'POST_COMPROMISE'),
    ('S3', 6, 'PRE_COMPROMISE', 'POST_COMPROMISE'),
    ('S5', 6, 'PRE_CHANGE', 'POST_CHANGE'),
    ('S6', 4, 'PRE_ATTACK', 'POST_ATTACK'),
])
def test_exact_transition(scenario, transition, pre, post):
    manifest = get_scenario_manifest(scenario, 10)
    events = EventGenerator().generate(scenario, 10)
    assert manifest.transition_sequence == transition
    assert events[transition - 2].provenance.phase == pre
    assert events[transition - 1].provenance.phase == post
    if scenario == 'S5':
        assert events[transition - 2].contextual_features['operating_mode'] == 'NORMAL'
        assert events[transition - 1].contextual_features['operating_mode'] == 'HIGH_OUTPUT'
        assert all(e.contextual_features['regime_change_sequence'] == transition for e in events)


@pytest.mark.parametrize('scenario', ['S1', 'S4'])
def test_scenarios_without_transition(scenario):
    manifest = get_scenario_manifest(scenario, 10)
    assert manifest.transition_sequence is None
    assert manifest.transition_type == 'NONE'
    assert len(manifest.phases) == 1


def test_coordinated_entities():
    manifest = get_scenario_manifest('S6', 10)
    assert {'HMI-02', 'PLC-04', 'SERVICE-03'} <= set(manifest.affected_entities)


@pytest.mark.parametrize('change,field', [
    ({'experiment_id': 'EXP-WRONG'}, 'experiment_id'),
    ({'sequence_number': 2}, 'sequence_number'),
    ({'scenario_id': 'S3'}, 'scenario_id'),
    ({'phase': 'WRONG'}, 'phase'),
    ({'phase': 'POST_COMPROMISE'}, 'phase'),
    ({'transition_type': 'NONE'}, 'transition_type'),
    ({'scenario_version': 'wrong'}, 'scenario_version'),
    ({'generator_version': 'wrong'}, 'generator_version'),
    ({'causal_tags': ('wrong',)}, 'causal_tags'),
    ({'total_events': 20}, 'manifest'),
])
def test_inconsistent_provenance_rejected(change, field):
    generator = EventGenerator()
    run = generator.create_run('S2', 10)
    event = generator.generate('S2', 10, run)[0]
    event.provenance = replace(event.provenance, **change)
    with pytest.raises(ProvenanceIntegrityError, match=field):
        validate_event_provenance(event, get_scenario_manifest('S2', 10), run)


def test_missing_provenance_rejected_but_standalone_supported():
    event = EventGenerator().generate('S2', 10)[0]
    event.provenance = None
    with pytest.raises(ProvenanceIntegrityError):
        EventManager().validate([event])
    standalone = replace(event, experiment_id=None, sequence_number=None)
    assert EventManager().validate([standalone]) == [standalone]


def test_unknown_scenario_rejected():
    event = EventGenerator().generate('S2', 10)[0]
    event.scenario_id = 'UNKNOWN'
    with pytest.raises(ProvenanceIntegrityError):
        validate_event_provenance(event)


@pytest.mark.parametrize('changes', [
    {'scenario_id': 'UNKNOWN'}, {'total_events': -1}, {'total_events': True},
    {'scenario_version': ''}, {'phases': ()}, {'phases': ('A', 'A')},
    {'transition_sequence': 11}, {'transition_sequence': 1}, {'transition_sequence': None},
    {'transition_type': 'NONE'},
])
def test_invalid_manifest(changes):
    with pytest.raises(ValueError):
        replace(get_scenario_manifest('S2', 10), **changes)


@pytest.mark.parametrize('count', [0, 1, 2, 3, 11])
def test_short_and_odd_runs(count):
    for scenario in ('S2', 'S3', 'S5', 'S6'):
        manifest = get_scenario_manifest(scenario, count)
        assert (manifest.transition_sequence is None) == (count < 2)
        events = EventGenerator().generate(scenario, count)
        assert all(validate_event_provenance(e, manifest) for e in events)


def test_manifest_persistence_and_rerun_bytes(tmp_path):
    runner = Orchestrator(log_dir=tmp_path)
    runner.run_scenario('S5', 10)
    folder = runner.event_logger.path.parent
    filenames = ('experiment.json', 'scenario_manifest.json', 'events.jsonl')
    before = {name: (folder / name).read_bytes() for name in filenames}
    runner.run_scenario('S5', 10)
    assert before == {name: (folder / name).read_bytes() for name in filenames}
    assert len((folder / 'events.jsonl').read_text().splitlines()) == 10
    runner.run_scenario('S2', 10)
    assert json.loads((runner.event_logger.path.parent / 'scenario_manifest.json').read_text())['name'] == 'compromised_device'


def test_invalid_provenance_fails_before_logging(tmp_path, monkeypatch):
    runner = Orchestrator(log_dir=tmp_path)
    events = runner.generator.generate('S2', 10)
    events[-1].provenance = replace(events[-1].provenance, phase='PRE_COMPROMISE')
    monkeypatch.setattr(runner.generator, 'generate', lambda *_: events)
    with pytest.raises(ProvenanceIntegrityError):
        runner.run_scenario('S2', 10)
    assert not list(tmp_path.rglob('*.json*'))
