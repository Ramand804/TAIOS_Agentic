"""Central testbed process limits. These are not TAIOS scientific parameters."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ProcessLimits:
    mixer_speed_rpm_min: float = 0.0
    mixer_speed_rpm_max: float = 1800.0
    mixer_temperature_celsius_max: float = 90.0
    pump_pressure_bar_max: float = 50.0
    pump_flow_rate_lpm_min: float = 0.0
    pump_flow_rate_lpm_max: float = 100.0
    conveyor_speed_mps_min: float = 0.0
    conveyor_speed_mps_max: float = 2.5
    production_rate_units_per_hour_min: float = 0.0
    production_rate_units_per_hour_max: float = 1000.0
    pump_pressure_bar_per_lpm: float = 0.5

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise ValueError(f"{name} must be a non-negative number")
        for lower, upper in (
            (self.mixer_speed_rpm_min, self.mixer_speed_rpm_max),
            (self.pump_flow_rate_lpm_min, self.pump_flow_rate_lpm_max),
            (self.conveyor_speed_mps_min, self.conveyor_speed_mps_max),
            (self.production_rate_units_per_hour_min, self.production_rate_units_per_hour_max),
        ):
            if lower > upper:
                raise ValueError("minimum cannot exceed maximum")
