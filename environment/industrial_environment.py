"""Dynamic plant state; static metadata remains in the asset registry.

Transitions accept any validated enum value; no process interlock policy is
invented here. Maintenance/emergency flags are independent explicit context.
"""
from dataclasses import dataclass, field, replace
from enum import Enum
import math
from types import MappingProxyType
from typing import Mapping

from environment.assets import ASSET_REGISTRY, get_asset


class ProductionState(str, Enum):
    IDLE = "IDLE"
    ACTIVE = "ACTIVE"
    MAINTENANCE = "MAINTENANCE"
    EMERGENCY = "EMERGENCY"


class OperatingMode(str, Enum):
    NORMAL = "NORMAL"
    HIGH_OUTPUT = "HIGH_OUTPUT"
    REDUCED = "REDUCED"
    MAINTENANCE = "MAINTENANCE"


class AssetStatus(str, Enum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"


class AssetHealth(str, Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


def validate_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")


def validate_version(value):
    if type(value) is not int or value < 0:
        raise ValueError("state_version must be a nonnegative integer")


@dataclass(frozen=True)
class AssetState:
    asset_id: str
    status: AssetStatus = AssetStatus.STOPPED
    health: AssetHealth = AssetHealth.NORMAL
    current_value: float | None = None
    last_operation: str | None = None
    state_version: int = 0

    def __post_init__(self):
        get_asset(self.asset_id)
        object.__setattr__(self, "status", AssetStatus(self.status))
        object.__setattr__(self, "health", AssetHealth(self.health))
        validate_version(self.state_version)
        if self.current_value is not None:
            validate_number(self.current_value, "current_value")
        if self.last_operation is not None and (
                not isinstance(self.last_operation, str) or not self.last_operation.strip()):
            raise ValueError("last_operation must be a nonempty string or None")

    def to_dict(self):
        return {"asset_id": self.asset_id, "status": self.status.value,
                "health": self.health.value, "current_value": self.current_value,
                "last_operation": self.last_operation, "state_version": self.state_version}


@dataclass(frozen=True)
class StateSnapshot:
    state_version: int
    production_state: ProductionState
    operating_mode: OperatingMode
    maintenance_mode: bool
    emergency_state: bool
    asset_states: Mapping[str, AssetState]

    def __post_init__(self):
        object.__setattr__(self, "asset_states", MappingProxyType(dict(self.asset_states)))

    def to_dict(self):
        return {"state_version": self.state_version,
                "production_state": self.production_state.value,
                "operating_mode": self.operating_mode.value,
                "maintenance_mode": self.maintenance_mode,
                "emergency_state": self.emergency_state,
                "asset_states": {key: self.asset_states[key].to_dict() for key in sorted(self.asset_states)}}


@dataclass(frozen=True)
class IndustrialState:
    production_state: ProductionState = ProductionState.ACTIVE
    operating_mode: OperatingMode = OperatingMode.NORMAL
    maintenance_mode: bool = False
    emergency_state: bool = False
    asset_states: Mapping[str, AssetState] = field(
        default_factory=lambda: {key: AssetState(key) for key in sorted(ASSET_REGISTRY)})
    state_version: int = 0

    def __post_init__(self):
        object.__setattr__(self, "production_state", ProductionState(self.production_state))
        object.__setattr__(self, "operating_mode", OperatingMode(self.operating_mode))
        for name in ("maintenance_mode", "emergency_state"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be bool")
        validate_version(self.state_version)
        for key, value in self.asset_states.items():
            if not isinstance(value, AssetState) or key != value.asset_id:
                raise ValueError("asset_states keys must match their AssetState.asset_id")
            get_asset(key)
        object.__setattr__(self, "asset_states", MappingProxyType(dict(self.asset_states)))

    def _transition(self, field_name, value):
        if getattr(self, field_name) != value:
            object.__setattr__(self, field_name, value)
            object.__setattr__(self, "state_version", self.state_version + 1)
        return self.state_version

    def set_production_state(self, value):
        return self._transition("production_state", ProductionState(value))

    def set_operating_mode(self, value):
        return self._transition("operating_mode", OperatingMode(value))

    def set_maintenance_mode(self, value):
        if type(value) is not bool:
            raise ValueError("maintenance_mode must be bool")
        return self._transition("maintenance_mode", value)

    def set_emergency_state(self, value):
        if type(value) is not bool:
            raise ValueError("emergency_state must be bool")
        return self._transition("emergency_state", value)

    def update_asset_state(self, asset_id, **changes):
        get_asset(asset_id)
        allowed = {"status", "health", "current_value", "last_operation"}
        if not set(changes) <= allowed:
            raise ValueError(f"Unsupported asset state fields: {sorted(set(changes) - allowed)}")
        previous = self.asset_states[asset_id]
        updated = replace(previous, **changes)
        if updated != previous:
            updated = replace(updated, state_version=previous.state_version + 1)
            assets = dict(self.asset_states)
            assets[asset_id] = updated
            self._transition("asset_states", MappingProxyType(assets))
        return self.state_version

    def snapshot(self, asset_id=None):
        assets = self.asset_states if asset_id is None else {asset_id: self.asset_states[asset_id]}
        return StateSnapshot(self.state_version, self.production_state, self.operating_mode,
                             self.maintenance_mode, self.emergency_state, assets)

    def to_dict(self):
        return self.snapshot().to_dict()


class IndustrialEnvironment:
    """Compatibility facade for the former environment snapshot interface."""
    def __init__(self, state=None):
        if isinstance(state, IndustrialState):
            self.state = state
        else:
            values = dict(state or {})
            if "emergency" in values:
                values["emergency_state"] = values.pop("emergency")
            self.state = IndustrialState(**values)

    def snapshot(self):
        return self.state.to_dict()
