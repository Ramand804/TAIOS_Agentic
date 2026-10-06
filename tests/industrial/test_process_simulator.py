from dataclasses import replace
from datetime import timedelta

import pytest

from industrial.process.commands import ProcessCommand
from industrial.process.enums import InterlockStatus, MachineState, OperatingMode, ProcessAsset, ProcessOperation
from industrial.process.model import ManufacturingCell
from industrial.process.state import SIMULATION_EPOCH, ProcessState
from industrial.testbed.scenarios import TESTBED_SCENARIOS


def command(n, target, operation, value=None, version=None):
    return ProcessCommand(
        command_id=f"test-{n}", target=target, operation=operation, requested_value=value,
        expected_state_version=version, timestamp=SIMULATION_EPOCH + timedelta(seconds=n),
    )


def start(cell, target, n):
    result = cell.apply(command(n, target, ProcessOperation.START_ASSET, version=cell.state.state_version))
    assert result.allowed
    return result


def test_initial_state_is_safe_and_immutable():
    state = ManufacturingCell().state
    assert state.operating_mode is OperatingMode.NORMAL
    assert state.state_version == 0
    assert all(value is MachineState.STOPPED for value in state.machine_state.values())
    with pytest.raises(TypeError):
        state.machine_state[ProcessAsset.MIXER] = MachineState.RUNNING


def test_normal_adjustments_change_only_expected_fields():
    cell = ManufacturingCell()
    start(cell, ProcessAsset.MIXER, 1)
    before = cell.state
    result = cell.apply(command(2, ProcessAsset.MIXER, ProcessOperation.SET_MIXER_SPEED_RPM, 900, before.state_version))
    assert result.allowed and result.state_after.mixer_speed_rpm == 900
    assert result.state_after.state_version == before.state_version + 1
    assert result.state_after.pump_flow_rate_lpm == before.pump_flow_rate_lpm
    assert result.state_after.machine_state == before.machine_state


def test_operating_modes_and_shutdown_transitions():
    cell = ManufacturingCell()
    assert cell.apply(command(1, ProcessAsset.PRODUCTION_CONTROLLER, ProcessOperation.CHANGE_OPERATING_MODE, OperatingMode.HIGH_OUTPUT, 0)).allowed
    assert cell.apply(command(2, ProcessAsset.PRODUCTION_CONTROLLER, ProcessOperation.CHANGE_OPERATING_MODE, OperatingMode.NORMAL, 1)).allowed
    assert cell.apply(command(3, ProcessAsset.PRODUCTION_CONTROLLER, ProcessOperation.CHANGE_OPERATING_MODE, OperatingMode.MAINTENANCE, 2)).allowed
    assert cell.state.maintenance_mode
    assert cell.apply(command(4, ProcessAsset.PRODUCTION_CONTROLLER, ProcessOperation.CHANGE_OPERATING_MODE, OperatingMode.NORMAL, 3)).allowed
    assert cell.apply(command(5, ProcessAsset.PRODUCTION_CONTROLLER, ProcessOperation.REQUEST_SHUTDOWN, version=4)).allowed
    assert cell.state.operating_mode is OperatingMode.SHUTDOWN
    assert cell.state.production_rate_units_per_hour == 0


@pytest.mark.parametrize(("target", "operation", "value", "field"), [
    (ProcessAsset.MIXER, ProcessOperation.SET_MIXER_SPEED_RPM, 800, "mixer_speed_rpm"),
    (ProcessAsset.PUMP, ProcessOperation.SET_PUMP_FLOW_RATE_LPM, 40, "pump_flow_rate_lpm"),
    (ProcessAsset.CONVEYOR, ProcessOperation.SET_CONVEYOR_SPEED_MPS, 1.2, "conveyor_speed_mps"),
    (ProcessAsset.PRODUCTION_CONTROLLER, ProcessOperation.SET_PRODUCTION_RATE_UNITS_PER_HOUR, 500, "production_rate_units_per_hour"),
])
def test_valid_setpoints(target, operation, value, field):
    cell = ManufacturingCell()
    start(cell, target, 1)
    result = cell.apply(command(2, target, operation, value, 1))
    assert result.allowed
    assert getattr(cell.state, field) == value
    if target is ProcessAsset.PUMP:
        assert cell.state.pump_pressure_bar == 20


@pytest.mark.parametrize(("target", "operation", "value"), [
    (ProcessAsset.MIXER, ProcessOperation.SET_MIXER_SPEED_RPM, 1801),
    (ProcessAsset.PUMP, ProcessOperation.SET_PUMP_FLOW_RATE_LPM, 101),
    (ProcessAsset.CONVEYOR, ProcessOperation.SET_CONVEYOR_SPEED_MPS, 2.6),
    (ProcessAsset.PRODUCTION_CONTROLLER, ProcessOperation.SET_PRODUCTION_RATE_UNITS_PER_HOUR, 1001),
])
def test_out_of_range_setpoints_leave_complete_state_unchanged(target, operation, value):
    cell = ManufacturingCell()
    start(cell, target, 1)
    before = cell.state
    result = cell.apply(command(2, target, operation, value, 1))
    assert result.interlock.status is InterlockStatus.REJECTED_OUT_OF_RANGE
    assert result.state_after == before == cell.state


def test_invalid_target_and_invalid_operation_are_rejected():
    cell = ManufacturingCell()
    invalid_target = cell.apply(command(1, ProcessAsset.PUMP, ProcessOperation.SET_MIXER_SPEED_RPM, 1, 0))
    assert invalid_target.interlock.status is InterlockStatus.REJECTED_INVALID_TARGET
    # A stopped but correctly targeted setpoint is an invalid state transition.
    invalid_operation = cell.apply(command(2, ProcessAsset.MIXER, ProcessOperation.SET_MIXER_SPEED_RPM, "not-numeric", 0))
    assert invalid_operation.interlock.status is InterlockStatus.REJECTED_INVALID_OPERATION


def test_maintenance_restricts_start_and_adjustment():
    cell = ManufacturingCell()
    assert cell.apply(command(1, ProcessAsset.PRODUCTION_CONTROLLER, ProcessOperation.CHANGE_OPERATING_MODE, OperatingMode.MAINTENANCE, 0)).allowed
    before = cell.state
    result = cell.apply(command(2, ProcessAsset.MIXER, ProcessOperation.START_ASSET, version=1))
    assert result.interlock.status is InterlockStatus.REJECTED_MAINTENANCE_RESTRICTION
    assert cell.state == before


def test_emergency_stop_requires_explicit_reset_and_blocks_commands():
    cell = ManufacturingCell()
    assert cell.apply(command(1, ProcessAsset.PRODUCTION_CONTROLLER, ProcessOperation.EMERGENCY_STOP, version=0)).allowed
    assert cell.state.emergency_state and all(s is MachineState.EMERGENCY_STOP for s in cell.state.machine_state.values())
    before = cell.state
    blocked = cell.apply(command(2, ProcessAsset.MIXER, ProcessOperation.START_ASSET, version=1))
    assert blocked.interlock.status is InterlockStatus.REJECTED_EMERGENCY_STATE
    assert cell.state == before
    reset = cell.apply(command(3, ProcessAsset.PRODUCTION_CONTROLLER, ProcessOperation.RESET_EMERGENCY, version=1))
    assert reset.allowed and not cell.state.emergency_state
    assert cell.state.operating_mode is OperatingMode.NORMAL
    assert all(s is MachineState.STOPPED for s in cell.state.machine_state.values())


def test_versioning_stale_rejection_and_no_mutation():
    cell = ManufacturingCell()
    assert cell.apply(command(1, ProcessAsset.PRODUCTION_CONTROLLER, ProcessOperation.CHANGE_OPERATING_MODE, OperatingMode.HIGH_OUTPUT, 0)).allowed
    before = cell.state
    stale = cell.apply(command(2, ProcessAsset.PRODUCTION_CONTROLLER, ProcessOperation.CHANGE_OPERATING_MODE, OperatingMode.NORMAL, 0))
    assert stale.interlock.status is InterlockStatus.REJECTED_STATE_VERSION_MISMATCH
    assert cell.state == before and cell.state.state_version == 1


def test_stopping_asset_zeroes_only_its_controlled_output():
    cell = ManufacturingCell()
    start(cell, ProcessAsset.PUMP, 1)
    assert cell.apply(command(2, ProcessAsset.PUMP, ProcessOperation.SET_PUMP_FLOW_RATE_LPM, 25, 1)).allowed
    before = cell.state
    result = cell.apply(command(3, ProcessAsset.PUMP, ProcessOperation.STOP_ASSET, version=2))
    assert result.allowed
    assert cell.state.pump_flow_rate_lpm == cell.state.pump_pressure_bar == 0
    assert cell.state.mixer_speed_rpm == before.mixer_speed_rpm


def test_identical_command_replay_is_logically_deterministic():
    commands = TESTBED_SCENARIOS["TB_PROCESS_01_NORMAL"].commands
    first, second = ManufacturingCell(), ManufacturingCell()
    for item in commands:
        assert first.apply(item).allowed
        assert second.apply(item).allowed
    assert first.state.logical_dict() == second.state.logical_dict()


@pytest.mark.parametrize("scenario_id", sorted(TESTBED_SCENARIOS))
def test_simulator_scenarios_are_deterministic(scenario_id):
    scenario = TESTBED_SCENARIOS[scenario_id]
    first, second = ManufacturingCell(), ManufacturingCell()
    results_a = [first.apply(item).interlock.status for item in scenario.commands]
    results_b = [second.apply(item).interlock.status for item in scenario.commands]
    assert results_a == results_b
    assert first.state.logical_dict() == second.state.logical_dict()


def test_direct_high_output_to_maintenance_is_an_invalid_transition():
    cell = ManufacturingCell()
    assert cell.apply(command(1, ProcessAsset.PRODUCTION_CONTROLLER, ProcessOperation.CHANGE_OPERATING_MODE, OperatingMode.HIGH_OUTPUT, 0)).allowed
    before = cell.state
    result = cell.apply(command(2, ProcessAsset.PRODUCTION_CONTROLLER, ProcessOperation.CHANGE_OPERATING_MODE, OperatingMode.MAINTENANCE, 1))
    assert result.interlock.status is InterlockStatus.REJECTED_INVALID_TRANSITION
    assert cell.state == before


def test_derived_excessive_pump_pressure_is_rejected():
    from industrial.process.constraints import ProcessLimits

    cell = ManufacturingCell(limits=ProcessLimits(pump_flow_rate_lpm_max=200))
    start(cell, ProcessAsset.PUMP, 1)
    before = cell.state
    result = cell.apply(command(2, ProcessAsset.PUMP, ProcessOperation.SET_PUMP_FLOW_RATE_LPM, 101, 1))
    assert result.interlock.status is InterlockStatus.REJECTED_OUT_OF_RANGE
    assert cell.state == before
