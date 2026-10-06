"""Single-path, deterministic manufacturing cell. State mutation follows interlock approval."""
from dataclasses import dataclass, replace
from typing import Mapping

from industrial.process.commands import ProcessCommand
from industrial.process.constraints import ProcessLimits
from industrial.process.enums import InterlockStatus, MachineState, OperatingMode, ProcessAsset, ProcessOperation
from industrial.process.state import ProcessState
from industrial.safety.interlock import InterlockResult, ProcessInterlock


@dataclass(frozen=True)
class ProcessCommandResult:
    command_id: str
    interlock: InterlockResult
    state_before: ProcessState
    state_after: ProcessState

    @property
    def allowed(self) -> bool:
        return self.interlock.allowed


class ManufacturingCell:
    """A deterministic software simulation; apply() is its sole public mutation path."""

    def __init__(self, initial_state: ProcessState | None = None, limits: ProcessLimits | None = None) -> None:
        self._limits = limits or ProcessLimits()
        self._interlock = ProcessInterlock(self._limits)
        self._state = initial_state or ProcessState.initial()

    @property
    def state(self) -> ProcessState:
        return self._state

    @property
    def limits(self) -> ProcessLimits:
        return self._limits

    def apply(self, command: ProcessCommand) -> ProcessCommandResult:
        before = self._state
        interlock = self._interlock.validate(command, before)
        if not interlock.allowed:
            return ProcessCommandResult(command.command_id, interlock, before, before)
        after = self._apply_allowed(command, before)
        self._state = after
        return ProcessCommandResult(command.command_id, interlock, before, after)

    def _apply_allowed(self, command: ProcessCommand, state: ProcessState) -> ProcessState:
        """Private transition invoked only after ProcessInterlock approval."""
        operation = command.operation
        updates: dict = {"state_version": state.state_version + 1, "source_timestamp": command.timestamp}
        machine_state = dict(state.machine_state)
        if operation is ProcessOperation.START_ASSET:
            machine_state[command.target] = MachineState.RUNNING
            updates["machine_state"] = machine_state
            if command.target is ProcessAsset.PUMP:
                updates["pump_state"] = MachineState.RUNNING
            elif command.target is ProcessAsset.CONVEYOR:
                updates["conveyor_state"] = MachineState.RUNNING
        elif operation is ProcessOperation.STOP_ASSET:
            machine_state[command.target] = MachineState.STOPPED
            updates["machine_state"] = machine_state
            self._zero_asset_updates(command.target, updates)
        elif operation is ProcessOperation.SET_MIXER_SPEED_RPM:
            updates["mixer_speed_rpm"] = float(command.requested_value)
        elif operation is ProcessOperation.SET_PUMP_FLOW_RATE_LPM:
            flow = float(command.requested_value)
            updates["pump_flow_rate_lpm"] = flow
            updates["pump_pressure_bar"] = flow * self._limits.pump_pressure_bar_per_lpm
        elif operation is ProcessOperation.SET_CONVEYOR_SPEED_MPS:
            updates["conveyor_speed_mps"] = float(command.requested_value)
        elif operation is ProcessOperation.SET_PRODUCTION_RATE_UNITS_PER_HOUR:
            updates["production_rate_units_per_hour"] = float(command.requested_value)
        elif operation is ProcessOperation.CHANGE_OPERATING_MODE:
            mode = OperatingMode(command.requested_value)
            updates["operating_mode"] = mode
            updates["maintenance_mode"] = mode is OperatingMode.MAINTENANCE
        elif operation is ProcessOperation.REQUEST_SHUTDOWN:
            updates.update(self._safe_shutdown_updates(machine_state))
        elif operation is ProcessOperation.EMERGENCY_STOP:
            machine_state = {asset: MachineState.EMERGENCY_STOP for asset in ProcessAsset}
            updates.update(self._safe_shutdown_updates(machine_state))
            updates["emergency_state"] = True
        elif operation is ProcessOperation.RESET_EMERGENCY:
            machine_state = {asset: MachineState.STOPPED for asset in ProcessAsset}
            updates["machine_state"] = machine_state
            updates["pump_state"] = MachineState.STOPPED
            updates["conveyor_state"] = MachineState.STOPPED
            updates["emergency_state"] = False
            updates["operating_mode"] = OperatingMode.NORMAL
            updates["maintenance_mode"] = False
        return replace(state, **updates)

    @staticmethod
    def _zero_asset_updates(asset: ProcessAsset, updates: dict) -> None:
        if asset is ProcessAsset.MIXER:
            updates["mixer_speed_rpm"] = 0.0
        elif asset is ProcessAsset.PUMP:
            updates["pump_state"] = MachineState.STOPPED
            updates["pump_flow_rate_lpm"] = 0.0
            updates["pump_pressure_bar"] = 0.0
        elif asset is ProcessAsset.CONVEYOR:
            updates["conveyor_state"] = MachineState.STOPPED
            updates["conveyor_speed_mps"] = 0.0
        elif asset is ProcessAsset.PRODUCTION_CONTROLLER:
            updates["production_rate_units_per_hour"] = 0.0

    @staticmethod
    def _safe_shutdown_updates(machine_state: Mapping[ProcessAsset, MachineState]) -> dict:
        return {
            "machine_state": dict(machine_state),
            "pump_state": machine_state[ProcessAsset.PUMP],
            "conveyor_state": machine_state[ProcessAsset.CONVEYOR],
            "mixer_speed_rpm": 0.0,
            "pump_flow_rate_lpm": 0.0,
            "pump_pressure_bar": 0.0,
            "conveyor_speed_mps": 0.0,
            "production_rate_units_per_hour": 0.0,
            "operating_mode": OperatingMode.SHUTDOWN,
            "maintenance_mode": False,
        }
