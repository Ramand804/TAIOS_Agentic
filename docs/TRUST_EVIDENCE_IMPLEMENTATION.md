# Day 2B: trust evidence extraction

Implemented scope: label-safe observations to immutable evidence records only. No trust score, dynamic model, composite, agent, history accumulator, adaptation, or LLM integration exists in this change. The Day-2A scientific specification remains unchanged.

## Files and architecture

`core/trust_evidence.py` contains the validated record, enums and post-inference correlation function. This follows the existing `core/decision_record.py` / `core/experiment.py` record-model convention rather than introducing a duplicate models package. `intelligence/trust_evidence_extractor.py` implements stateless extraction; `config/trust_evidence.yaml` holds validated numeric settings. There is no orchestration hook or modification to frozen events, projection, scenarios, trust.yaml or Day-1 logs.

Inspect the existing `runtime_observation` projection first. Call:

```python
safe = runtime_observation(event)
evidence = extractor.extract(safe)
audited = attach_audit_correlation(
    evidence, event_id=event.event_id, sequence_number=event.sequence_number
)
```

The caller is an outer evaluation/audit adapter. The extractor never receives original IDs, sequences, scenario metadata or raw events. Audit stamping copies records after inference and cannot alter direction, strength, confidence, source or reason. Uncorrelated records have both audit fields None; correlated records require a nonempty ID and positive integer sequence. Re-stamping fails explicitly. No opaque ordering token is required yet because extraction has no state, no update, and no replay side effects; stateful delivery control remains Day 2C work.

## Exact input contract

The exact existing projection schema is required: source_id, source_type, target_id, target_type, identity_id, event_type, operation, requested_value, network_zone, protocol, authentication_status, asset_criticality, and contextual_features. Context may contain only production_state and operating_mode. String/boolean/enum/criticality values are validated. Numeric operational-limit requests must satisfy the centralized limit model's finite-number validation. Unknown operations are insufficient evidence, not an invented numeric rule.

Raw IndustrialEvent objects, raw event dictionaries and extra top-level/context fields are rejected at one schema boundary. This is an allowlist, not separate label blacklists in each evidence rule. Missing context keys are accepted as missing evidence. Authentication status is an observation, not authorization. Event_type, target_type and criticality are available but do not affect the current evidence rules. Identifiers are used for reference lookup/attribution only, never scenario-specific rules. Payloads are not interpreted as instruction text.

## Model and ordered extraction

TrustEvidence is frozen and contains entity_id, dimension, direction, strength, confidence, source, reason, event_id and sequence_number. Enum values are IDENTITY/DEVICE/BEHAVIOR/HISTORY/CONTEXT and POSITIVE/NEGATIVE/NEUTRAL. Scores must be finite numbers in [0,1], not booleans. Required strings must be nonempty. effective_magnitude is exactly strength*confidence. The extractor emits neutral records with strength=confidence=0; the data model itself does not perform downstream sign aggregation.

Exactly five records are emitted in IDENTITY, DEVICE, BEHAVIOR, HISTORY, CONTEXT order. All refer to `asset:<source_id>`; targets are not blamed. Sources use versioned dimension rule identifiers and reasons use controlled codes plus observable facts. Identity reasons retain the observed identity binding.

- IDENTITY: known identity plus successful authentication gives limited positive evidence; authentication failure gives negative evidence whether the identity is known or not. Unknown identity with authentication success gives neutral/insufficient evidence. No authorization policy is invented.
- DEVICE: compare source type, protocol and zone with the authoritative asset registry. Agreement gives limited positive evidence; mismatches yield one negative item naming mismatched fields; unknown source gives neutral. Day-1 validation already rejects inconsistencies, so these rules have low discriminative power in generated scenarios. Tests exercise safe synthetic observations, without weakening ingress validation.
- BEHAVIOR: look for a target/operation reference, then current mode, then that mode's limit. Missing references produce neutral with a specific reason. Existing OperationalLimits performs the check. In-range gives limited positive evidence; out-of-range strength is min(1, deviation/deviation_saturation). No stale-mode cache, hidden anomaly score, fallback mode or label lookup is used.
- HISTORY: explicit neutral NO_HISTORY, with no retained observations or statistics.
- CONTEXT: missing production/mode information gives neutral MISSING_CONTEXT; when both are present, neutral NO_CONTEXT_RULE explains that no independent rule is approved. Do not count a behavioral limit check again as contextual evidence. Maintenance/emergency/status fields remain unavailable.

## Provisional configuration

Every numeric evidence parameter is in trust_evidence.yaml. Calibration status is explicitly UNCALIBRATED; these are engineering defaults requiring sensitivity analysis, not measured probabilities.

| Parameter | Value | Origin |
|---|---:|---|
| identity_positive_strength | .10 | Day-2A proposal |
| identity_negative_strength | 1.0 | Day-2A proposal |
| identity_confidence | .50 | Day-2A illustrative source confidence |
| device_positive_strength | .10 | Day-2A registration proposal |
| device_negative_strength | 1.0 | New explicitly provisional mismatch severity, not scientifically calibrated |
| device_confidence | .50 | Day-2A illustrative source confidence |
| behavior_positive_strength | .10 | Day-2A in-range proposal |
| behavior_confidence | .50 | Day-2A illustrative source confidence |
| deviation_saturation | 1.0 | Day-2A proposal |

Strength/confidence ranges are [0,1]; saturation is finite and >0. Unknown/missing config keys and unsupported version/status fail. Zero neutral values and strength saturation at 1 are semantic bounds, not scattered calibration settings. YAML is loaded relative to the module location, not the working directory; the path never appears in evidence. No learning/recovery rates, priors or composite weights are applied.

## Determinism and leakage

No randomness, time, UUIDs or run-scoped mutable state is used by extraction. Reference assets/identities are snapshotted at extractor construction; operational limits are the frozen centralized model (whose check still validates target membership in the authoritative registry). Registry/limit definitions are reference configuration and must remain fixed for an extraction run. No shared registry or global data is mutated. Configuration changes require a new explicitly configured extractor for reproducible comparisons.

Metamorphic tests mutate ground_truth, expected_safe_action, scenario IDs, original audit IDs/sequences, provenance, phase hints and synthetic scores before the unchanged projection. Ordered uncorrelated records remain identical across S1–S6. Audit correlation tests show only audit fields differ when IDs change. Exact-schema tests reject bypassing the projection with raw/enriched records. Repeated extraction leaves observations unchanged and produces equal records.

## Observed focused inspection, seed 42, ten events

Sequence/scenario columns below belong only to the evaluation harness. The extractor did not receive them or any transition label.

| Evaluation event | Observable request | Observable mode / applicable range | Behavioral evidence |
|---|---|---|---|
| S2 event 5 | set_speed 48 | mode missing | NEUTRAL, MISSING_MODE |
| S2 event 6 | set_speed 97 | mode missing | NEUTRAL, MISSING_MODE |
| S3 event 5 | write_register 55 | no target/operation limit | NEUTRAL, MISSING_LIMIT |
| S3 event 6 | write_register 999 | no target/operation limit | NEUTRAL, MISSING_LIMIT |
| S5 event 5 | set_speed 53 | NORMAL / 20–80 | POSITIVE, strength .10, confidence .50 |
| S5 event 6 | set_speed 85 | HIGH_OUTPUT / 60–95 | POSITIVE, strength .10, confidence .50 |

All six observed events authenticate successfully with known identities; each yields positive IDENTITY strength .10/confidence .50 and positive DEVICE strength .10/confidence .50. HISTORY and CONTEXT are neutral. A separate safe observable fixture with authenticated identity and speed 90 under NORMAL produces simultaneous positive IDENTITY and negative BEHAVIOR (strength 1/6, confidence .50). That fixture demonstrates dimensional independence; it is not a claim of S3 detection.

## Limitations and verification

S2 requires an approved observable mode feed before mode-aware behavioral detection. S3 lacks approved register limits/authorization semantics. No authorization, contextual interlock, historical inference or trustworthiness verdict is manufactured. Parameter calibration and richer context remain future work. Registration consistency and authentication success are weak evidence, not full trust. Configurations cannot change frozen Day-1 experiment fingerprints because extraction is separate and does not write event logs.

Added tests cover record validation/immutability/correlation, identity/device/behavior/context/history, mode-sensitive limits, determinism, leakage and S2/S3/S5 integration. No frozen-code bug was changed; a missing-audit-metadata edge case in the new correlation helper was caught and fixed during implementation. The task report records executed full-suite, syntax and diff checks. Stop at Day 2B.
