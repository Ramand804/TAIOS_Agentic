"""Typed command contract for the simulator only; it is not TAIOS authorization."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from industrial.process.enums import ProcessAsset, ProcessOperation
from industrial.process.state import SIMULATION_EPOCH, _timestamp


@dataclass(frozen=True)
class ProcessCommand:
    command_id: str
    target: ProcessAsset
    operation: ProcessOperation
    requested_value: Any = None
    timestamp: datetime = SIMULATION_EPOCH
    expected_state_version: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.command_id, str) or not self.command_id.strip():
            raise ValueError("command_id must be a non-empty string")
        object.__setattr__(self, "target", ProcessAsset(self.target))
        object.__setattr__(self, "operation", ProcessOperation(self.operation))
        object.__setattr__(self, "timestamp", _timestamp(self.timestamp))
        if self.expected_state_version is not None and (
            type(self.expected_state_version) is not int or self.expected_state_version < 0
        ):
            raise ValueError("expected_state_version must be a non-negative integer or None")
