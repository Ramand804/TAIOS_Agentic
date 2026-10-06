"""Maps an authoritative ProcessState snapshot into stable OPC UA node values."""
from industrial.opcua.namespace import NODES
from industrial.process.enums import ProcessAsset
from industrial.process.state import ProcessState


def state_values(state: ProcessState) -> dict[str, object]:
    return {
        "ProductionController.MachineState": state.state_for(ProcessAsset.PRODUCTION_CONTROLLER).value,
        "Mixer.MachineState": state.state_for(ProcessAsset.MIXER).value,
        "Mixer.SpeedRPM": state.mixer_speed_rpm,
        "Mixer.TemperatureCelsius": state.mixer_temperature_celsius,
        "Pump.MachineState": state.pump_state.value,
        "Pump.PressureBar": state.pump_pressure_bar,
        "Pump.FlowRateLPM": state.pump_flow_rate_lpm,
        "Conveyor.MachineState": state.conveyor_state.value,
        "Conveyor.SpeedMPS": state.conveyor_speed_mps,
        "Process.OperatingMode": state.operating_mode.value,
        "Process.ProductionRateUnitsPerHour": state.production_rate_units_per_hour,
        "Process.MaintenanceMode": state.maintenance_mode,
        "Process.EmergencyState": state.emergency_state,
        "Process.StateVersion": state.state_version,
        "Process.SourceTimestamp": state.source_timestamp,
    }
