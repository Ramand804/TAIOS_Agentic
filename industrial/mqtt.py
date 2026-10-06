"""Fail-closed MQTT ingestion adapter; it never performs industrial writes."""
from dataclasses import dataclass
from enum import Enum
import json


class MqttIngestStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    INVALID_TOPIC = "INVALID_TOPIC"
    MALFORMED_PAYLOAD = "MALFORMED_PAYLOAD"
    DISCONNECTED = "DISCONNECTED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class MqttIngestResult:
    status: MqttIngestStatus
    detail: str
    gateway_result: object | None = None


class MqttIndustrialAdapter:
    """Maps a bounded command topic to the existing read/validation gateway."""
    command_topic = "taios/industrial/commands"

    def __init__(self, gateway):
        self._gateway = gateway
        self._connected = False

    def set_connected(self, connected: bool):
        self._connected = bool(connected)

    def ingest(self, topic: str, payload: bytes | str):
        if not self._connected:
            return MqttIngestResult(MqttIngestStatus.DISCONNECTED, "MQTT adapter is disconnected")
        if topic != self.command_topic:
            return MqttIngestResult(MqttIngestStatus.INVALID_TOPIC, "Topic is not an accepted command topic")
        try:
            decoded = json.loads(payload.decode() if isinstance(payload, bytes) else payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return MqttIngestResult(MqttIngestStatus.MALFORMED_PAYLOAD, "Payload is not valid JSON")
        from industrial.gateway.types import IndustrialCommandRequest
        try:
            request = IndustrialCommandRequest(**decoded)
        except (TypeError, ValueError):
            return MqttIngestResult(MqttIngestStatus.MALFORMED_PAYLOAD, "Payload does not match command schema")
        result = self._gateway.ingest_command(request)
        return MqttIngestResult(
            MqttIngestStatus.ACCEPTED if result.accepted else MqttIngestStatus.REJECTED,
            result.reason.value,
            result,
        )
