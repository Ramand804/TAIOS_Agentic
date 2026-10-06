"""Stable namespace paths for the simulated plant."""
FACTORY = "TAIOSFactory"
NODES = {
    "ProductionController.MachineState": ("ProductionController", "MachineState"),
    "Mixer.MachineState": ("Mixer", "MachineState"),
    "Mixer.SpeedRPM": ("Mixer", "SpeedRPM"),
    "Mixer.TemperatureCelsius": ("Mixer", "TemperatureCelsius"),
    "Pump.MachineState": ("Pump", "MachineState"),
    "Pump.PressureBar": ("Pump", "PressureBar"),
    "Pump.FlowRateLPM": ("Pump", "FlowRateLPM"),
    "Conveyor.MachineState": ("Conveyor", "MachineState"),
    "Conveyor.SpeedMPS": ("Conveyor", "SpeedMPS"),
    "Process.OperatingMode": ("Process", "OperatingMode"),
    "Process.ProductionRateUnitsPerHour": ("Process", "ProductionRateUnitsPerHour"),
    "Process.MaintenanceMode": ("Process", "MaintenanceMode"),
    "Process.EmergencyState": ("Process", "EmergencyState"),
    "Process.StateVersion": ("Process", "StateVersion"),
    "Process.SourceTimestamp": ("Process", "SourceTimestamp"),
}
