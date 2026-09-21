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
