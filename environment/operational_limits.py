"""Centralized operating limits; missing limits fail explicitly."""
from dataclasses import asdict, dataclass
from types import MappingProxyType

from environment.assets import get_asset
from environment.industrial_environment import OperatingMode, validate_number


@dataclass(frozen=True)
class LimitCheck:
    within_limit: bool
    minimum: float
    maximum: float
    requested_value: float
    deviation: float

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class OperationalLimits:
    limits: object = None

    def __post_init__(self):
        configured = self.limits if self.limits is not None else {
            ("MOTOR-02", "set_speed", OperatingMode.NORMAL): (20, 80),
            ("MOTOR-02", "set_speed", OperatingMode.HIGH_OUTPUT): (60, 95),
            ("MOTOR-02", "set_speed", OperatingMode.REDUCED): (10, 50),
            ("MOTOR-02", "set_speed", OperatingMode.MAINTENANCE): (0, 20),
        }
        validated = {}
        for (asset_id, operation, mode), (minimum, maximum) in configured.items():
            get_asset(asset_id)
            if not isinstance(operation, str) or not operation.strip():
                raise ValueError("operation must be a nonempty string")
            validate_number(minimum, "minimum")
            validate_number(maximum, "maximum")
            if minimum > maximum:
                raise ValueError("minimum must not exceed maximum")
            validated[(asset_id, operation, OperatingMode(mode))] = (minimum, maximum)
        object.__setattr__(self, "limits", MappingProxyType(validated))

    def check_operational_limit(self, asset_id, operation, requested_value, operating_mode):
        """d = max(minimum-x, 0, x-maximum) / (maximum-minimum).

        Bounds are inclusive. For a zero-width range the denominator is 1,
        so deviation is absolute distance in the operation's units.
        """
        get_asset(asset_id)
        validate_number(requested_value, "requested_value")
        key = (asset_id, operation, OperatingMode(operating_mode))
        if key not in self.limits:
            raise KeyError(f"No operational limits configured for {key}")
        minimum, maximum = self.limits[key]
        distance = max(minimum - requested_value, 0, requested_value - maximum)
        return LimitCheck(minimum <= requested_value <= maximum, minimum, maximum,
                          requested_value, distance / (maximum - minimum or 1))

    def to_dict(self):
        return [{"asset_id": asset, "operation": operation, "operating_mode": mode.value,
                 "minimum": bounds[0], "maximum": bounds[1]}
                for (asset, operation, mode), bounds in sorted(self.limits.items())]


DEFAULT_OPERATIONAL_LIMITS = OperationalLimits()


def check_operational_limit(asset_id, operation, requested_value, operating_mode):
    return DEFAULT_OPERATIONAL_LIMITS.check_operational_limit(
        asset_id, operation, requested_value, operating_mode)
