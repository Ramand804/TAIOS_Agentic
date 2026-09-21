from dataclasses import replace
import json

import pytest

from core.event_manager import EventManager
from core.orchestrator import Orchestrator
from environment.assets import ASSET_REGISTRY, VirtualAsset, asset_index, get_asset
from environment.event_generator import EventGenerator
from environment.validators import EventIntegrityError, validate_event_asset_integrity


def test_plc07_registry_metadata():
    asset = get_asset("PLC-07")
    assert (asset.asset_type, asset.network_zone, asset.protocol, asset.criticality) == (
        "PLC", "control", "modbus", 0.92)
    assert asset_index()["PLC-07"] is ASSET_REGISTRY["PLC-07"]


def test_s2_integrity_for_100_events():
    assert all(validate_event_asset_integrity(e) for e in EventGenerator(42).generate("S2", 100))


def test_s2_source_metadata():
    for e in EventGenerator(42).generate("S2", 100):
        assert (e.source_id, e.source_type, e.network_zone, e.protocol) == (
            "PLC-07", "PLC", "control", "modbus")


def test_malformed_plc07_reports_all_mismatches():
    event = EventGenerator(42).generate("S2", 1)[0]
    event = replace(event, network_zone="enterprise", protocol="https")
    with pytest.raises(EventIntegrityError) as exc:
        validate_event_asset_integrity(event)
    assert all(field in str(exc.value) for field in (event.event_id, "network_zone", "protocol"))
    assert event.network_zone == "enterprise"
    assert event.protocol == "https"


def test_unknown_asset_lookup():
    with pytest.raises(KeyError):
        get_asset("PLC-DOES-NOT-EXIST")


def test_s2_transition():
    for sequence, e in enumerate(EventGenerator(42).generate("S2", 10), 1):
        compromised = sequence >= 6
        assert e.ground_truth == ("MALICIOUS" if compromised else "BENIGN")
        assert e.expected_safe_action == ("BLOCK" if compromised else "ALLOW")
        assert e.contextual_features == {
            "production_state": "ACTIVE", "anomaly_score": 0.92 if compromised else 0.05,
            "compromise_phase": compromised, "event_sequence": sequence, "compromise_event": 6,
        }
        low, high = (90, 120) if compromised else (40, 70)
        assert low <= e.requested_value <= high


def test_s2_target_metadata():
    target = get_asset("MOTOR-02")
    for e in EventGenerator(42).generate("S2", 10):
        assert (e.target_id, e.target_type, e.asset_criticality) == (
            target.asset_id, target.asset_type, target.criticality)


@pytest.mark.parametrize("field,value", [
    ("source_id", "UNKNOWN"), ("target_id", "UNKNOWN"),
    ("source_type", "service"), ("network_zone", "enterprise"),
    ("protocol", "https"), ("target_type", "PLC"), ("asset_criticality", 0.5),
])
def test_each_integrity_check(field, value):
    event = replace(EventGenerator(42).generate("S2", 1)[0], **{field: value})
    with pytest.raises(EventIntegrityError, match=field):
        validate_event_asset_integrity(event)


@pytest.mark.parametrize("asset_id,criticality", [("", 0.5), ("  ", 0.5), ("A", -0.1), ("A", 1.1), ("A", float("nan"))])
def test_invalid_asset_metadata(asset_id, criticality):
    with pytest.raises(ValueError):
        VirtualAsset(asset_id, "PLC", "control", "modbus", criticality)


@pytest.mark.parametrize("criticality", [0.0, 1.0])
def test_asset_criticality_boundaries(criticality):
    assert VirtualAsset("A", "PLC", "control", "modbus", criticality).criticality == criticality


def test_event_manager_rejects_invalid_events():
    event = replace(EventGenerator(42).generate("S2", 1)[0], protocol="https")
    with pytest.raises(EventIntegrityError):
        EventManager().validate(iter([event]))


def test_orchestrator_validates_entire_batch_before_logging(tmp_path, monkeypatch):
    runner = Orchestrator(log_dir=tmp_path)
    events = runner.generator.generate("S2", 2)
    events[1].protocol = "https"
    monkeypatch.setattr(runner.generator, "generate", lambda *_: events)
    with pytest.raises(EventIntegrityError):
        runner.run_scenario("S2", 2)
    assert not list(tmp_path.rglob("events.jsonl"))


@pytest.mark.parametrize("scenario", ["S1", "S2", "S3", "S4", "S5", "S6"])
def test_all_scenarios_pass_pipeline_integrity(scenario, tmp_path):
    runner = Orchestrator(seed=42, log_dir=tmp_path)
    events = runner.run_scenario(scenario, 100)
    assert len(events) == 100
    assert all(validate_event_asset_integrity(event) for event in events)
    rows = [json.loads(line) for line in runner.event_logger.path.read_text().splitlines()]
    assert rows == [event.to_dict() for event in events]
