<<<<<<< HEAD
# TAIOS

**TAIOS: An Agentic AI Operating System for Trust-Aware, Adaptive, and Explainable Autonomous Decision Intelligence in Industrial IoT**

This repository contains the Day 1B foundation:

- canonical IndustrialEvent model
- canonical DecisionRecord model
- virtual IIoT assets and identities
- deterministic scenario/event generator
- YAML configuration
- JSONL audit/event logging
- initial tests

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py --scenario S1 --events 20 --seed 42
pytest -q
```

Generated records are written under `logs/<experiment_id>/`:

- `experiment.json`: run inputs, asset/identity configuration snapshot, and SHA-256 event-stream fingerprint.
- `events.jsonl`: the complete validated event sequence. Repeating a run replaces this file rather than appending duplicates. Earlier flat logs are left untouched.

Generation is deterministic per call, including when reusing the same generator or orchestrator. The default simulated start is `2026-01-01T00:00:00+00:00`, with one second between events. Override these using `--simulation-start-time` (timezone required) and `--event-interval-seconds`.

Run identity includes scenario, seed, count, normalized start time, interval, generator version, and the ordered asset/identity configuration used by generation. Existing YAML files are not consumed by the scenario generator; this step does not introduce new configuration semantics. Bump `GENERATOR_VERSION` when changing generation rules.

Event sequences start at 1. Generated IDs and timestamps are deterministic; directly constructed `IndustrialEvent` objects retain their UUID and wall-clock defaults. `EventGenerator.generate(scenario_id, n)` and `Orchestrator.run_scenario(scenario_id, n)` still return event lists. An optional third `ExperimentRun` argument supplies generator context. `Orchestrator.event_logger` is available after a successful run, alongside `experiment` and `fingerprint`.

The stream fingerprint hashes ordered event content and deterministic experiment identity, excluding event IDs and standalone wall-clock timestamps while retaining simulated timestamps. Seed or configuration changes therefore alter the fingerprint even for scenarios without random draws.

## Core scenario IDs

- S1: normal operation
- S2: compromised device
- S3: credential compromise
- S4: conflicting evidence
- S5: concept drift
- S6: coordinated attack

## Day 1C Step 3: industrial state

`IndustrialState` separates dynamic context from the static asset registry. It defaults to ACTIVE/NORMAL, false maintenance/emergency flags, and registered assets in STOPPED/NORMAL state with unknown (`None`) current values. This default does not infer equipment operation from the plant's production label.

Use `set_production_state`, `set_operating_mode`, `set_maintenance_mode`, `set_emergency_state`, and `update_asset_state` for changes. A successful change increments the plant version once; an asset change also increments that asset's version once. No-op updates leave versions unchanged. Invalid values fail before mutation. Enum transitions are permitted between valid values; process interlocks and automatic coupling of maintenance/emergency flags are not implemented.

`snapshot(asset_id)` returns an immutable snapshot of plant context and the relevant asset. `snapshot()` includes all assets. `to_dict()` returns an independent JSON-compatible representation. No wall clock is used. `IndustrialEnvironment` remains as a compatibility facade with `snapshot()` returning a dictionary; its `state` now holds the validated model instead of an unrestricted dictionary.

`OperationalLimits` centralizes asset/operation/mode ranges. MOTOR-02 `set_speed` ranges are NORMAL 20–80, HIGH_OUTPUT 60–95, REDUCED 10–50, and MAINTENANCE 0–20, inclusive. Checks return `within_limit`, `minimum`, `maximum`, `requested_value`, and `deviation`. For request x and bounds L/U, deviation is `max(L-x, 0, x-U) / (U-L)`. For L=U the denominator is 1, giving absolute distance in the operation's units. Missing limits, unknown assets, invalid modes, and nonfinite values fail explicitly.

S5 changes NORMAL to HIGH_OUTPUT at one-based sequence `max(1, n // 2) + 1`, when that event exists. Ten events change at event 6; a single-event run has no change and records `regime_change_sequence: null`. Each event includes pre-command state context, the limit check, and the regime-change sequence. Both phases remain BENIGN/ALLOW. This does not execute the requested command or implement adaptation. Initial state and operational limits are included in experiment configuration; generator version is `day1c-step3-v1`.

## Day 1C Step 4: scenario manifests and provenance

Each experiment now saves deterministic `scenario_manifest.json` alongside its metadata and events. Manifests describe scenario design, labeling policy, affected assets, and ordered phases. The canonical `transition_sequence` is the first event in the new phase: event 6 for ten-event S2/S3/S5 runs and event 4 for S6. S1/S4 have no transition. Zero/one-event runs retain only their initial phase in generated events and record no realized transition (`null`); their manifest still names both designed phases where applicable.

Manifests drive generator boundaries and participate in experiment configuration. Generated events carry immutable `EventProvenance` with experiment/scenario/version identifiers, sequence, phase, transition type, and design-derived causal tags. The additional `total_events` field permits provenance validation against the canonical manifest even outside an orchestrator call. Causal tags describe experimental origin, not agent inference. Ground truth and expected actions remain separate labels.

`EventManager` checks provenance before logging, including sequence-specific phase and transition metadata. Standalone events may omit provenance; deterministic experiment events may not. JSON event reconstruction accepts provenance dictionaries. Provenance and manifests participate in reproducibility; generator version is now `day1c-step4-v1`. Existing Step 3 snapshots and label semantics are preserved. One-event S2 runs now record `compromise_event: null` rather than pointing to a nonexistent event 2.
=======
# TAIOS_Agentic
An Agentic AI Operating System for Trust-Aware, Adaptive, and Explainable Autonomous Decision Intelligence in Industrial IoT
>>>>>>> origin/main
