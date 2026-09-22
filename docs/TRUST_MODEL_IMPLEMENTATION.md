# Day 2C — dynamic trust model

Implemented: mathematical per-entity state updates from Day-2B evidence. No Trust Agent, decision/risk/governance wrapper, scenario changes, adaptation, long-term memory or LLM integration. Day-2A specification and Day-2B extraction are unchanged. Implementation version: `day2c-model-v1`.

## State and API

`core/trust_state.py` defines frozen `EntityTrustState`. It contains the five dimension scores, composite, entity ID, observation count, version, last_sequence_number, bounded historical statistic, a tuple of five persistent negative-history flags, and per-dimension counts of effective evidence-bearing observations. Tuple order is IDENTITY, DEVICE, BEHAVIOR, HISTORY, CONTEXT. Counters indicate coverage, not calibrated confidence. `to_dict()` returns independent JSON-compatible data.

`intelligence/trust_model.py` provides:

```python
model = TrustModel()
state = model.initialize_entity('asset:PLC-07')
evidence = extractor.extract(runtime_observation(event))
state = model.update('asset:PLC-07', evidence,
                     delivery_token=opaque_token,
                     observation_number=local_ordinal)
state = model.get_state('asset:PLC-07')
```

Initialization is explicit and idempotent: calling it again returns existing state, never resets a profile. Update/get of an uninitialized entity raises KeyError. Each model instance is an isolated run; there is no shared trajectory/global state. Registered assets and identities are snapshotted at construction for prior selection. Namespace `asset:` and `identity:` isolates the two populations. Unknown names receive the uncertain prior; unknown entities are not called malicious.

## Configuration and initialization

`config/trust_model.yaml` references the existing `trust.yaml`. The canonical known prior (.80), bounds (0/1) and weights (.20/.25/.25/.15/.15) are loaded from that file without duplication. The new file configures unknown prior .50, positive rate alpha=.01, negative rate beta=.10, recovery rho=.005, recency lambda=.25, historical confidence c_H=.50, and weight tolerance 1e-9. All experimental numeric choices remain UNCALIBRATED; no scientific validation is claimed. No prior or weight was silently changed.

`TrustModelConfig` is immutable; it requires finite bounded values, five nonnegative weights summing to 1 within tolerance, 0<rho<=alpha<beta<=1, 0<lambda<=1 and an unknown prior strictly inside the bounds. Weights are not normalized. Configuration overrides use a newly validated config/model; do not change parameters mid-run. Source paths are configuration-loading details and never inference features. Config version/status and unknown/missing configuration keys are validated.

All five dimensions initialize to their entity's prior. h=0; counters and flags start empty. Missing dimensions retain their prior and zero coverage rather than being excluded from composite weights.

## Exact aggregation and simultaneous update

This follows the additive equation in the authoritative specification. The prompt's conceptual headroom/vulnerability example is not substituted for that equation.

1. Accept a list/tuple of exact `TrustEvidence` records for one entity, without original event audit fields. Reject other objects, mixed entities and audit-correlated records.
2. Deduplicate by `(entity_id, dimension, source, reason)`; exact duplicates count once, conflicting payloads with the same key fail before mutation. Source/reason text is used only for equality-based deduplication, never parsed for labels or numeric rules.
3. Effective magnitude m=strength*confidence. For each dimension compute P=max(positive m,0), N=max(negative m,0). NEUTRAL contributes zero even if its record has nonzero numeric fields. No sums or sequential per-item trust updates occur.
4. Compute the direct event's positive/negative maxima before adding internal historical evidence. Day-2B neutral HISTORY records are accepted but do not supply history. Nonneutral external HISTORY is rejected: the specified history recurrence is the single authority.
5. If direct evidence is nonzero, synthesize HISTORY evidence from the previous h as described below.
6. If any N>0, set all P to zero for that entity/event, including positive historical support. Current authentication success cannot cancel negative behavior.
7. From the same pre-event vector, for each dimension d:

   `x_next[d] = clip(x[d] + a[d]*P[d] - beta*N[d], minimum, maximum)`

   `a[d] = rho` if the dimension has ever received nonzero negative evidence, otherwise `alpha`. Mark that dimension's negative-history flag when N[d]>0; flags persist for the run. A negative event suppresses positive updates, so choosing the pre-event flag for that event makes no mathematical difference.
8. Composite is `sum(w[d]*x_next[d])` in fixed dimension order using math.fsum; clamp numerical boundary drift to the configured bounds. There is no missing-dimension reweighting.

Evidence order within a batch is irrelevant. The maxima and deduplication key prevent repeated weak positives from winning by quantity or iteration order. Evidence counts advance for dimensions with positive or negative effective evidence before suppression; they describe evidence availability, not whether a positive update was permitted.

## Historical recurrence and recovery

Only per-entity sufficient statistics are retained; no event-history database or memory agent is introduced.

For a direct evidence-bearing observation, let z=-max(N_direct) if any direct negative exists, otherwise z=max(P_direct). Set:

`h_next = (1-lambda)*h + lambda*z`.

The current historical update uses **old h**, not h_next: positive magnitude h*c_H when h>0, negative magnitude (-h)*c_H when h<0, otherwise zero. Historical evidence never feeds back into z. A current direct negative is applied immediately even after long positive history; positive HISTORY support is suppressed on that event. A negative prior h can temporarily suppress present positive updates, but h itself still advances using the direct positive observations. Thus sustained real positives eventually reverse historical evidence and allow gradual recovery.

Empty, neutral-only and zero-confidence batches leave all trust values, h, flags and evidence counts unchanged. They still count as accepted transport observations (see ordering below). They neither reward missing evidence nor punish it. No wall-clock decay occurs. Once negative evidence has affected a dimension, subsequent positive recovery uses rho, not alpha. One good event cannot undo a strong loss under the provisional rates. Recovery requires supported positive evidence; missing data offers no automatic rehabilitation.

## Delivery ordering and atomicity

The caller supplies a transport-owned opaque token and an entity-local ordinal, **not** the original scenario-bearing ID or experimental sequence. `last_sequence_number` stores that local ordinal for compatibility with the requested state schema. Model arithmetic never depends on its magnitude; it is checked only for ordering.

Ordinals must be exactly 1,2,3,... per entity. Duplicate tokens, reused/out-of-order ordinals and ordinal gaps are rejected. Tokens are compared only for equality; callers must not substitute original IDs. Deduplication tokens are retained in a private per-entity in-memory set for this model instance. Separate entities may use the same transport token (one observation can concern distinct profiles); each profile can receive it once.

Each accepted update advances version and observation_count by one, even if neutral or empty, because delivery state changed. Invalid batches consume neither state, token nor ordinal. An old immutable state remains unchanged after later updates. Reusing the same numeric evidence at a new genuine delivery is legitimate; idempotency requires the adapter to preserve a delivery's token across retries. The model cannot identify a relabeled retry from content alone.

Correlation workflow: project -> extract uncorrelated evidence -> update model with opaque delivery metadata -> attach original audit IDs/sequences outside the model. Correlated evidence is rejected rather than inspecting its scenario-bearing strings. No orchestration hook was added in Day 2C.

## Leakage and determinism

Public update accepts TrustEvidence only, not IndustrialEvent, dictionaries or arbitrary additional label arguments. It uses dimension, direction, strength/confidence, namespaced attribution, equality-based source/reason deduplication, and opaque ordering metadata. The existing projection/extractor remains responsible for origin hygiene; callers cannot claim arbitrary label-derived records are safe merely by constructing TrustEvidence. The model is an API boundary, not an adversarial sandbox.

Model configuration, fixed reference registries and the same initial/evidence sequence yield identical states. No time, UUID, randomness, process identity, filesystem-derived features or scenario branching enters arithmetic. Strict type checks reject subclasses carrying hidden extra fields through the public evidence API. Immutable returned states and configuration prevent accidental public mutation. Python-private internals are not intended as mutable API.

Tests cover raw/correlated record rejection, unexpected label arguments, and identical S2/S3/S5 trajectories after changing hidden labels/provenance before safe projection. Day-2B leakage tests also remain passing.

## Actual diagnostic results

Using generated scenarios with seed 42, ten events, a fresh model per scenario and the unchanged Day-2B extractor:

| Scenario | Event | TI | TD | TB | TH | TC | Composite |
|---|---:|---:|---:|---:|---:|---:|---:|
| S2 | 5 | .802500 | .802500 | .800000 | .800487305 | .800000 | .801198096 |
| S2 | 6 | .803000 | .803000 | .800000 | .800677979 | .800000 | .801451697 |
| S3 | 5 | .802500 | .802500 | .800000 | .800487305 | .800000 | .801198096 |
| S3 | 6 | .803000 | .803000 | .800000 | .800677979 | .800000 | .801451697 |
| S5 | 5 | .802500 | .802500 | .802500 | .800487305 | .800000 | .801823096 |
| S5 | 6 | .803000 | .803000 | .803000 | .800677979 | .800000 | .802201697 |

Numbers are rounded for display. Scenario/event labels in this table belong to the diagnostic harness, not the model. For S2/S3, identity and device positive magnitudes are .05 each; missing behavioral/context references provide zero evidence. TI/TD increase slowly, TB/TC hold, and TH increases from prior observed positive support. There is no forced degradation at event 6. These are evidence-coverage limitations (S2 missing mode, S3 missing approved register limits), not detection successes or trust-model failures. S5 additionally supplies positive behavioral magnitude .05 under the current mode; no false penalty is applied for the legitimate HIGH_OUTPUT change. Historical statistic at events 5/6 is .038134765625 / .04110107421875 in all three cases because maxima, not sums, define z.

## Verification, limitations and scope

New tests cover priors, configurable weights, exact effective magnitudes, asymmetry, maxima/permutation invariance, simultaneous negative precedence, clipping, history lag, history nonfeedback, gradual recovery, neutral holds, delivery errors, atomicity, entity isolation, immutable state, reproducible trajectories and leakage. Existing 207 tests remain unchanged. No frozen-code bug required a fix; the implementation adds the requested mathematical behavior and guards. Full-suite and syntax results are reported in the task response.

Limitations: all rates/confidences/priors remain uncalibrated; identity/device evidence can slowly raise trust despite unobserved behavior; bounded weighted sums are not safety decisions; TH is correlated with other dimensions; token memory grows with run length; no concurrent-update/thread-safety guarantee, durable state, long-term memory or trust-evaluation artifact store is provided. Caller authenticity and correct opaque token assignment are assumed. Missing S2/S3 references are not invented. Model instances and diagnostic output are separate from frozen Day-1 artifacts.

Added files: core/trust_state.py, intelligence/trust_model.py, config/trust_model.yaml, tests/test_trust_model.py, docs/TRUST_MODEL_IMPLEMENTATION.md. Existing source, scenarios, configuration and authoritative specifications were not modified. Stop after Day 2C.
