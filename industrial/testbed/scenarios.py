"""Fixed command sequences for the software-defined manufacturing cell."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from industrial.process.commands import ProcessCommand
from industrial.process.enums import OperatingMode, ProcessAsset, ProcessOperation
from industrial.process.state import SIMULATION_EPOCH


@dataclass(frozen=True)
class TestbedScenario:
    scenario_id: str
    description: str
    commands: tuple[ProcessCommand, ...]


def _command(index: int, target: ProcessAsset, operation: ProcessOperation, value=None, version=None) -> ProcessCommand:
    return ProcessCommand(
        command_id=f"TB-CMD-{index:03d}", target=target, operation=operation,
        requested_value=value, expected_state_version=version,
        timestamp=SIMULATION_EPOCH + timedelta(seconds=index),
    )


TESTBED_SCENARIOS = {
    "TB_PROCESS_01_NORMAL": TestbedScenario(
        "TB_PROCESS_01_NORMAL", "Start the normal cell and make valid adjustments.",
        (_command(1, ProcessAsset.PRODUCTION_CONTROLLER, ProcessOperation.START_ASSET, version=0),
         _command(2, ProcessAsset.MIXER, ProcessOperation.START_ASSET, version=1),
         _command(3, ProcessAsset.MIXER, ProcessOperation.SET_MIXER_SPEED_RPM, 900, 2),
         _command(4, ProcessAsset.PRODUCTION_CONTROLLER, ProcessOperation.SET_PRODUCTION_RATE_UNITS_PER_HOUR, 450, 3)),
    ),
    "TB_PROCESS_02_HIGH_OUTPUT": TestbedScenario(
        "TB_PROCESS_02_HIGH_OUTPUT", "Enter HIGH_OUTPUT from NORMAL.",
        (_command(1, ProcessAsset.PRODUCTION_CONTROLLER, ProcessOperation.CHANGE_OPERATING_MODE, OperatingMode.HIGH_OUTPUT, 0),),
    ),
    "TB_PROCESS_03_MAINTENANCE": TestbedScenario(
        "TB_PROCESS_03_MAINTENANCE", "Enter maintenance; production adjustment is restricted.",
        (_command(1, ProcessAsset.PRODUCTION_CONTROLLER, ProcessOperation.CHANGE_OPERATING_MODE, OperatingMode.MAINTENANCE, 0),
         _command(2, ProcessAsset.MIXER, ProcessOperation.START_ASSET, version=1)),
    ),
    "TB_PROCESS_04_OUT_OF_RANGE": TestbedScenario(
        "TB_PROCESS_04_OUT_OF_RANGE", "Attempt an unsafe mixer setpoint.",
        (_command(1, ProcessAsset.MIXER, ProcessOperation.SET_MIXER_SPEED_RPM, 5000, 0),),
    ),
    "TB_PROCESS_05_INVALID_TRANSITION": TestbedScenario(
        "TB_PROCESS_05_INVALID_TRANSITION", "Attempt HIGH_OUTPUT to MAINTENANCE directly.",
        (_command(1, ProcessAsset.PRODUCTION_CONTROLLER, ProcessOperation.CHANGE_OPERATING_MODE, OperatingMode.HIGH_OUTPUT, 0),
         _command(2, ProcessAsset.PRODUCTION_CONTROLLER, ProcessOperation.CHANGE_OPERATING_MODE, OperatingMode.MAINTENANCE, 1)),
    ),
    "TB_PROCESS_06_EMERGENCY_STOP": TestbedScenario(
        "TB_PROCESS_06_EMERGENCY_STOP", "Emergency stop then attempt a production command.",
        (_command(1, ProcessAsset.PRODUCTION_CONTROLLER, ProcessOperation.EMERGENCY_STOP, version=0),
         _command(2, ProcessAsset.MIXER, ProcessOperation.SET_MIXER_SPEED_RPM, 200, 1)),
    ),
    "TB_PROCESS_07_STALE_VERSION": TestbedScenario(
        "TB_PROCESS_07_STALE_VERSION", "Use a stale expected version after a successful mode transition.",
        (_command(1, ProcessAsset.PRODUCTION_CONTROLLER, ProcessOperation.CHANGE_OPERATING_MODE, OperatingMode.HIGH_OUTPUT, 0),
         _command(2, ProcessAsset.PRODUCTION_CONTROLLER, ProcessOperation.CHANGE_OPERATING_MODE, OperatingMode.NORMAL, 0)),
    ),
}
