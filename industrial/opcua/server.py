"""Async local OPC UA server reflecting, never owning, ManufacturingCell state."""
import asyncio
from contextlib import suppress

from asyncua import Server, ua

from industrial.opcua.config import OpcUaConfig, OpcUaSecurityMode
from industrial.opcua.mapper import state_values
from industrial.opcua.namespace import FACTORY, NODES
from industrial.process.model import ManufacturingCell


class OpcUaTestbedServer:
    """Read-only local OPC UA projection with controlled snapshot synchronization."""

    def __init__(self, cell: ManufacturingCell, config: OpcUaConfig | None = None) -> None:
        self.cell = cell
        self.config = config or OpcUaConfig()
        self._server = Server()
        self._namespace_index: int | None = None
        self._nodes: dict[str, object] = {}
        self._refresh_task: asyncio.Task | None = None
        self._running = False

    @property
    def endpoint(self) -> str:
        return self.config.endpoint

    @property
    def running(self) -> bool:
        return self._running

    @property
    def namespace_index(self) -> int | None:
        return self._namespace_index

    async def start(self) -> None:
        if self._running:
            return
        if self.config.security_mode is OpcUaSecurityMode.SECURE_CERTIFICATE:
            raise NotImplementedError("certificate security is not implemented for this local testbed")
        await self._server.init()
        self._server.set_endpoint(self.endpoint)
        self._server.set_server_name("TAIOS Software-Defined Testbed")
        self._namespace_index = await self._server.register_namespace(self.config.namespace_uri)
        await self._create_read_only_namespace()
        await self.synchronize()
        await self._server.start()
        self._running = True
        self._refresh_task = asyncio.create_task(self._refresh_loop())

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._refresh_task is not None:
            self._refresh_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._refresh_task
            self._refresh_task = None
        await self._server.stop()

    def health(self):
        from industrial.opcua.types import OpcUaHealth
        return OpcUaHealth(self._running, self.endpoint, None, None, None, 0)

    async def _create_read_only_namespace(self) -> None:
        assert self._namespace_index is not None
        index = self._namespace_index
        factory = await self._server.nodes.objects.add_object(ua.NodeId(FACTORY, index), FACTORY)
        groups: dict[str, object] = {}
        for group, _ in NODES.values():
            if group not in groups:
                groups[group] = await factory.add_object(ua.NodeId(group, index), group)
        for key, (group, name) in NODES.items():
            node = await groups[group].add_variable(ua.NodeId(key, index), name, state_values(self.cell.state)[key])
            await node.set_writable(False)
            self._nodes[key] = node

    async def synchronize(self) -> None:
        """Refresh variables from one authoritative immutable cell snapshot."""
        values = state_values(self.cell.state)
        for key, node in self._nodes.items():
            await node.write_value(values[key])

    async def _refresh_loop(self) -> None:
        while self._running:
            await asyncio.sleep(self.config.synchronization_interval_seconds)
            await self.synchronize()
