"""Deterministic experiment identity, simulation clock, and stream hashing."""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from typing import Any

DEFAULT_SIMULATION_START = "2026-01-01T00:00:00+00:00"
GENERATOR_VERSION = "day1c-step4-v1"
OBSERVABLE_GENERATOR_VERSION = "day2c5-observable-v1"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ExperimentRun:
    scenario_id: str
    seed: int
    total_events: int
    simulation_start_time: str = DEFAULT_SIMULATION_START
    generator_version: str = GENERATOR_VERSION
    event_interval_seconds: float = 1.0
    configuration: dict = field(default_factory=dict)
    experiment_id: str = field(init=False)

    def __post_init__(self):
        if self.scenario_id not in {f"S{i}" for i in range(1, 7)}:
            raise ValueError(f"Unknown scenario: {self.scenario_id}")
        if type(self.seed) is not int:
            raise ValueError("seed must be an integer")
        if type(self.total_events) is not int or self.total_events < 0:
            raise ValueError("total_events must be nonnegative")
        start = datetime.fromisoformat(self.simulation_start_time)
        if start.tzinfo is None or start.utcoffset() is None:
            raise ValueError("simulation_start_time must include a timezone")
        interval = float(self.event_interval_seconds)
        if not math.isfinite(interval) or interval <= 0 or timedelta(seconds=interval) <= timedelta(0):
            raise ValueError("event_interval_seconds must be positive and at least one microsecond")
        object.__setattr__(self, "simulation_start_time", start.astimezone(timezone.utc).isoformat())
        object.__setattr__(self, "event_interval_seconds", interval)
        # Snapshot inputs so later mutation of the caller's dict cannot change this run.
        object.__setattr__(self, "configuration", json.loads(canonical_json(self.configuration)))
        identity = {k: getattr(self, k) for k in (
            "scenario_id", "seed", "total_events", "simulation_start_time",
            "generator_version", "event_interval_seconds", "configuration")}
        object.__setattr__(self, "experiment_id",
                           f"EXP-{self.scenario_id}-{self.seed}-{self.total_events}-{fingerprint(identity)[:16]}")

    def validate_identity(self):
        identity = self.to_dict()
        identity.pop("experiment_id")
        expected = f"EXP-{self.scenario_id}-{self.seed}-{self.total_events}-{fingerprint(identity)[:16]}"
        if expected != self.experiment_id:
            raise ValueError("Experiment configuration changed after identity creation")
        return True

    def event_metadata(self, sequence_number: int) -> dict:
        if not 1 <= sequence_number <= self.total_events:
            raise ValueError("sequence_number is outside the experiment")
        timestamp = datetime.fromisoformat(self.simulation_start_time) + (
            timedelta(seconds=self.event_interval_seconds) * (sequence_number - 1))
        return {"experiment_id": self.experiment_id, "sequence_number": sequence_number,
                "event_id": f"{self.experiment_id}-E{sequence_number:06d}",
                "timestamp": timestamp.isoformat()}

    def to_dict(self) -> dict:
        return asdict(self)


def event_stream_fingerprint(events) -> str:
    """Hash ordered research content and deterministic experiment provenance.

    Simulated timestamps and sequence numbers are research content and are retained.
    Runtime metadata added to persistence envelopes is not part of this projection.
    """
    content = []
    for event in events:
        row = event.to_dict()
        deterministic = row.get("experiment_id") is not None
        row.pop("event_id", None)
        if not deterministic:
            row.pop("experiment_id", None)
            row.pop("timestamp", None)
        content.append(row)
    return fingerprint(content)
