# Day 2C.5 — observable evidence coverage

## Scope and compatibility

This task audits semantic coverage and adds an explicit, versioned observable-state generation profile. No trust mathematics, evidence strengths, weights, learning/recovery rates, recency, aggregation or composite formula changed. No agents or authorization policies were added.

Frozen generation remains the default (`day1c-step4-v1`). Enable the enriched profile through `EventGenerator(observable_state=True)`, `Orchestrator(observable_state=True)`, or:

```bash
python main.py --scenario S2 --events 10 --seed 42 --observable-state
```

Enriched runs use `day2c5-observable-v1` and record `observable_state: true` in experiment configuration. Their IDs/log directories are distinct; frozen datasets are not silently rewritten. This explicit profile preserves all 246 pre-existing tests, including assertions that the frozen S2 dataset lacks mode. Provenance accepts both supported generation versions and retains exact version checks against supplied experiment context.

## Original S2 gap and justified enrichment

S2 requests PLC-07 -> MOTOR-02 `set_speed`, with authentication true, production ACTIVE, normal requests 40–70 and later requests 90–120. Previously its event context did not contain operating_mode or a state snapshot. The existing projection already accepts operating_mode, so the omission was in generation, not a projection blacklist.

A subtle distinction: old S2 did not instantiate live IndustrialState. Its experiment configuration already declared the shared initial IndustrialState ACTIVE/NORMAL, but emitted events omitted that state. The new profile materializes this declared initial state once per generation, records target-specific immutable snapshots, and derives production_state/operating_mode from those snapshots. No S2-specific mode branch or inference fallback exists. The common event constructor applies this to all scenarios. Generation resets the state each call.

This is a simulator assumption made explicit, not a claim that physical telemetry proved NORMAL. ACTIVE alone does not imply NORMAL. The justification is the repository's existing initial state and S2's unchanged operating regime, not a desire for falling trust. Central MOTOR-02 limits remain NORMAL 20–80, HIGH_OUTPUT 60–95, REDUCED 10–50, MAINTENANCE 0–20. No new numerical limits were introduced.

## S3 audit and deliberately unresolved rule gap

S3 uses HMI-02 -> PLC-03, identity operator-01, operation write_register, values 55/999, authentication true and production ACTIVE. The new general profile records NORMAL from the same initial state. There is still no register address, units, control meaning, permissible range, or authorized operation/role matrix. The identity registry supplies roles but no permissions. Thus no observable industrial rule establishes that 999 is invalid.

The smallest defensible future addition would require a specified register/address/value domain or an independently justified role-operation policy. Neither can be derived scientifically from these two values or labels. A policy banning operator register writes would also ban both phases, not explain a transition; introducing it here would be an unsupported assumption. No S3 policy or negative evidence is manufactured. Identity evidence stays positive and behavior stays neutral with MISSING_LIMIT. This task explicitly leaves the coverage issue unresolved.

## S5 safeguard

S5 uses the same live state object as the enriched common event constructor. Its existing NORMAL -> HIGH_OUTPUT transition updates that object before the event snapshot. There is no stale NORMAL overlay. Requests 85 in HIGH_OUTPUT are checked against 60–95, not 20–80. The original S5 transition and generated request sequence are unchanged. A regression test also runs S5 followed by S2 on the same generator to verify state resets instead of leaking HIGH_OUTPUT between runs.

## Boundary and generality

Neither runtime_observation nor TrustEvidenceExtractor changed. Only the already-approved production_state and operating_mode pass through the projection; full snapshots remain privileged simulator context. Scenario ID, labels, provenance, phase, causal tags, anomaly scores and transitions never reach inference. Standalone safe dictionaries exercise the same rule: speed 90 under NORMAL is negative, while the same speed under HIGH_OUTPUT is positive. No TrustModel component branches on scenario or event 6.

New leakage tests alter ground_truth, expected_safe_action, provenance, scenario ID and hidden context hints while keeping observable state fixed; extraction is unchanged. All original leakage tests still pass. The model receives uncorrelated evidence and opaque delivery ordering as before.

## Observed seed-42 diagnostic trajectories

These results use the enriched profile, ten events and a fresh unchanged TrustModel per scenario. Event numbers/scenario names below are evaluation annotations only. Production state is ACTIVE throughout. Identity and device evidence are POSITIVE with effective magnitude .05 at every listed event; context remains NEUTRAL because there is no independent context rule. Behavior magnitude is strength times confidence, not trust itself.

| Scenario/event | Operation/value | Mode | Behavior | Effective magnitude | Composite |
|---|---|---|---|---:|---:|
| S2 / 4 | set_speed 63 | NORMAL | POSITIVE | .050000000 | .801447461 |
| S2 / 5 | set_speed 48 | NORMAL | POSITIVE | .050000000 | .801823096 |
| S2 / 6 | set_speed 97 | NORMAL | NEGATIVE | .141666667 | .798281429 |
| S2 / 7 | set_speed 97 | NORMAL | NEGATIVE | .141666667 | .794688645 |
| S2 / 8 | set_speed 94 | NORMAL | NEGATIVE | .116666667 | .791468016 |
| S3 / 4 | write_register 55 | NORMAL | NEUTRAL | 0 | .800947461 |
| S3 / 5 | write_register 55 | NORMAL | NEUTRAL | 0 | .801198096 |
| S3 / 6 | write_register 999 | NORMAL | NEUTRAL | 0 | .801451697 |
| S3 / 7 | write_register 999 | NORMAL | NEUTRAL | 0 | .801707523 |
| S3 / 8 | write_register 999 | NORMAL | NEUTRAL | 0 | .801965017 |
| S5 / 4 | set_speed 68 | NORMAL | POSITIVE | .050000000 | .801447461 |
| S5 / 5 | set_speed 53 | NORMAL | POSITIVE | .050000000 | .801823096 |
| S5 / 6 | set_speed 85 | HIGH_OUTPUT | POSITIVE | .050000000 | .802201697 |
| S5 / 7 | set_speed 85 | HIGH_OUTPUT | POSITIVE | .050000000 | .802582523 |
| S5 / 8 | set_speed 84 | HIGH_OUTPUT | POSITIVE | .050000000 | .802965017 |

For S2 events 6/7, deviation=(97-80)/(80-20)=17/60, so magnitude=(17/60)*.5=.141666667. Event 8 magnitude=(14/60)*.5=.116666667. Negative-precedence suppresses positive identity/device gains. At event 6 the prior history is positive and cannot offset the behavioral loss. Events 7/8 also receive negative internal HISTORY from the earlier observed limit violations (previous h=-.006815592 and -.040528361; history confidence .5). Thus both immediate and historical losses are traceable to observed nonconformance, not compromise labels. Later S2 events 9/10 similarly exceed 80 (113/93) and are evaluated by the identical rule; no attack marker is read.

S3 slowly increases due to positive identity/device evidence and prior support; that is not evidence that the register request is authorized. S5 also receives positive conformance evidence under its current mode. Falling trust alone is not a scientific detection result, and remaining within a limit does not prove safety.

## Files and verification

Inspected generation, state/snapshot definitions, projection, limits, identities, provenance/version checks, orchestration/CLI, trust specification and existing coverage/model tests. Added tests/test_observable_coverage.py and this document. Modified core/experiment.py (new version constant), core/orchestrator.py and main.py (explicit option), environment/event_generator.py (general state path), environment/provenance.py (supported version validation). No existing tests were edited.

Full suite: 251 passed, 0 failed. Changed Python files passed syntax checks. git diff --check passed. The frozen trust model/state/configuration files have no diff. Existing baseline behavior is retained; enabling the enriched profile is an explicit experimental choice. Stop after Day 2C.5.
