import asyncio
from datetime import timedelta
from pathlib import Path
import socket

import pytest

from industrial.opcua.client import OpcUaTestbedClient
from industrial.opcua.config import OpcUaConfig, OpcUaSecurityMode
from industrial.opcua.server import OpcUaTestbedServer
from industrial.opcua.types import ConnectionState, ObservationQuality, OpcUaConnectionError, OpcUaReadError
from industrial.process.commands import ProcessCommand
from industrial.process.enums import InterlockStatus, MachineState, ProcessAsset, ProcessOperation
from industrial.process.model import ManufacturingCell
from industrial.process.state import SIMULATION_EPOCH


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def config(port=None, **changes):
    return OpcUaConfig(port=free_port() if port is None else port, synchronization_interval_seconds=0.005, **changes)


def run(coro):
    return asyncio.run(coro)


async def with_server(check):
    cell = ManufacturingCell()
    cfg = config()
    server = OpcUaTestbedServer(cell, cfg)
    await server.start()
    client = OpcUaTestbedClient(cfg)
    try:
        await client.connect()
        await check(cell, server, client)
    finally:
        await client.disconnect()
        await server.stop()


def test_opcua_server_start_stop_and_loopback_default():
    async def check(cell, server, client):
        assert server.running
        assert server.endpoint.startswith("opc.tcp://127.0.0.1:")
        assert client.connection_state is ConnectionState.CONNECTED
    run(with_server(check))


def test_opcua_config_rejects_unsafe_default_and_certificate_is_partial():
    with pytest.raises(ValueError):
        OpcUaConfig(host="192.168.1.20")
    cfg = config(security_mode=OpcUaSecurityMode.SECURE_CERTIFICATE)
    with pytest.raises(NotImplementedError):
        run(OpcUaTestbedServer(ManufacturingCell(), cfg).start())


def test_opcua_namespace_and_read_full_state():
    async def check(cell, server, client):
        state = await client.read_full_state()
        assert state.namespace_uri == "urn:taios:industrial:testbed"
        assert state.state_version == 0
        assert state.values["Process.OperatingMode"].value == "NORMAL"
        assert state.source_timestamp == SIMULATION_EPOCH
    run(with_server(check))


@pytest.mark.parametrize(("asset", "expected_nodes"), [
    ("Mixer", {"Mixer.MachineState", "Mixer.SpeedRPM", "Mixer.TemperatureCelsius"}),
    ("Pump", {"Pump.MachineState", "Pump.PressureBar", "Pump.FlowRateLPM"}),
    ("Conveyor", {"Conveyor.MachineState", "Conveyor.SpeedMPS"}),
])
def test_opcua_read_individual_assets(asset, expected_nodes):
    async def check(cell, server, client):
        values = await client.read_asset(asset)
        assert set(values) == expected_nodes
        assert all(item.quality is ObservationQuality.GOOD for item in values.values())
    run(with_server(check))


def test_opcua_state_version_timestamp_quality_and_server_sync():
    async def check(cell, server, client):
        before = await client.read_full_state()
        command = ProcessCommand(
            command_id="opcua-sync-1", target=ProcessAsset.MIXER, operation=ProcessOperation.START_ASSET,
            expected_state_version=0, timestamp=SIMULATION_EPOCH + timedelta(seconds=1),
        )
        assert cell.apply(command).interlock.status is InterlockStatus.ALLOWED
        await asyncio.sleep(server.config.synchronization_interval_seconds * 3)
        after = await client.read_full_state()
        assert after.state_version == before.state_version + 1
        assert after.source_timestamp == command.timestamp
        assert after.values["Mixer.MachineState"].value == MachineState.RUNNING.value
        state_node = after.values["Process.StateVersion"]
        assert state_node.quality is ObservationQuality.GOOD
        assert state_node.source_timestamp is not None
        assert state_node.ingestion_timestamp >= state_node.source_timestamp
    run(with_server(check))


def test_opcua_disconnect_and_read_after_disconnect_is_controlled():
    async def check(cell, server, client):
        await client.disconnect()
        assert client.connection_state is ConnectionState.DISCONNECTED
        with pytest.raises(OpcUaReadError):
            await client.read_full_state()
    run(with_server(check))


def test_opcua_reconnect_and_bounded_exhaustion_do_not_mutate_process():
    async def check(cell, server, client):
        before = cell.state
        assert await client.reconnect()
        assert client.connection_state is ConnectionState.CONNECTED
        await server.stop()
        assert not await client.reconnect()
        assert client.connection_state is ConnectionState.FAILED
        assert client.reconnect_count >= server.config.reconnect_attempts
        assert cell.state == before
    run(with_server(check))


def test_server_shutdown_while_connected_is_a_controlled_read_failure():
    async def check(cell, server, client):
        before = cell.state
        await server.stop()
        with pytest.raises(OpcUaReadError):
            await client.read_full_state()
        assert client.connection_state is ConnectionState.DEGRADED
        assert cell.state == before
    run(with_server(check))


def test_server_unavailable_connection_refused_is_typed():
    async def check():
        client = OpcUaTestbedClient(config())
        with pytest.raises(OpcUaConnectionError):
            await client.connect()
        assert client.connection_state is ConnectionState.FAILED
    run(check())


def test_no_generic_process_write_client_api_or_taios_pipeline_import():
    client = OpcUaTestbedClient(config())
    assert not any(hasattr(client, name) for name in ("write", "set_speed", "set_pressure", "set_production_rate", "apply"))
    source = Path("industrial/opcua").read_text() if False else "\n".join(path.read_text() for path in Path("industrial/opcua").glob("*.py"))
    assert "TAIOSPipeline" not in source
    assert "process_event(" not in source


def test_opcua_nodes_are_explicitly_read_only_and_server_health_is_exposed():
    async def check(cell, server, client):
        assert server.health().server_running is True
        node = client._client.get_node(f"ns={client._namespace_index};s=Mixer.SpeedRPM")
        with pytest.raises(Exception):
            await node.write_value(123.0)
        assert cell.state.mixer_speed_rpm == 0.0
    run(with_server(check))
