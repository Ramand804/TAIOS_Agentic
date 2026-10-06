# Industrial Testbed: Deterministic Software-Defined Manufacturing Cell

This package provides a **software-defined simulator**, intended to establish repeatable industrial process context before protocol adapters or a TAIOS execution gateway are considered. It is not a physical industrial process, a hardware controller, or a high-fidelity digital twin.

## Manufacturing cell

The simulated cell contains `PRODUCTION_CONTROLLER`, `MIXER`, `PUMP`, and `CONVEYOR`. It has no network connection, OPC UA server, MQTT broker, external API, or hardware interface.

`ProcessState` is immutable and contains a state for every asset; `MIXER` speed is in RPM, temperature is in Celsius, `PUMP` pressure is in bar and flow is in LPM, `CONVEYOR` speed is in m/s, and production rate is in units/hour. The deterministic model presently changes requested settings and derives pump pressure as flow × `pump_pressure_bar_per_lpm`; it intentionally does not simulate thermal or fluid dynamics.

## Commands and the safety boundary

`ProcessCommand` binds a command ID, target, operation, optional requested value, explicit timezone-aware timestamp, and optional expected state version. These IDs prepare a future execution gateway for idempotency; no durable idempotency ledger is implemented in this milestone.

`ManufacturingCell.apply(command)` is the sole public process-changing path. It validates every command through the independent non-AI `ProcessInterlock` before creating a new immutable state. Rejection returns the same state object/value and never advances `state_version`.

Supported operations are `START_ASSET`, `STOP_ASSET`, the four unit-specific setpoint operations, `CHANGE_OPERATING_MODE`, `REQUEST_SHUTDOWN`, `EMERGENCY_STOP`, and `RESET_EMERGENCY`. This command contract is simulator-only and is not TAIOS authorization or execution approval.

## Operating and machine transitions

Operating modes are `NORMAL`, `HIGH_OUTPUT`, `MAINTENANCE`, and `SHUTDOWN`:

| Current | Allowed next modes |
| --- | --- |
| NORMAL | HIGH_OUTPUT, MAINTENANCE, SHUTDOWN |
| HIGH_OUTPUT | NORMAL, SHUTDOWN |
| MAINTENANCE | NORMAL, SHUTDOWN |
| SHUTDOWN | none |

Asset starts require `STOPPED`; stops require `RUNNING`. The simulator uses explicit `STOPPED`, `STARTING`, `RUNNING`, `STOPPING`, `FAULT`, and `EMERGENCY_STOP` values, while currently exercising the deterministic STOPPED/RUNNING/emergency paths.

In `MAINTENANCE`, production adjustments and starts are rejected. Shutdown and stop operations remain available. `ProcessLimits` centralizes safe simulator defaults (rather than TAIOS scientific parameters): mixer 0–1800 RPM, pump 0–100 LPM / maximum 50 bar, conveyor 0–2.5 m/s, and production 0–1000 units/hour.

## Emergency behaviour and versioning

An emergency stop is always available. It sets every asset to `EMERGENCY_STOP`, sets all controllable outputs and production rate to zero, moves the process to `SHUTDOWN`, and marks `emergency_state=True`. All normal production-changing commands are rejected while that flag is active. Only an explicit `RESET_EMERGENCY` can clear it; reset brings all assets to STOPPED and returns the simulated mode to NORMAL. Every allowed command increments state version exactly once and records its supplied timestamp. A command with a stale expected version is rejected.

## Simulator-only scenarios

`industrial.testbed.scenarios` supplies `TB_PROCESS_01_NORMAL` through `TB_PROCESS_07_STALE_VERSION`. They are not TAIOS publication scenarios S1–S9 and do not alter frozen experiment artifacts.

## Limitations

This isolated testbed has no protocol security, certificates, persistence, durable command idempotency, authorization bridge, physical safety controller, or process/hardware validation. Those are intentionally outside Milestone 2.

## Local OPC UA representation (Milestone 3)

The local testbed exposes a read-only OPC UA representation through `asyncua==2.0`, an asyncio OPC UA client/server library supporting Python 3.10+. Its default endpoint is `opc.tcp://127.0.0.1:4840/taios/testbed/`, with namespace `urn:taios:industrial:testbed`. `OpcUaConfig` accepts only literal loopback addresses by default; a non-loopback bind needs explicit `allow_non_loopback=True`. No discovery or external connection is implemented.

The namespace contains `TAIOSFactory` with `ProductionController`, `Mixer`, `Pump`, `Conveyor`, and `Process` groups. Variables represent the immutable `ManufacturingCell` snapshot: machine states, setpoints/measurements, operating mode, flags, version, and source timestamp. The server has no independent process model: a controlled refresh loop reads `ManufacturingCell.state` and updates OPC UA variables from that one snapshot. Generic client writes are not exposed and OPC UA variables are not made writable.

Every client observation retains OPC UA source timestamp, server timestamp where supplied, status normalized as GOOD/UNCERTAIN/BAD, and a distinct client ingestion timestamp. The dedicated `Process.SourceTimestamp` represents the simulator timestamp. The client has explicit connection states and bounded reconnect attempts; read/connection failure returns typed integration exceptions without changing process state.

`DEVELOPMENT_LOCAL` is the only active security mode. `SECURE_CERTIFICATE` exists in configuration but is deliberately marked **PARTIAL** and fails startup until certificate provisioning and validation are designed. This server is a representation of software-defined simulated equipment only; it is not connected to PLCs, SCADA, or physical industrial equipment.

## Runtime gateway

Milestone 4 adds a protocol-neutral, non-executing industrial gateway. It synchronizes validated telemetry and creates `IndustrialRuntimeEvent` only for explicit command requests. It does not create frozen experiment events or invoke TAIOS.
