# Industrial Operations Boundary

The industrial testbed is a software-defined simulator. Its lifecycle assesses a validated industrial runtime event, records an authoritative transaction, produces a non-executable shadow decision, and registers an industrial governance decision. It does not call the frozen research pipeline or expose evaluator-only labels.

A process-changing operation requires the separate path: authoritative governance record, required human review, opaque one-shot capability, capability execution gateway, and the independent `ManufacturingCell` interlock. The default mode is `SIMULATION`; `SHADOW` also cannot issue mutating capabilities. `SUPERVISED` requires a bound approved review. `CONTROLLED_EXECUTION` uses the same capability and interlock path under trusted runtime configuration.

Production industrial code has one `ManufacturingCell.apply()` call site: `industrial/capabilities.py`, inside `CapabilityExecutionGateway`. Direct simulator mutation in `tests/industrial` and the local OPC UA fixture is testbed-only and is not an industrial runtime authority path. MQTT performs bounded ingestion only; it has no write or execution operation. The read model exposes health and evidence only.

The design is application-level single-process authority separation, not a hardware safety certification or a real deployment claim.
