# Industrial runtime gateway

`IndustrialRuntimeEvent` is the runtime/testbed decision-input contract. The frozen `environment.event.IndustrialEvent` remains the experiment, replay, and publication contract. They are deliberately not interchangeable: **ground truth belongs to the evaluator, not the autonomous decision system**, and scenario identity cannot substitute for runtime security evidence.

The protocol-neutral gateway accepts `IndustrialObservation` for state synchronization only and `IndustrialCommandRequest` for explicit runtime event normalization. It has quality gates (`GOOD`, `UNCERTAIN`, `BAD`), freshness gates (`FRESH`, `STALE`, `FUTURE_TIMESTAMP`, `TIMESTAMP_MISSING`), state-version consistency checks, and a separate industrial registry. Telemetry never produces a decision event. The OPC UA adapter converts only typed observations; raw asyncua values never leave the protocol layer. No pipeline, process write, or scientific state mutation occurs here.

The V1 registry is controlled research-scenario metadata. The industrial registry holds only the software-defined testbed assets and no evaluator labels.
