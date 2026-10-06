"""Immutable, unit-explicit state for the deterministic testbed cell."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Mapping

from industrial.process.enums import MachineState, OperatingMode, ProcessAsset

SIMULATION_EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _timestamp(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("source_timestamp must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ProcessState:
    """Observable simulated process state. All numeric fields carry units."""

    machine_state: Mapping[ProcessAsset, MachineState] = field(
        default_factory=lambda: {asset: MachineState.STOPPED for asset in ProcessAsset}
    )
    operating_mode: OperatingMode = OperatingMode.NORMAL
    mixer_speed_rpm: float = 0.0
    mixer_temperature_celsius: float = 20.0
    pump_state: MachineState = MachineState.STOPPED
    pump_pressure_bar: float = 0.0
    pump_flow_rate_lpm: float = 0.0
    conveyor_state: MachineState = MachineState.STOPPED
    conveyor_speed_mps: float = 0.0
    production_rate_units_per_hour: float = 0.0
    maintenance_mode: bool = False
    emergency_state: bool = False
    state_version: int = 0
    source_timestamp: datetime = SIMULATION_EPOCH

    def __post_init__(self) -> None:
        states = {ProcessAsset(asset): MachineState(value) for asset, value in self.machine_state.items()}
        if set(states) != set(ProcessAsset):
            raise ValueError("machine_state must contain every ProcessAsset")
        object.__setattr__(self, "machine_state", MappingProxyType(states))
        object.__setattr__(self, "operating_mode", OperatingMode(self.operating_mode))
        object.__setattr__(self, "pump_state", MachineState(self.pump_state))
        object.__setattr__(self, "conveyor_state", MachineState(self.conveyor_state))
        if type(self.maintenance_mode) is not bool or type(self.emergency_state) is not bool:
            raise ValueError("maintenance_mode and emergency_state must be bool")
        if type(self.state_version) is not int or self.state_version < 0:
            raise ValueError("state_version must be a non-negative integer")
        for field_name in (
            "mixer_speed_rpm", "mixer_temperature_celsius", "pump_pressure_bar",
            "pump_flow_rate_lpm", "conveyor_speed_mps", "production_rate_units_per_hour",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{field_name} must be numeric")
            object.__setattr__(self, field_name, float(value))
        object.__setattr__(self, "source_timestamp", _timestamp(self.source_timestamp))
        if self.pump_state != states[ProcessAsset.PUMP] or self.conveyor_state != states[ProcessAsset.CONVEYOR]:
            raise ValueError("pump_state and conveyor_state must match machine_state")
        if self.maintenance_mode != (self.operating_mode is OperatingMode.MAINTENANCE):
            raise ValueError("maintenance_mode must match MAINTENANCE operating mode")

    @classmethod
    def initial(cls, source_timestamp: datetime = SIMULATION_EPOCH) -> "ProcessState":
        return cls(source_timestamp=source_timestamp)

    def state_for(self, asset: ProcessAsset) -> MachineState:
        return self.machine_state[ProcessAsset(asset)]

    def logical_dict(self) -> dict:
        """Stable content used by tests; no runtime identity or hidden state."""
        return {
            "machine_state": {asset.value: self.machine_state[asset].value for asset in ProcessAsset},
            "operating_mode": self.operating_mode.value,
            "mixer_speed_rpm": self.mixer_speed_rpm,
            "mixer_temperature_celsius": self.mixer_temperature_celsius,
            "pump_state": self.pump_state.value,
            "pump_pressure_bar": self.pump_pressure_bar,
            "pump_flow_rate_lpm": self.pump_flow_rate_lpm,
            "conveyor_state": self.conveyor_state.value,
            "conveyor_speed_mps": self.conveyor_speed_mps,
            "production_rate_units_per_hour": self.production_rate_units_per_hour,
            "maintenance_mode": self.maintenance_mode,
            "emergency_state": self.emergency_state,
            "state_version": self.state_version,
            "source_timestamp": self.source_timestamp.isoformat(),
        }
