# TAIOS trust model specification — Day 2A

Status: **DEFINED DESIGN for later implementation; no Trust Agent is implemented.**
Specification version: `day2a-spec-v1`. Inspected Day-1 scenario/generator version: `day1c-step4-v1`.

Throughout this document, **DEFINED DESIGN** identifies the proposed normative algorithm/interface contract for Day 2B/2C. **PARAMETER REQUIRING EXPERIMENTAL VALIDATION** identifies an uncalibrated experimental setting. Neither means the corresponding runtime feature already exists. Day-1 generation, labels, manifests, fingerprints and configuration are unchanged.

## 1. Purpose

Specify bounded, persistent, evidence-driven trust for Industrial IoT actors. Trust is a model of confidence in an actor's observable conduct, not a probability of attack, a risk score, an authorization grant, or an execution decision. Later implementation must be deterministic given the same approved observations, initial state, evidence rules and trust configuration. No inference may access experimental answers.

## 2. Threat and trust assumptions

**DEFINED DESIGN:** Registered devices and authenticated credentials can be compromised. Authentication proves only the observed authentication result; registration establishes a reference identity, not continuing benign behavior. Legitimate operating regimes can change. Missing information is uncertainty, not adverse evidence. A limit violation is evidence of nonconforming behavior, not proof of malicious intent. Target criticality is observable but must not directly penalize trust; impact-based reasoning belongs to future risk work.

The evidence source itself is assumed trusted at this stage. Spoof-resistant telemetry, attestation, adversarial evidence manipulation, collusion, identity recovery and physical-process fidelity are deferred. Synthetic Day-1 anomaly/trust/attack-probability fixtures are not measured evidence.

Primary entity attribution is `asset:<source_id>` for source conduct; the target identifies which operation limits apply and is not blamed for receiving a command. TI for this source profile measures identity/authentication evidence associated with that source's current commands. Evidence retains the observed identity binding in its reason/source records. Separate `identity:<identity_id>` profiles may receive IDENTITY and attributed BEHAVIOR/HISTORY evidence, but their scores are separate outputs, never substituted into another profile mid-update. Unobserved dimensions retain their priors and a missing-evidence flag. Asset and identity namespaces prevent collisions. Trust scores are comparable only with their entity type, evidence coverage and model version reported. General multi-identity attribution requires later review; no cross-entity score propagation is defined.

## 3. Trust dimensions

| Symbol | Dimension | Meaning |
|---|---|---|
| TI | IDENTITY | Confidence supported by observed identity/authentication compatibility |
| TD | DEVICE | Confidence supported by device reference consistency and independent integrity evidence |
| TB | BEHAVIOR | Confidence that requests conform to approved, mode-specific operational behavior |
| TH | HISTORY | Recency-weighted summary of prior independently observed conduct |
| TC | CONTEXT | Compatibility with approved plant/context constraints not already charged to TB |

Each profile persists five dimension values between observations. Reinitializing per event is prohibited. Values are finite real numbers in [0,1]; reject NaN, infinity, booleans used as scores, invalid dimension names and invalid weights. Evidence coverage/confidence must remain distinguishable from numeric trust: a prior with no evidence is not a calibrated high-confidence estimate.

## 4. Composite trust equation

**DEFINED DESIGN:** For entity e after accepted observation t:

\[
T(e,t)=0.20T_I(e,t)+0.25T_D(e,t)+0.25T_B(e,t)+0.15T_H(e,t)+0.15T_C(e,t).
\]

Generally use configured nonnegative weights with sum 1 (validate within a documented numerical tolerance, proposed 1e-9; never silently normalize). Existing YAML keys are `identity`, `device`, `behavioral`, `historical`, `contextual`; retain these spellings in later configuration loading. All five dimensions remain in the denominator even if some have no evidence; report coverage rather than renormalizing missing dimensions away. The convex combination guarantees a bounded composite when dimensions are bounded. A trust threshold, if used for evaluation, is not a governance decision.

## 5. Dynamic trust update equation

**DEFINED DESIGN:** For each entity and dimension d, compute effective evidence m_i = strength_i × confidence_i. Within an event, deduplicate evidence by `(entity_id, dimension, source, reason)` and reject duplicate conflicting payloads. Use maxima rather than sums to avoid inflating updates by repeating correlated detectors:

\[
P_d=\max(\{m_i:direction_i=POSITIVE\}\cup\{0\}),\quad
N_d=\max(\{m_i:direction_i=NEGATIVE\}\cup\{0\}).
\]

NEUTRAL always contributes zero, regardless of strength. No evidence means P_d=N_d=0. Compute all five updates from the same pre-event snapshot. For conservative within-event conflict handling, if any dimension has N_d>0, set every P_d to zero for that entity in that update. Thus successful authentication cannot cancel contemporaneous negative behavioral evidence. This is a configurable policy alternative only in future sensitivity experiments, not an implicit code branch.

\[
x_{d,t+1}=clip(x_{d,t}+a_{d,t}P_d-\beta_dN_d,L,U).
\]

Here L=0 and U=1 initially; a=alpha for a dimension with no prior negative evidence, and a=rho after its first nonzero negative evidence. The `has_negative_history` bit persists for the run, so recovery remains gradual rather than reverting after one good event. Require 0<rho<=alpha<beta<=1. Use common rates initially; per-dimension rates are optional future experimental parameters. With equal nonzero evidence and no clipping, loss beta*m exceeds gain alpha*m and recovery rho*m. Clipping can limit actual changes at boundaries, so asymmetry is not a claim that every saturated numeric loss exceeds every possible gain.

No autonomous decay/recovery on wall-clock time, no reset on a regime change, and no updates on duplicate event delivery. A transport-owned opaque token and an entity observation ordinal enforce exactly-once ordering; see section 12. Compute composite only after the simultaneous dimension update. Example arithmetic fixture (not observed implementation): alpha=.01, beta=.10, rho=.005, x=.80 and m=.80 yields .72 after negative evidence; one subsequent positive observation can restore at most .005, not .08.

## 6. TrustEvidence model

**DEFINED DESIGN:** Later implement a validated immutable record:

| Field | Contract |
|---|---|
| entity_id | Namespaced observable entity being assessed; never a scenario-specific constant |
| dimension | IDENTITY, DEVICE, BEHAVIOR, HISTORY or CONTEXT |
| direction | POSITIVE, NEGATIVE or NEUTRAL |
| strength | Finite [0,1] severity/support from an approved observation rule |
| confidence | Finite [0,1] reliability/coverage of that evidence source |
| source | Versioned allowlisted rule identifier, not provenance causal tags |
| reason | Controlled rule code and observable facts; no free-form evaluation-label explanation |
| event_id | Audit correlation assigned by the outer adapter, not read by inference |
| sequence_number | Original audit sequence assigned after inference; ordering uses a separate opaque envelope |

Effective magnitude is exactly strength*confidence and enters P/N above. Zero confidence causes no update. Negative strength/confidence or out-of-range values fail, not clip. Audit fields must not be parsed, hashed into inference features, or used for scenario selection. A source/reason rule is versioned with declared feature dependencies. Duplicate delivery of a previously accepted envelope produces no further state transition. Evidence and the resulting profile transition will be separately serializable for tests; this specification does not build explainability agents.

## 7. Evidence-to-dimension mapping

| Observable evidence | Dimension/direction | Defined handling and availability |
|---|---|---|
| Authentication success | TI positive, weak support | Strength from configured auth-positive rule; confidence from source quality. A bounded update only; never assign TI or composite to 1. Repeated identical facts within one observation count once. |
| Authentication failure | TI negative | Uses authentication_status; failure does not prove maliciousness. Source confidence determines magnitude. |
| Known identity | TI positive support | Trusted identity registry lookup; combine correlated success/known checks by max, not sum. |
| Unknown identity | TI neutral initially | Use uncertain prior; do not infer maliciousness from absence. Authentication failure is separate evidence. |
| Authorization or identity/operation mismatch | TI negative if verified | Requires an approved operation/role policy that Day 1 does not provide. Otherwise neutral. |
| Device registered and expected source/protocol/zone agree | TD limited positive support | Registry and observable source fields; consistency is not attestation. |
| Unknown device / integrity violation | TD neutral unknown or negative verified inconsistency | Day-1 EventManager rejects unknown/mismatched assets before inference. This requires a separately approved ingress-evidence adapter later; do not weaken integrity validation. |
| Operation/value outside current approved range | TB negative | Recompute deviation from observable operation/value/mode and trusted limits; never consume logged anomaly_score. |
| Operation/value inside range | TB limited positive | Conformance supports behavior, not guaranteed safety or successful execution. |
| Repeated adverse conduct | TH negative | Summarize past evidence as below. Do not charge the same limit violation again to TD/TC. |
| Independently verified contextual incompatibility | TC negative | Requires a separate approved context rule, such as maintenance authorization; if absent, neutral. |
| Independent contextual compatibility | TC limited positive | Only where a positive rule exists; absence of emergency metadata is not a positive signal. |

For TB, recompute Day-1 d=max(L-x,0,x-U)/(U-L); zero-width ranges use denominator 1. Negative strength is min(1,d/d_sat), with d_sat>0 configured. In-range support has configured strength s_ok in [0,1]. Confidence is explicit: a missing or stale mode/limit yields neutral evidence and a missing-coverage marker. Do not infer a mode from scenario ID, phase, requested value or event position. Do not learn a baseline from labels.

A single operational-limit check is assigned to TB, not both TB and TC. TH is intentionally a lagged temporal summary and is correlated with prior dimensions; it is not independent probabilistic evidence. Composite weights are heuristic research weights, not a calibrated Bayesian combination.

## 8. Cold-start policy

**DEFINED DESIGN:** Keep existing `initial_default: 0.80` for all dimensions of known registered asset and known identity profiles in the first comparison baseline. Registration itself does not imply evidence coverage or perfect trust. This is a favorable prior and must be tested against lower-prior alternatives.

Unknown profiles use configurable p_unknown strictly between 0 and 1, proposed .50. Mark them uncertain and leave unsupported dimensions at that prior. Separate asset/identity known-prior parameters may later be added with .80 compatibility defaults, not silently changed. Neither unseen identity nor unseen device means malicious. Unknown devices are currently rejected upstream; a cold-start unit fixture can test the future profile model without altering Day-1 scenarios.

No prior depends on scenario name, attacker IDs, source being PLC-07, provenance, ground truth or expected action. Initialize once per entity per run. Fresh experiment state is isolated from previous experiments.

## 9. Negative evidence and historical trust

**DEFINED DESIGN:** Contemporary negative evidence immediately updates its originating dimension with beta; old positives never discount that update. Maintain a per-entity bounded signed recency statistic h in [-1,1], initially 0, over accepted evidence-bearing observations only. For the current event, using dimensions other than HISTORY, define z=-max_d N_d if any N_d>0, else z=max_d P_d. If all P/N are zero, leave h and TH unchanged.

For a nonneutral event, update h_next=(1-lambda)*h+lambda*z, 0<lambda<=1. Larger lambda prioritizes recent conduct. TH for this event uses the *previous* h as one HISTORY evidence item: sign(h), strength=abs(h), confidence=c_history. The new statistic becomes available on the next evidence-bearing event. Missing history h=0 gives NEUTRAL. HISTORY evidence is never fed back into its own statistic; no circular reinforcement. Old positive history is bounded, while the current negative updates TB/TI/TD/TC without waiting for h to turn negative. Positive history is suppressed by the negative-precedence rule on a negative event.

Later tests must verify recovery after a sufficiently long clean sequence and degradation under a long previously positive sequence. Long-term memory, persistent databases and cross-run history are not required; only per-run in-memory sufficient statistics are specified. Evidence-bearing observations, not wall-clock age, define recency. Thus this design does not claim protection against arbitrarily high-rate manufactured positive traffic.

## 10. Trust recovery

**DEFINED DESIGN:** After negatives stop, real positive evidence increases each affected dimension at rho*P, subject to the global negative-precedence rule and bounds. A decaying historical negative may delay recovery until subsequent genuine positives turn h positive. This delay must be measured, not hidden with resets. Repeated supported positive observations eventually make h positive and increase trust; silence, neutral events or missing data do not rehabilitate it. Persistent lack of evidence in a degraded dimension does not guarantee recovery.

No scenario transition label triggers recovery. A one-event positive increment is at most rho per dimension (and at most rho in composite for common rates); choose and report rates that cannot erase the loss from strong evidence in one event. Sensitivity tests must include both recovering and non-recovering evidence patterns. Revocation/re-enrollment policy is deferred.

## 11. Context-awareness

**DEFINED DESIGN:** TB uses the mode observed at the time of the request and the target's approved limits. Speed 90 under NORMAL 20–80 yields deviation 10/60; HIGH_OUTPUT 60–95 yields 0; MAINTENANCE 0–20 yields 70/20. These are conformance checks, not maliciousness classifications. A legitimate new mode must not be penalized simply for differing from a previous mode.

Production state and operating mode are currently projected when present. Maintenance/emergency flags, asset status/health, and full state snapshots are not currently projected. Do not access raw snapshots to bypass this restriction. Future selective projection requires an explicit reviewed change and validated, observable telemetry; state_version itself is not an inference feature. Context rules linking flags to allowed actions are not defined by the independent Day-1 state enums. TC must remain neutral without such rules, not invent an interlock.

Recent-behavior heuristics must condition on observable operating mode; unconditional speed-change penalties would incorrectly penalize S5. Learned change detection/adaptation is outside this specification.

## 12. Exact label-leakage boundary

**DEFINED DESIGN:** The future trust updater accepts only `core.runtime_inputs.runtime_observation(event)` plus explicitly approved reference configuration. Never pass IndustrialEvent, its `to_dict()`, ExperimentRun.configuration (which contains the manifest), or scenario manifests into inference.

Exact currently allowlisted top-level fields are:

`source_id`, `source_type`, `target_id`, `target_type`, `identity_id`, `event_type`, `operation`, `requested_value`, `network_zone`, `protocol`, `authentication_status`, `asset_criticality`.

Only `contextual_features.production_state` and `contextual_features.operating_mode` are copied, validated through their enums, if present. Other context keys are excluded by default. Source/identity IDs support reference lookup and state indexing only, never hardcoded scenario recognition. `asset_criticality` is available but unused in trust scoring.

Strict evaluation-only fields: `ground_truth`, `expected_safe_action`, manifest `ground_truth_policy`. Privileged simulator metadata also forbidden to inference: all provenance (phase, causal_tags, transition_type, versions, total_events), scenario_id, experiment_id, event_id, sequence_number, timestamp, compromise_phase, compromise_event, event_sequence, drift_phase, new_operating_regime, regime_change_sequence, coordination_group, valid_credentials, synthetic anomaly_score, prior_device_trust, simulated_attack_probability, logged operational_limit and raw state_snapshot. Some state/limit information is conceptually observable, but its full logged representation is not an approved input. Recompute limits from an explicit reference object.

**Audit-correlation conflict resolved by separation:** Day-1 event IDs embed scenario/seed, and the projection intentionally omits IDs/sequences. A future outer adapter must retain original event_id/sequence privately, supply an opaque delivery token plus monotonic local ordinal for idempotency, invoke inference on the projected observation, then stamp TrustEvidence audit fields after scoring. Inference cannot inspect the original run envelope. Do not add those fields to the projection just to satisfy TrustEvidence. Store experimental run IDs/model parameters only in the outer evaluation artifact writer.

Metamorphic acceptance test: changing/removing all privileged fields while preserving projected observations must leave evidence magnitudes, dimension trajectories and composite scores identical. Audit-link strings may differ. Changing an allowed operating mode may legitimately change the evidence. The Python API boundary is not a security sandbox; dependency/interface tests must prevent accidental raw-event access.

## 13. S2 behavior requirements and current gap

Evaluation-only code may use the manifest's first post-compromise event to measure pre-stability, false degradation, post-change delay and minimum trust. Inference must see only observable requests and approved configuration. Under a valid NORMAL reference, 40–70 supports conformance and 90–120 supplies negative behavioral evidence. A confirmed strong negative must reduce the source profile's composite even if authentication remains successful, because positive updates are suppressed in that observation.

**Day-1 conflict:** S2 exposes production_state=ACTIVE but no operating_mode. Do not assume ACTIVE means NORMAL: S5 is ACTIVE in both regimes. Therefore frozen S2 alone is insufficient for the mode-aware limit rule. Day 2B/2C must explicitly approve an out-of-band observable mode feed or a declared deployment-level fallback assumption, versioned as inference configuration and applied by asset/operation, never by scenario. Until then emit neutral behavioral/context evidence for missing mode and report reduced coverage. Degradation cannot honestly be claimed from the forbidden anomaly_score/compromise_phase substitutes.

## 14. S3 behavior requirements and current gap

Authentication success is limited TI evidence and cannot overwrite low TB/TC/TD. Under verified negative behavior, the composite must decline; TI may remain high or steady while other dimensions fall. Do not require a device-integrity failure to detect credential misuse.

**Day-1 conflict:** S3 uses PLC-03 `write_register` values 55 then 999, but OperationalLimits configures only MOTOR-02 `set_speed`. No role-operation authorization policy or register-value reference exists. These values alone do not establish an approved threshold. Later implementation needs separately justified register semantics or an observable baseline specification; no threshold may be reverse-engineered from the malicious half/labels. With frozen Day-1 references alone, TB/TC must be neutral and successful S3 detection is not guaranteed. This is an explicit evidence-coverage blocker, not permission to change ground truth.

## 15. S5 behavior requirements

S5 projects NORMAL then HIGH_OUTPUT and supplies target and requested value. Recompute limits from the trusted central model; never read the logged `within_limit`, anomaly_score or regime_change_sequence. Normal-phase values 45–70 and high-output values 82–94 are within their respective ranges. Acceptance: no negative TB evidence solely due to this legitimate change, no mode-reset of persistent trust, no hidden-phase branch, and deterministic trajectories. False degradation is evaluated separately using labels, not inside inference.

Frozen S5 has no recovery episode following compromise. Recovery speed needs later independent observable-evidence fixtures; do not relabel S5 or invent post-compromise recovery results for it.

## 16. Configuration parameters

No YAML changes are made in Day 2A. **All proposed numeric values below are PARAMETERS REQUIRING EXPERIMENTAL VALIDATION**, intended only as a first explicit sensitivity baseline, not scientifically validated constants.

| Parameter | Status/value | Valid range | Meaning and reason |
|---|---|---|---|
| weights identity/device/behavioral/historical/contextual | Currently configured .20/.25/.25/.15/.15 | Each [0,1], sum 1 | Dimension contribution; preserve existing baseline |
| initial_default / known prior | Currently configured .80 | [0,1] | One-time known asset/identity initialization; favorable assumption to evaluate |
| minimum / maximum | Currently configured 0/1 | 0<=L<U<=1 | Bounded trust; initial design retains 0/1 |
| unknown prior | Proposed .50 | L<p<U | Uncertain initialization without automatic suspicion/trust |
| alpha positive rate | Proposed .01 | 0<alpha<beta<=1 | Slow acquisition |
| beta negative rate | Proposed .10 | alpha<beta<=1 | Faster loss under equal effective evidence |
| rho recovery rate | Proposed .005 | 0<rho<=alpha | Gradual gain after negative history |
| lambda history recency | Proposed .25 | (0,1] | Bounded recent evidence statistic; larger means more recent emphasis |
| c_source evidence confidence | Proposed explicit per rule; illustrative .50 | [0,1] | Reliability attenuation; never inferred from a label. Missing required evidence has confidence 0 |
| c_history | Proposed .50 | [0,1] | Avoid treating correlated temporal summary as certain |
| s_auth_positive | Proposed .10 | [0,1] | Weak support from successful authentication |
| s_auth_negative | Proposed 1.0 | [0,1] | Strong authentication-failure evidence when reliable |
| s_registered_positive | Proposed .10 | [0,1] | Weak registration/consistency support |
| s_ok behavior-positive strength | Proposed .10 | [0,1] | Small reward for an in-range request |
| d_sat | Proposed 1.0 | Finite >0 | Deviation at which behavioral negative strength saturates |
| weight tolerance | Proposed 1e-9 | Finite >0, small relative to 1 | Floating comparison, not weight renormalization |
| evaluation threshold theta | Proposed, unset pending protocol | [0,1] | Offline degradation/false-alarm measurement; not action selection |
| recovery tolerance epsilon | Proposed, unset pending protocol | [0,1] | Offline return-to-pre-event band criterion |

Negative-precedence policy, evidence maxima and no silent-time recovery are DEFINED DESIGN, not unspecified tuning knobs. Missing reference data uses neutral evidence; confidence defaults must never manufacture data. No defaults are claimed for absent authorization/context rules. Context-rule strengths/confidences require named reference rules before implementation.

Later trust configuration must be validated, frozen for a run and recorded separately with trust model/evidence-rule versions and sensitivity settings. Day-1 experiment identity currently does not include trust.yaml because no trust model is running. Preserve event identity/fingerprint and use a distinct trust-evaluation identity for different trust parameters; do not overwrite Day-1 event artifacts.

## 17. Metrics for later evaluation

Evaluation alone may align with manifest transitions. Report per entity and dimension as well as composite:

- Pre-change mean, standard deviation, maximum decrease and below-theta fraction.
- Degradation delay: first post-transition observation with T<theta, minus transition ordinal; also count entity-local observations. Non-crossing runs are right-censored, not assigned zero delay.
- Minimum post-change trust, cumulative decrease and loss per evidence-bearing observation.
- Recovery time: first sustained return to pre-negative baseline minus epsilon after adverse evidence ends, using a preregistered persistence count; censored if absent.
- False degradation: decreases/threshold crossings on evaluation-labeled benign observations, separately for S5 mode changes.
- Evidence coverage: missing mode/limits/authorization fractions, positive/negative/neutral counts and source confidence.
- Sensitivity across weights, priors, rates, recency and evidence strengths/confidences; multiple seeds and independent recovery fixtures.

No performance numbers are reported here. Thresholds, persistence length, metrics window and acceptable false-degradation budgets must be selected before interpreting experimental results. Avoid tuning on the same evaluation labels used to claim performance.

## 18. Limitations and unresolved decisions

The weighted model permits compensation across dimensions in the stored composite; it does not make a safety guarantee even with per-event negative precedence. Evidence and TH are correlated. Repeated authenticated traffic could gradually inflate TI; confidence/novelty controls need sensitivity analysis rather than presumed independence. Aggregation maxima trade off redundancy protection against discarded independent evidence. Hostile event flooding, nonstationary evidence calibration and identity attribution are unresolved research limitations.

No adverse observation can be inferred where references are missing. Outstanding implementation prerequisites are an approved mode source for S2, approved PLC register/authorization semantics for S3, selective context telemetry for future TC rules, source-specific confidence/strength calibration, entity-attribution review for multiple identities per device, and offline evaluation thresholds/windows. The update/aggregation/recency equations are fully specified; these coverage and calibration decisions remain open and must not be silently filled using scenario knowledge.

Current EventManager intentionally rejects asset-integrity failures; trust evidence from rejected traffic needs a future explicit adapter. Day-1 state is pre-command and cannot supply real execution outcomes. Existing YAML is not consumed by Day-1 inference, because none exists. TrustEvidence, updater state, history statistics and correlation adapter described here are all unimplemented.

## 19. Day 2B/2C implementation requirements

1. Preserve frozen Day-1 generation, logs and all existing tests. Implement no risk/planning/governance/execution logic as a side effect of trust work.
2. Add separately validated TrustEvidence/profile/configuration models, then a deterministic stateful updater implementing sections 3–10. No raw-event or manifest dependency inside inference.
3. Unit-test bounds, nonfinite rejection, weight validity, effective magnitude, asymmetric loss/gain, negative precedence, neutral/no-evidence stability, recovery, historical lag/recency, exactly-once replay and entity/run isolation.
4. Test scalar equations using explicitly named test configurations; these fixtures do not validate parameters scientifically.
5. Implement reviewed observable-evidence rules only after their references exist. Missing inputs must yield neutral with coverage diagnostics, not success or failure fabrication.
6. Add the outer audit-correlation adapter and metamorphic label-leakage tests before wiring inference into orchestration. Keep original IDs/sequences outside evidence derivation.
7. Evaluate S2/S3 only with documented observable reference coverage; report blockers otherwise. Verify S5 conformance without hidden scores, transitions or state resets.
8. Keep trust results separate from Day-1 event records, include model/configuration identity, and compare deterministic trajectories across identical inputs. Do not claim detection or recovery until actually measured.

## Day 2A inspection and verification record

Inspected: config/trust.yaml; environment/event.py, event_generator.py, industrial_environment.py, provenance.py, operational_limits.py, identities.py; core/event_manager.py, experiment.py, runtime_inputs.py. The specification records their present contracts rather than assuming future capabilities.

Only docs/TRUST_MODEL_SPEC.md is added for this task. No source, scenario, test or configuration file is modified. Complete existing suite result is recorded in the accompanying task report after execution. Syntax checking is unnecessary for this Markdown-only change.
