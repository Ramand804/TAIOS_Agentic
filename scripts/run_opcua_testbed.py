"""Local read-only OPC UA demonstration for the software-defined testbed."""
import asyncio

from industrial.opcua import OpcUaTestbedClient, OpcUaTestbedServer
from industrial.process import ManufacturingCell


async def main() -> None:
    cell = ManufacturingCell()
    server = OpcUaTestbedServer(cell)
    client = OpcUaTestbedClient(server.config)
    await server.start()
    try:
        await client.connect()
        observations = await client.read_full_state()
        print({key: value.value for key, value in observations.values.items()})
    finally:
        await client.disconnect()
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
