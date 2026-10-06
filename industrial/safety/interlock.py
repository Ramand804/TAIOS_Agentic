"""Independent deterministic command validator for the manufacturing simulator."""
from dataclasses import dataclass
from math import isfinite

from industrial.process.commands import ProcessCommand
from industrial.process.constraints import ProcessLimits
from industrial.process.enums import (
    InterlockStatus, MachineState, OperatingMode, ProcessAsset, ProcessOperation,
)
from industrial.process.state import ProcessState


@dataclass(frozen=True)
class InterlockResult:
    status: InterlockStatus
    reason: str

    @property
    def allowed(self) -> bool:
        return self.status is InterlockStatus.ALLOWED


class ProcessInterlock:
    """Safety boundary that validates every public process-changing command."""

    _TARGETS = {
        ProcessOperation.SET_MIXER_SPEED_RPM: {ProcessAsset.MIXER},
        ProcessOperation.SET_PUMP_FLOW_RATE_LPM: {ProcessAsset.PUMP},
        ProcessOperation.SET_CONVEYOR_SPEED_MPS: {ProcessAsset.CONVEYOR},
        ProcessOperation.SET_PRODUCTION_RATE_UNITS_PER_HOUR: {ProcessAsset.PRODUCTION_CONTROLLER},
        ProcessOperation.CHANGE_OPERATING_MODE: {ProcessAsset.PRODUCTION_CONTROLLER},
        ProcessOperation.START_ASSET: set(ProcessAsset),
        ProcessOperation.STOP_ASSET: set(ProcessAsset),
        ProcessOperation.REQUEST_SHUTDOWN: {ProcessAsset.PRODUCTION_CONTROLLER},
        ProcessOperation.EMERGENCY_STOP: {ProcessAsset.PRODUCTION_CONTROLLER},
        ProcessOperation.RESET_EMERGENCY: {ProcessAsset.PRODUCTION_CONTROLLER},
    }
    _MAINTENANCE_ALLOWED = {
        ProcessOperation.STOP_ASSET,
        ProcessOperation.CHANGE_OPERATING_MODE,
        ProcessOperation.REQUEST_SHUTDOWN,
        ProcessOperation.EMERGENCY_STOP,
        ProcessOperation.RESET_EMERGENCY,
    }
    _MODE_TRANSITIONS = {
        OperatingMode.NORMAL: {OperatingMode.HIGH_OUTPUT, OperatingMode.MAINTENANCE, OperatingMode.SHUTDOWN},
        OperatingMode.HIGH_OUTPUT: {OperatingMode.NORMAL, OperatingMode.SHUTDOWN},
        OperatingMode.MAINTENANCE: {OperatingMode.NORMAL, OperatingMode.SHUTDOWN},
        OperatingMode.SHUTDOWN: set(),
    }

    def __init__(self, limits: ProcessLimits | None = None) -> None:
        self.limits = limits or ProcessLimits()

    @staticmethod
    def _result(status: InterlockStatus, reason: str) -> InterlockResult:
        return InterlockResult(status, reason)

    @staticmethod
    def _finite_number(value: object) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
            return None
        return float(value)

    def validate(self, command: ProcessCommand, state: ProcessState) -> InterlockResult:
        """Validate command against current state; this method never mutates it."""
        if command.expected_state_version is not None and command.expected_state_version != state.state_version:
            return self._result(InterlockStatus.REJECTED_STATE_VERSION_MISMATCH, "stale state version")
        if command.target not in self._TARGETS.get(command.operation, set()):
            return self._result(InterlockStatus.REJECTED_INVALID_TARGET, "operation is not valid for target")
        if state.emergency_state and command.operation not in {
            ProcessOperation.RESET_EMERGENCY, ProcessOperation.EMERGENCY_STOP,
        }:
            return self._result(InterlockStatus.REJECTED_EMERGENCY_STATE, "emergency state is active")
        if state.maintenance_mode and command.operation not in self._MAINTENANCE_ALLOWED:
            return self._result(InterlockStatus.REJECTED_MAINTENANCE_RESTRICTION, "maintenance mode restricts production changes")
        if command.operation is ProcessOperation.RESET_EMERGENCY and not state.emergency_state:
            return self._result(InterlockStatus.REJECTED_INVALID_TRANSITION, "emergency is not active")
        if command.operation is ProcessOperation.EMERGENCY_STOP:
            return self._result(InterlockStatus.ALLOWED, "emergency stop is always available")
        if command.operation is ProcessOperation.CHANGE_OPERATING_MODE:
            try:
                requested_mode = OperatingMode(command.requested_value)
            except (TypeError, ValueError):
                return self._result(InterlockStatus.REJECTED_INVALID_OPERATION, "requested operating mode is invalid")
            if requested_mode not in self._MODE_TRANSITIONS[state.operating_mode]:
                return self._result(InterlockStatus.REJECTED_INVALID_TRANSITION, "operating-mode transition is not permitted")
        if command.operation is ProcessOperation.START_ASSET:
            if state.state_for(command.target) is not MachineState.STOPPED:
                return self._result(InterlockStatus.REJECTED_INVALID_TRANSITION, "only stopped assets can start")
            if state.operating_mode is OperatingMode.SHUTDOWN:
                return self._result(InterlockStatus.REJECTED_INVALID_TRANSITION, "assets cannot start in shutdown")
        if command.operation is ProcessOperation.STOP_ASSET and state.state_for(command.target) is not MachineState.RUNNING:
            return self._result(InterlockStatus.REJECTED_INVALID_TRANSITION, "only running assets can stop")
        numeric_ranges = {
            ProcessOperation.SET_MIXER_SPEED_RPM: (self.limits.mixer_speed_rpm_min, self.limits.mixer_speed_rpm_max),
            ProcessOperation.SET_PUMP_FLOW_RATE_LPM: (self.limits.pump_flow_rate_lpm_min, self.limits.pump_flow_rate_lpm_max),
            ProcessOperation.SET_CONVEYOR_SPEED_MPS: (self.limits.conveyor_speed_mps_min, self.limits.conveyor_speed_mps_max),
            ProcessOperation.SET_PRODUCTION_RATE_UNITS_PER_HOUR: (
                self.limits.production_rate_units_per_hour_min, self.limits.production_rate_units_per_hour_max,
            ),
        }
        if command.operation in numeric_ranges:
            value = self._finite_number(command.requested_value)
            if value is None:
                return self._result(InterlockStatus.REJECTED_INVALID_OPERATION, "requested value must be finite numeric")
            lower, upper = numeric_ranges[command.operation]
            if not lower <= value <= upper:
                return self._result(InterlockStatus.REJECTED_OUT_OF_RANGE, "requested value exceeds testbed limits")
            if command.operation is ProcessOperation.SET_PUMP_FLOW_RATE_LPM and (
                value * self.limits.pump_pressure_bar_per_lpm > self.limits.pump_pressure_bar_max
            ):
                return self._result(InterlockStatus.REJECTED_OUT_OF_RANGE, "derived pump pressure exceeds testbed limit")
            if state.state_for(command.target) is not MachineState.RUNNING:
                return self._result(InterlockStatus.REJECTED_INVALID_TRANSITION, "asset must be running before adjustment")
        return self._result(InterlockStatus.ALLOWED, "command satisfies deterministic interlock")
