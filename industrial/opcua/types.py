"""Typed integration contracts; these are not canonical TAIOS IndustrialEvents."""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Mapping


class ConnectionState(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"


class ObservationQuality(str, Enum):
    GOOD = "GOOD"
    UNCERTAIN = "UNCERTAIN"
    BAD = "BAD"


@dataclass(frozen=True)
class OpcUaObservation:
    endpoint: str
    namespace_uri: str
    asset: str
    node: str
    value: Any
    source_timestamp: datetime | None
    server_timestamp: datetime | None
    quality: ObservationQuality
    ingestion_timestamp: datetime


@dataclass(frozen=True)
class PlantObservations:
    endpoint: str
    namespace_uri: str
    values: Mapping[str, OpcUaObservation]
    source_timestamp: datetime | None
    state_version: int


@dataclass(frozen=True)
class OpcUaHealth:
    server_running: bool | None
    endpoint: str
    client_state: ConnectionState | None
    last_successful_read: datetime | None
    last_error: str | None
    reconnect_count: int


class OpcUaConnectionError(RuntimeError):
    """Controlled connection failure without process mutation."""


class OpcUaReadError(RuntimeError):
    """Controlled read failure without process mutation."""
