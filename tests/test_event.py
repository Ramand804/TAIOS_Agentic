import pytest
from environment.event import IndustrialEvent

def test_event_validation():
    e = IndustrialEvent(
        source_id="PLC-01", source_type="PLC", target_id="MOTOR-02",
        target_type="actuator", identity_id="operator-01",
        event_type="control_command", operation="set_speed",
        requested_value=50, network_zone="control", protocol="modbus",
        authentication_status=True, asset_criticality=0.9,
        ground_truth="BENIGN", scenario_id="S1", expected_safe_action="ALLOW")
    assert e.ground_truth == "BENIGN"
    assert 0 <= e.asset_criticality <= 1

def test_invalid_criticality():
    with pytest.raises(ValueError):
        IndustrialEvent(
            source_id="x", source_type="x", target_id="y", target_type="y",
            identity_id="z", event_type="x", operation="x", requested_value=1,
            network_zone="x", protocol="x", authentication_status=True,
            asset_criticality=1.5, ground_truth="BENIGN", scenario_id="S1")
