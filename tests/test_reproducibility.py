from dataclasses import replace
from datetime import datetime, timedelta
import json
import random

import pytest

from core.experiment import ExperimentRun, event_stream_fingerprint
from core.orchestrator import Orchestrator
from environment.event import IndustrialEvent
from environment.event_generator import EventGenerator
from environment.validators import validate_event_asset_integrity


@pytest.mark.parametrize("scenario", [f"S{i}" for i in range(1, 7)])
def test_repeated_generation_is_identical_and_valid(scenario):
    generator = EventGenerator(42)
    first = generator.generate(scenario, 100)
    generator.generate("S1", 7)
    second = generator.generate(scenario, 100)
    assert [e.to_dict() for e in first] == [e.to_dict() for e in second]
    assert [e.event_id for e in first] == [e.event_id for e in second]
    assert [e.timestamp for e in first] == [e.timestamp for e in second]
    assert [e.sequence_number for e in first] == list(range(1, 101))
    assert len({e.event_id for e in first}) == 100
    assert event_stream_fingerprint(first) == event_stream_fingerprint(second)
    assert all(validate_event_asset_integrity(e) for e in first + second)


def test_different_seed_changes_content_and_fingerprint():
    first = EventGenerator(42).generate("S2", 100)
    second = EventGenerator(123).generate("S2", 100)
    assert first[0].experiment_id != second[0].experiment_id
    assert [e.requested_value for e in first] != [e.requested_value for e in second]
    assert event_stream_fingerprint(first) != event_stream_fingerprint(second)


@pytest.mark.parametrize("change", [
    {"scenario_id": "S3"}, {"seed": 123}, {"total_events": 11},
    {"simulation_start_time": "2026-02-01T00:00:00+00:00"},
    {"event_interval_seconds": 2}, {"generator_version": "next"},
    {"configuration": {"setting": 2}},
])
def test_meaningful_run_inputs_change_identity(change):
    run = ExperimentRun("S2", 42, 10)
    assert replace(run, **change).experiment_id != run.experiment_id


def test_canonical_configuration_and_timezone():
    a = ExperimentRun("S2", 42, 10, configuration={"a": 1, "b": 2})
    b = ExperimentRun("S2", 42, 10, "2026-01-01T05:30:00+05:30", configuration={"b": 2, "a": 1})
    assert a.to_dict() == b.to_dict()


def test_configurable_simulated_clock():
    generator = EventGenerator(42)
    run = generator.create_run("S2", 10, "2026-03-01T00:00:00+00:00", 0.5)
    events = generator.generate("S2", 10, run)
    assert [e.timestamp for e in events] == [
        (datetime.fromisoformat(run.simulation_start_time) + timedelta(seconds=i * 0.5)).isoformat()
        for i in range(10)]
    assert events[0].event_id == f"{run.experiment_id}-E000001"


def test_generation_never_uses_uuid_or_wall_clock(monkeypatch):
    import environment.event as event_module
    def forbidden(*args, **kwargs):
        raise AssertionError("Volatile metadata used during experiment generation")
    class NoClock:
        now = forbidden
    monkeypatch.setattr(event_module.uuid, "uuid4", forbidden)
    monkeypatch.setattr(event_module, "datetime", NoClock)
    for scenario in [f"S{i}" for i in range(1, 7)]:
        assert len(EventGenerator().generate(scenario, 10)) == 10


def test_module_random_state_is_untouched():
    before = random.getstate()
    for scenario in [f"S{i}" for i in range(1, 7)]:
        EventGenerator().generate(scenario, 10)
    assert random.getstate() == before


def test_fingerprint_detects_content_and_order_changes():
    events = EventGenerator().generate("S2", 10)
    original = event_stream_fingerprint(events)
    assert event_stream_fingerprint(list(reversed(events))) != original
    changed = [replace(events[0], requested_value=999)] + events[1:]
    assert event_stream_fingerprint(changed) != original
    changed = [replace(events[0], timestamp="2027-01-01T00:00:00+00:00")] + events[1:]
    assert event_stream_fingerprint(changed) != original


def test_standalone_events_keep_legacy_defaults_and_ignore_volatile_metadata():
    row = EventGenerator().generate("S2", 1)[0].to_dict()
    for field in ("event_id", "timestamp", "experiment_id", "sequence_number"):
        row.pop(field)
    first, second = IndustrialEvent(**row), IndustrialEvent(**row)
    assert first.event_id.startswith("EVT-")
    assert first.event_id != second.event_id
    assert first.experiment_id is None
    assert first.sequence_number is None
    assert event_stream_fingerprint([first]) == event_stream_fingerprint([second])


def test_repeated_persistence_replaces_log_and_separates_runs(tmp_path):
    runner = Orchestrator(log_dir=tmp_path)
    first = runner.run_scenario("S2", 10)
    path = runner.event_logger.path
    before = path.read_bytes()
    metadata = json.loads((path.parent / "experiment.json").read_text())
    second = runner.run_scenario("S2", 10)
    assert [e.to_dict() for e in first] == [e.to_dict() for e in second]
    assert path.read_bytes() == before
    assert len(path.read_text().splitlines()) == 10
    assert metadata == json.loads((path.parent / "experiment.json").read_text())
    assert metadata["event_stream_fingerprint"] == event_stream_fingerprint(second)
    assert metadata["experiment_id"] == runner.experiment.experiment_id
    runner.run_scenario("S3", 10)
    assert runner.event_logger.path != path
    assert path.read_bytes() == before
    assert not (tmp_path / "events.jsonl").exists()


def test_empty_run_persists_empty_stream(tmp_path):
    runner = Orchestrator(log_dir=tmp_path)
    assert runner.run_scenario("S2", 0) == []
    assert runner.event_logger.path.read_bytes() == b""


@pytest.mark.parametrize("change", [
    {"simulation_start_time": "2026-01-01T00:00:00"},
    {"event_interval_seconds": 0}, {"event_interval_seconds": -1},
    {"event_interval_seconds": float("nan")}, {"total_events": -1},
])
def test_invalid_run_parameters(change):
    with pytest.raises(ValueError):
        replace(ExperimentRun("S2", 42, 10), **change)


def test_context_mismatch_rejected():
    generator = EventGenerator()
    run = generator.create_run("S2", 10)
    with pytest.raises(ValueError):
        generator.generate("S3", 10, run)
    with pytest.raises(ValueError):
        generator.generate("S2", 10, replace(run, configuration={}))


def test_registry_changes_affect_run_identity(monkeypatch):
    from environment.assets import ASSET_REGISTRY
    generator = EventGenerator()
    first = generator.create_run("S2", 10)
    monkeypatch.setitem(ASSET_REGISTRY, "MOTOR-02", replace(ASSET_REGISTRY["MOTOR-02"], criticality=0.8))
    second = generator.create_run("S2", 10)
    assert first.experiment_id != second.experiment_id
    with pytest.raises(ValueError, match="configuration"):
        generator.generate("S2", 10, first)
    assert all(event.asset_criticality == 0.8 for event in generator.generate("S2", 10, second))


def test_incompatible_generator_version_rejected():
    generator = EventGenerator()
    run = replace(generator.create_run("S2", 10), generator_version="future")
    with pytest.raises(ValueError, match="generator_version"):
        generator.generate("S2", 10, run)


def test_seed_provenance_changes_fingerprint_without_random_draws():
    first = EventGenerator(42).generate("S4", 10)
    second = EventGenerator(123).generate("S4", 10)
    assert event_stream_fingerprint(first) != event_stream_fingerprint(second)
