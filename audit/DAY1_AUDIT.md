# Final Day 1 audit — 2026-09-22

Recommendation: **READY_TO_FREEZE_DAY1**, for the deterministic synthetic experimental foundation. This is not evidence of detector accuracy, calibrated risk, physical-plant fidelity, or readiness for autonomous execution. No Day 2 components were implemented. Commit the reviewed audit changes before creating a baseline tag; this audit did not commit or tag files.

## Observed checks

| Area | Result | Evidence / scope |
|---|---|---|
| Architecture boundaries | PASS | Environment defines scenarios; core generates, validates and logs. Future-component modules remain placeholders. No inference/decision execution is called. |
| Label-leakage protection | PASS | Explicit allowlisted `runtime_observation` excludes labels, phase/provenance, synthetic scores and arbitrary context; six scenario regression cases verify exclusion. Full event records remain evaluation artifacts. |
| Scenario semantics | PASS | S1–S6 inspected and exercised at n=1,2,3,10; labels and phase boundaries checked. |
| Reproducibility | PASS | 78 separate CLI executions: each of 24 scenario/count combinations repeated across paths/hash seeds and in place; six additional seed-123 runs. All required artifact bytes matched; seed changes altered IDs/fingerprints. |
| Industrial-state integrity | PASS | Existing state/version/snapshot/limit tests pass; S5 smoke checks agree with manifest boundaries. |
| Provenance integrity | PASS | Existing tests plus corrupted-batch, timestamp, ID and missing-provenance tests pass after fixes. |
| Deterministic logging | PASS | experiment.json, scenario_manifest.json, events.jsonl match byte for byte on repeats; counts remain exact. |
| Repository cleanliness | PASS (artifact hygiene) | No tracked logs, caches, .venv or .pyc; no tracked file above 1 MB; git diff --check clean. Working tree has intentional uncommitted audit changes listed below. |

Baseline: **149 passed**. Final `python -m pytest -q`: **162 passed in 0.26s; 0 failed**. Interpreter: **Python 3.14.4** from the project virtual environment. All project Python source files parsed successfully after syntax repairs. Scenario version and generator version: **day1c-step4-v1**. Audit validation/helper changes do not alter valid generated event content, so generation versions were retained.

Reproducible smoke runner: `audit/verify_day1.py`. Observed per-scenario IDs/fingerprints: `audit/smoke_results.json`. The runner creates temporary experiment directories and removes only those directories on completion; existing research logs were not deleted.

## Dependency and leakage trace

Environment generation/provenance depends on `core.experiment`, a plain deterministic run/hash model. Core orchestration depends on environment generation and validation. There is no module import cycle in these paths. Future-agent directories have no imports or working reasoning logic. `DecisionRecord` contains reserved result fields but is not instantiated by the current orchestration pipeline. `MessageBus` and generic `StateManager` are unused scaffolding, not agent implementations. Static registry fields are absent from mutable asset state. Limits are defined centrally by `OperationalLimits`.

Uses of ground_truth/expected_safe_action are scenario assignment, structural validation, serialization/fingerprinting, and tests. Manifest labeling policies describe experimental design. Provenance phases and tags are assigned by manifests and validated; they are not used by any simulated decision-maker. No current decision-maker exists. The pre-audit full-event interface nevertheless exposed privileged labels; future consumers must use the new observable projection, not raw events or `to_dict()`.

| Classification | Fields / handling |
|---|---|
| Runtime-observable inputs | Source/target IDs and types, identity ID, event type, operation, requested value, network zone, protocol, authentication result, registered target criticality. Production state and operating mode are included only as validated observable context. |
| Simulator/context metadata | Experiment/scenario IDs and versions; event ID, sequence, simulated timestamp; provenance, phase, causal tags, transition type/sequence; compromise/drift flags, new_operating_regime, coordination_group, valid_credentials fixture; full snapshots, operational-limit results; synthetic anomaly_score, prior_device_trust and simulated_attack_probability. These remain in research logs and are excluded from the runtime projection. Selected legitimate context could be exposed later only through explicit reviewed fields. |
| Evaluation-only labels | ground_truth, expected_safe_action, and manifest ground_truth_policy. Retained for evaluation; never included in runtime inputs. |

The projection is an API boundary and tested allowlist, not a security sandbox preventing Python callers from deliberately accessing raw records. It defaults to excluding new context fields. Synthetic scores must not be silently reclassified as measured/model-derived features. True command values can naturally correlate with experimental labels; that does not justify exposing privileged phase or label fields.

## Scenario review

- S1: all BENIGN/ALLOW, no transition; empty affected_entities means no designated intervention, not an assertion that no assets participate.
- S2: PLC-07 to MOTOR-02, first post-compromise event uses malicious/BLOCK labels; no nonexistent compromise event in n=1.
- S3: HMI-02 writes to PLC-03 under operator-01; authentication remains successful while requested behavior changes. Assets are manifest entities; identity is recorded in event content.
- S4: conflicting fixture evidence, SUSPICIOUS/REQUEST_APPROVAL labels. Values 0.91/0.76 are configured synthetic evidence, not Trust/Risk outputs.
- S5: NORMAL to HIGH_OUTPUT; all BENIGN/ALLOW and speeds within their mode-specific limits. Snapshots are pre-command; no execution or adaptation occurs.
- S6: designated attacking HMI-02, PLC-04 and SERVICE-03 target PLC-03; random normal pre-phase assets need not be designated attackers. Short runs may not sample all three attackers; the manifest describes the designed population.

For n=1, no realized transition. S2/S3/S5 transitions for n=2,3,10 are 2,2,6. S6 transitions are 2,2,4. No transition references an absent event.

## Configuration and scientific assumptions

All five YAML files were inspected. They are currently not loaded by generation or orchestration. `trust.yaml`, `risk.yaml` and `policies.yaml` are intentionally reserved for future work; enabled policy flags currently have no execution effect. Do not activate them as part of Day 1.

`system.yaml` contains unused system/version/action/logging defaults. Its version 0.1.0 is not the generator version. Action names are duplicated in the event and decision schemas and the YAML list; they currently agree. Seed 42 is repeated as an API/CLI/default YAML value. `experiments.yaml` default count 100 differs from CLI default 20; these are presently separate, unused batch defaults. Its S5 name `concept_drift` is a legacy descriptive alias; the authoritative manifest names it `legitimate_regime_change`. These settings are documented rather than newly wired into execution.

Code-level research assumptions include midpoint transitions (one-third for S6), uniform integer request ranges, fixed anomaly-score fixtures, S3 benign/abnormal register values 55/999, S4 request 84, S6 attack values 900–999, fixed identities, labels and expected actions. These are synthetic scenario design, not empirically calibrated relationships. Generation-rule edits require a generator-version bump. Asset/identity models, initial industrial state, operational limits and manifests participate in run configuration. MOTOR-02 operating limits are centralized; no PUMP-01 policy is claimed. Current unitless set_speed values are simulator units, not validated physical RPM.

## Bugs fixed and coverage added

1. Nine placeholder modules contained literal backslash-n text and failed Python parsing. Converted only those escapes to real newlines; placeholders remain unimplemented.
2. No label-safe consumer API existed. Added an explicit observable-field projection and scenario-wide regression checks; no agent built.
3. EventManager accepted incomplete/duplicate batches and could accept stripped provenance when an experiment context was supplied. Added exact count/order checks and mandatory provenance in experiment mode.
4. Provenance validation did not bind event ID/timestamp to the supplied run. Added deterministic metadata/scenario checks.
5. ExperimentRun's nested configuration remained mutable after its ID was computed. Added identity-consistency validation at generation and experiment-batch acceptance; mutated configurations now fail explicitly. Also reject non-integer run seeds/counts.

New tests target these actual gaps; previous tests were retained. Smoke checks independently cover all short-run label/phase semantics, cross-process hash-seed/path independence and byte-stable reruns.

## Files and Git status

Modified (13):

- adaptation/feedback.py
- agents/base_agent.py
- baselines/rule_based.py
- core/event_manager.py
- core/experiment.py
- environment/event_generator.py
- environment/provenance.py
- evaluation/metrics.py
- experiments/run_all.py
- explainability/decision_trace.py
- governance/policy_engine.py
- intelligence/threat_detector.py
- memory/episodic_memory.py

Added:

- core/runtime_inputs.py
- tests/test_day1_audit.py
- audit/verify_day1.py
- audit/smoke_results.json
- audit/DAY1_AUDIT.md

Initial working tree was clean. Final status has the 13 modifications above plus untracked `audit/`, `core/runtime_inputs.py`, and `tests/test_day1_audit.py`. No unrelated source changes or tracked generated artifacts were found. `.gitignore` excludes .venv, caches, bytecode, logs and designated model binaries; generated files remain on disk but ignored. The small smoke-results JSON is intentionally retained audit evidence, not a full experiment log. No Git commit/tag was created during this audit.

## Deliberately deferred limitations

No agent inference, governance/execution, adaptive learning, memory, model calibration, evaluation metrics or physical-process simulation. State flags are independent validated context rather than process interlocks. Experiment records retain full evaluation data; safe consumer access requires the allowlisted projection. Valid-run determinism is verified on Python 3.14.4, not promised across all future interpreter versions. Event-file replacement is atomic, but the three-file artifact set is not a transactional crash-recovery database; concurrent writers and mid-write crash recovery are outside this single-process Day 1 scope. Historical logs remain historical and are not migrated automatically. Empty streams share the same content fingerprint while their run IDs still distinguish configuration.

No known correctness issue remains in the tested Day 1 scope. **READY_TO_FREEZE_DAY1**.
