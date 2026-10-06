"""Read-only async client for the local software-defined OPC UA testbed."""
import asyncio
from datetime import datetime, timezone

from asyncua import Client, ua

from industrial.opcua.config import OpcUaConfig
from industrial.opcua.namespace import NODES
from industrial.opcua.types import (
    ConnectionState, ObservationQuality, OpcUaConnectionError, OpcUaHealth,
    OpcUaObservation, OpcUaReadError, PlantObservations,
)


def _utc(value):
    if value is None:
        return None
    return value.astimezone(timezone.utc) if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _quality(status_code) -> ObservationQuality:
    if status_code.is_good():
        return ObservationQuality.GOOD
    if status_code.is_uncertain():
        return ObservationQuality.UNCERTAIN
    return ObservationQuality.BAD


class OpcUaTestbedClient:
    """No process-write methods are exposed; this client only obtains observations."""

    def __init__(self, config: OpcUaConfig | None = None) -> None:
        self.config = config or OpcUaConfig()
        self._client: Client | None = None
        self._namespace_index: int | None = None
        self.connection_state = ConnectionState.DISCONNECTED
        self.last_successful_read: datetime | None = None
        self.last_error: str | None = None
        self.reconnect_count = 0

    async def connect(self) -> None:
        if self.connection_state is ConnectionState.CONNECTED:
            return
        self.connection_state = ConnectionState.CONNECTING
        self._client = Client(url=self.config.endpoint, timeout=self.config.connection_timeout_seconds)
        try:
            await self._client.connect()
            self._namespace_index = await self._client.get_namespace_index(self.config.namespace_uri)
        except Exception as exc:
            self.connection_state = ConnectionState.FAILED
            self.last_error = f"{type(exc).__name__}: {exc}"
            self._client = None
            raise OpcUaConnectionError("unable to connect to configured OPC UA endpoint") from exc
        self.connection_state = ConnectionState.CONNECTED
        self.last_error = None

    async def disconnect(self) -> None:
        client, self._client = self._client, None
        self._namespace_index = None
        if client is not None:
            try:
                await client.disconnect()
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
        self.connection_state = ConnectionState.DISCONNECTED

    async def reconnect(self) -> bool:
        await self.disconnect()
        for attempt in range(self.config.reconnect_attempts):
            self.reconnect_count += 1
            try:
                await self.connect()
                return True
            except OpcUaConnectionError:
                if attempt + 1 < self.config.reconnect_attempts:
                    await asyncio.sleep(self.config.reconnect_delay_seconds)
        self.connection_state = ConnectionState.FAILED
        return False

    async def read_full_state(self) -> PlantObservations:
        values = {key: await self._read_node(key, group) for key, group in NODES.items()}
        source = values["Process.SourceTimestamp"].value
        if not isinstance(source, datetime):
            raise OpcUaReadError("process source timestamp did not decode as datetime")
        state_version = values["Process.StateVersion"].value
        if isinstance(state_version, bool) or not isinstance(state_version, int):
            raise OpcUaReadError("process state version did not decode as integer")
        return PlantObservations(self.config.endpoint, self.config.namespace_uri, values, _utc(source), state_version)

    async def read_asset(self, asset: str) -> dict[str, OpcUaObservation]:
        prefix = f"{asset}."
        selected = {key: path for key, path in NODES.items() if key.startswith(prefix)}
        if not selected:
            raise ValueError(f"unknown exposed asset: {asset}")
        return {key: await self._read_node(key, path) for key, path in selected.items()}

    async def _read_node(self, key: str, path: tuple[str, str]) -> OpcUaObservation:
        if self.connection_state is not ConnectionState.CONNECTED or self._client is None or self._namespace_index is None:
            raise OpcUaReadError("client is not connected")
        try:
            node = self._client.get_node(ua.NodeId(key, self._namespace_index))
            data_value = await asyncio.wait_for(node.read_data_value(), timeout=self.config.read_timeout_seconds)
        except Exception as exc:
            self.connection_state = ConnectionState.DEGRADED
            self.last_error = f"{type(exc).__name__}: {exc}"
            raise OpcUaReadError(f"unable to read OPC UA node {key}") from exc
        observed = OpcUaObservation(
            endpoint=self.config.endpoint, namespace_uri=self.config.namespace_uri,
            asset=path[0], node=key, value=data_value.Value.Value,
            source_timestamp=_utc(data_value.SourceTimestamp), server_timestamp=_utc(data_value.ServerTimestamp),
            quality=_quality(data_value.StatusCode), ingestion_timestamp=datetime.now(timezone.utc),
        )
        self.last_successful_read = observed.ingestion_timestamp
        self.last_error = None
        return observed

    def health(self) -> OpcUaHealth:
        return OpcUaHealth(None, self.config.endpoint, self.connection_state, self.last_successful_read, self.last_error, self.reconnect_count)
