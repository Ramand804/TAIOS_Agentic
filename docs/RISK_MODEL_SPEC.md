# TAIOS risk model specification — Day 3A

Specification version: `day3a-spec-v1`. Documentation only; no risk implementation.

**DEFINED DESIGN** means a normative contract for subsequent work. **PROVISIONAL PARAMETER** means an explicit UNCALIBRATED setting, not a validated constant. **UNAVAILABLE SIGNAL** means no supported observation exists. **FUTURE CALIBRATION REQUIREMENT** means evidence or a preregistered study is needed before interpreting or changing a setting. Frozen trust, generation, event identities and configuration remain unchanged.

## 1. Purpose

Define risk as the estimated potential danger of allowing or executing the current requested industrial action, given currently observable evidence. This specification establishes an explainable numeric research index before implementation. It does not authorize execution, predict physical damage, or implement a decision policy.

Inspection covered `config/risk.yaml`; directory inventories and placeholders under `agents/`, `intelligence/` and `evaluation/`, plus `agents/trust_agent.py` and `intelligence/trust_evidence_extractor.py`; `core/trust_assessment.py`, `core/runtime_inputs.py`, `core/event_manager.py`; `environment/event.py`, `industrial_environment.py`, `assets.py`, `operational_limits.py`, `validators.py`, `provenance.py`; and `docs/TRUST_MODEL_SPEC.md`, `TRUST_AGENT_IMPLEMENTATION.md`, `TRUST_EVALUATION.md`. The `models/` directory does not exist. `agents/base_agent.py` is a placeholder; TrustAgent is implemented. `intelligence/threat_detector.py` contains only a docstring. `evaluation/metrics.py` is a placeholder; trust evaluation is implemented. There is no implemented RiskModel or RiskAgent.

Existing risk weights are exactly threat .40, distrust .25, criticality .20, anomaly .15. Existing threshold keys are allow .20, monitor .40, limit .55, request_approval .70, block .85. These are provisional action-named settings, not validated risk classes. Boundary direction, interval conventions and an isolate threshold are not defined here. No configuration is changed or activated.

## 2. Risk semantics

**DEFINED DESIGN:** Risk is an additive, compensatory danger index in [0,1], conditional on the supported components used. Attack probability concerns hostile intent/activity; anomaly concerns observable deviation; distrust concerns accumulated source conduct; criticality concerns consequence potential. None alone is equivalent to risk. Neither the composite nor its complements are calibrated probabilities of attack, failure, injury or expected monetary loss.

Zero denotes zero contribution on all included components, not proof of safety. A high value is no automatic block instruction. Incomplete coverage always qualifies the number. Different coverage masks can change the denominator; compare like masks or report contribution and coverage changes explicitly.

## 3. Threat model

Registered equipment and authenticated identities may be compromised. A legitimate action may be unusual; an authenticated action may be harmful. Observations and reference registries are assumed trustworthy at this stage. Spoof-resistant sensing, physical execution outcomes, authorization semantics, coordinated threat inference and adversarial evidence reliability are not implemented.

**UNAVAILABLE SIGNAL:** There is currently no real label-safe threat detector. `P_attack` is null with status MISSING and reason NO_THREAT_DETECTOR for every current event. Successful authentication does not set it to zero; evaluator-known maliciousness does not set it to one. Simulator `simulated_attack_probability` is not a detector output.

A future detector requires separately reviewed observable inputs, a versioned score definition, validation and calibration status. An uncalibrated confidence may occupy the conceptual threat slot only when explicitly marked as confidence, never represented as calibrated probability. No detector is specified for implementation in this milestone.

## 4. Input components

| Component | Definition | Authorized source | Current availability |
|---|---|---|---|
| THREAT, P | Threat probability/confidence with declared semantics | Future reviewed detector contract | MISSING |
| TRUST, D | 1 minus composite trust | Public TrustAssessment inference view for current source | Available when a valid assessment is supplied, including prior-supported scores |
| CRITICALITY, C | Registered target criticality | Validated observation and authoritative registry | Available for valid current events |
| ANOMALY, A | Saturated current-mode operational deviation or separately reviewed independent anomaly | Central OperationalLimits and safe observation | Candidate computable for supported operations; excluded from primary fusion when overlapping trust |

Input availability is separate from fusion inclusion and evidence sufficiency. Known zero, missing, invalid and deliberately excluded signals have distinct states. No raw event, manifest, joined evaluation record or full configuration containing a scenario manifest enters inference.

## 5. Risk equation

With all four components supported and nonredundant, the conceptual starting model is:

`R = .40 P + .25 D + .20 C + .15 A`, where `D = 1 - T`.

**DEFINED DESIGN:** Let `m_i` be 1 exactly when component i has a valid value and is included under the dependency policy, otherwise 0. Let original nonnegative weights `w = (.40, .25, .20, .15)` sum to 1. Define:

`W = sum(w_i * m_i)`

`effective_weight_i = w_i * m_i / W` when W > 0

`contribution_i = effective_weight_i * value_i` for included components

`risk_score = sum(contribution_i)`.

If W=0, risk_score and all effective weights/contributions are null, with status INSUFFICIENT_INPUTS. If W>0, excluded/missing components have effective weight 0 and contribution 0 **as accounting entries only**; their input value is not imputed as zero. Validate input/weight bounds rather than clipping invalid data. A final floating-point boundary correction within a documented numerical tolerance is permitted; it cannot conceal invalid inputs.

For the current TrustAssessment profile with no independent threat or anomaly, the primary model is:

`R = (.25 (1-T) + .20 C) / .45`.

This consequence-plus-distrust index is deliberately incomplete. It is not tuned to maximize S2 response. If trust is missing and a valid operational anomaly candidate exists, that candidate can be included because no trust component is being fused. This changes the coverage mask and must be visible.

## 6. Input normalization

P, T and C must be finite numeric values in [0,1]; booleans, NaN and infinity are invalid. T is already normalized by its public contract; compute only its complement. C is already the registry's normalized consequence proxy; do not rescale it from this experimental sample.

Reuse `OperationalLimits.check_operational_limit`:

`d = max(L-x, 0, x-U) / (U-L or 1)`; inclusive bounds.

The raw d is nonnegative but can exceed 1. Candidate anomaly is `A_candidate = min(1, d / d_sat)` with finite positive d_sat. **PROVISIONAL PARAMETER:** reuse the current evidence configuration's deviation_saturation=1.0 and record that setting explicitly; do not create a conflicting range normalization. Zero means the observed value conforms to this configured range, not absence of every anomaly. One means deviation reaches the chosen saturation, not certain attack.

Zero-width ranges use the existing denominator 1, so d then has the operation's unit scale and is not generally comparable across operations. Current default ranges have positive width. Future zero-width use requires operation-specific unit/saturation review before claiming cross-operation comparability; preserve the existing arithmetic and expose this limitation.

Do not derive anomaly by negating behavioral trust, parsing human-readable evidence reasons, or dividing effective evidence magnitude by confidence. Recompute from the shared reference and safe observation, retaining mode, bounds and raw deviation as explanation facts.

## 7. Missing-input policy

**DEFINED DESIGN:** Select available-component renormalization together with explicit incomplete coverage; use no neutral prior and no unknown-to-zero substitution.

| Alternative | Scientific consequence | Decision |
|---|---|---|
| Renormalization | No invented observation; preserves bounded index but changes scale as availability changes | Selected, with mandatory mask/weight reporting |
| Neutral prior (e.g. .5 threat) | Adds an unsupported baseline and prior sensitivity; .5 is not known neutral danger | Not selected |
| Fixed weights with missing values replaced by 0 | Systematically lowers index when information disappears and conflates ignorance with absence | Not selected |
| Coverage only | Describes uncertainty but cannot itself choose a numeric missing-value rule | Required alongside selected policy |

Missing threat: null/MISSING/NO_THREAT_DETECTOR. Missing mode or target-operation limits: anomaly null/MISSING with the exact reference gap. Missing TrustAssessment: distrust null/MISSING, no reconstructed prior. A supplied valid prior-dominated trust assessment remains numerically available but carries INSUFFICIENT evidence flags. Missing criticality in a future nullable adapter: null/MISSING, never infer it from source or operation. Current EventManager requires registered target metadata; missing/unknown/mismatched target criticality is instead an ingress validation error. Do not weaken that interface to manufacture a partial event.

Malformed provided values, target registry mismatches and mismatched trust entity are errors, not ordinary missingness. A future partial-input unit fixture can exercise missing-criticality behavior separately from current production ingress. No signal is automatically available because a detector is absent.

## 8. Coverage/confidence

**DEFINED DESIGN:** Each component reports status AVAILABLE, MISSING, or EXCLUDED_CORRELATED; observed_value (nullable); included boolean; and a stable reason code. For EXCLUDED_CORRELATED an observed value may be retained, but it contributes nothing and is not relabeled missing. MISSING uses null. Ablations additionally use EXCLUDED_ABLATION.

Coverage contains: ordered observed_components (valid values, including excluded ones), included_components, missing_components, excluded_components, original_weight_coverage W, and observation_weight_coverage (sum original weights with a valid observed value). Ordering is THREAT, TRUST, CRITICALITY, ANOMALY. Never count excluded anomaly toward W. Components of zero original weight do not improve weighted coverage.

Report trust_evidence_coverage exactly as supplied by TrustAssessment, plus prior_only_dimensions where cumulative evidence_counts are zero. Direct HISTORY may be INSUFFICIENT while internal historical trust changes; do not reinterpret it as new independent evidence. Current per-dimension coverage is not a calibrated confidence estimate or a lifetime evidence measure.

Coverage status is INSUFFICIENT_INPUTS if W=0; otherwise INCOMPLETE if any positive-weight component is missing/excluded or any trust dimension has insufficient direct evidence; otherwise COMPONENTS_PRESENT. Even COMPONENTS_PRESENT is not calibrated certainty. Do not collapse these diagnostics into a fabricated confidence probability. Calibration status remains UNCALIBRATED.

Current S2/S5 with trust and criticality: W=.45; observed-weight coverage=.60 if anomaly candidate is computable but excluded. Current S3: both W and observed-weight coverage=.45. Threat is missing in both; S3 additionally lacks anomaly semantics. This distinction remains visible despite equal primary denominators.

## 9. Trust integration

Consume TrustAssessment through `to_inference_dict()` and its documented public fields. The adapter strips audit before passing the view to numeric inference. Require entity_id=`asset:<source_id>` and a current assessment from the same caller-owned observation transaction. Use the post-observation composite, supplied trust_state_version and coverage. The caller enforces ordering/current pairing through opaque delivery context; never parse experimental event IDs to match inputs.

Do not instantiate another TrustModel, recompute weights/dimensions, undo current behavioral updates, or substitute previous trust to evade correlation. High/low numeric trust and insufficient evidence are separate descriptive concepts; define no qualitative cutoffs. All-neutral/prior-supported trust is usable as the declared existing estimate with prominent evidence limitations, not proof of reliable conduct. Reasons and evidence are explanatory records, not text to classify into another threat score.

## 10. Criticality semantics

`validate_event_asset_integrity` checks `asset_criticality` against the **target** VirtualAsset. Source type/zone/protocol are separate checks. Thus C describes affected asset consequence potential, not source criticality or operation-specific damage. MOTOR-02 is .91; PLC-03 is .95. These registry values are uncalibrated research proxies.

Use the validated field and verify agreement with the reference, rather than silently overriding inconsistent data. A legitimate command to critical machinery still has a baseline consequence contribution. There is no approved action-impact multiplier, execution simulator or damage model; do not invent one. Asset criticality is not maliciousness, and this additive index does not model a probability-times-loss expectation.

## 11. Anomaly semantics

Operational anomaly describes the current request relative to limits for its target, operation and **currently observed** mode. NORMAL MOTOR-02 set_speed uses [20,80]; HIGH_OUTPUT uses [60,95]; REDUCED [10,50]; MAINTENANCE [0,20]. ProductionState.ACTIVE does not imply NORMAL. Missing mode stays unknown. Never read logged anomaly scores, limit results or state snapshots as an inference shortcut.

A within-range check supplies a known-zero candidate. Missing PLC-03 write_register or PUMP-01 speed semantics supplies no candidate. A future independent anomaly source requires separately reviewed normalization and dependency declarations; no such detector exists now. Full plant snapshots contain additional state but the approved projection includes only production_state and operating_mode; do not expand it in this task.

## 12. Double-counting analysis

The current composite includes behavioral trust updated by these same limit checks and historical effects derived from prior conduct. Adding the same limit deviation directly as A would duplicate evidence. Treating lagged or attenuated updates as statistically independent would also be unjustified.

**DEFINED DESIGN:** For the current trust profile, exclude the operational-deviation anomaly component whenever TRUST is included. This is a fixed source-dependency rule, irrespective of sign, magnitude, scenario or current behavioral coverage. Retain computable A_candidate as an explanation diagnostic with EXCLUDED_CORRELATED. If no candidate can be computed, use MISSING instead. Do not switch inclusion on/off merely because deviation becomes nonzero; that would change denominators at the violation itself.

This intentionally sacrifices some instantaneous severity sensitivity to avoid recharging the same observation while preserving the frozen composite contract. S2 can still increase risk through distrust. Prior history may influence present risk: that is the trust contribution's purpose. We make no claim that all remaining components are statistically independent. Future threat/anomaly detectors must disclose shared evidence and receive a reviewed dependency policy before enabling their weights.

A future Risk-NoTrust ablation may include the operational anomaly because the overlapping trust term is absent. Report this substitution explicitly and also run a fixed-mask removal comparison (section 21). No extraction of a “behavior-free trust” or modification of frozen trust is authorized.

## 13. Component contributions

Every component reports original_weight, effective_weight, observed_value, included, status, reason_code, contribution and source/version. For W>0, included contributions sum to risk_score and effective weights sum to 1; excluded accounting zeros must accompany their explicit status. If W=0, all effective weights/contributions are null. Explain renormalization and dependency exclusions in deterministic reasons.

Illustration only, **not an executed risk result**: supplied T=.8, target C=.91, missing threat, correlated anomaly excluded gives weights TRUST=5/9, CRITICALITY=4/9; contributions .111111… and .404444…; R=.515555…. High target consequence can dominate this partial index. Existing action thresholds must not turn this illustrative value into a decision.

## 14. RiskAssessment contract

**DEFINED DESIGN:** A future immutable validated record contains:

- entity_id (source trust namespace), target_id, operation;
- threat_probability (nullable), threat_score_kind (UNAVAILABLE, CONFIDENCE, or CALIBRATED_PROBABILITY), distrust_score, criticality_score, anomaly_score (nullable observed candidate, possibly excluded);
- risk_score (nullable only when no weighted inputs), assessment_status;
- component_availability, coverage, component_contributions as specified above;
- trust_state_version (nullable with missing trust), trust_evidence_coverage and prior_only_dimensions;
- reasons (deterministic observable facts, exclusions and limitations);
- model_version, configuration_fingerprint, calibration_status;
- optional audit correlation metadata, attached after inference and excluded from the inference export.

Configuration identity covers original weights, missing/dependency policies, reference versions, normalization and supplied trust configuration identity. Keep it separate from frozen event/experiment identity. No wall-clock timestamps, random IDs or output paths influence scores or result fingerprints. Contract fields contain no labels, scenarios, phases, recommended actions or governance categories. Nullable fields must serialize as null, never NaN. Preserve exact decomposition with stable ordering and full-precision values; round only displays.

## 15. S1 expectations

Relatively stable source trust and target criticality imply relatively stable risk, not zero. Multiple targets/sources and changing coverage can cause differences; evaluate matched entity/target/operation/mask trajectories. MOTOR-02 requests within limits have zero anomaly candidates; PUMP-01 has missing limits. Both remain incomplete. No absence-of-detector statement means observed absence of threat.

## 16. S2 expectations

Observable mode-specific violations reduce trust in the evaluated observable-state profile. With fixed C and mask, a decrease in T produces an increase in R of `-(.25/.45)*delta_T`. The repeated anomaly candidate is excluded from primary fusion but explained. Do not require monotonically increasing risk under every arbitrary event sequence. No compromise transition, PLC-07 special case or malicious label enters computation.

## 17. S3 expectations

Successful authentication with unsupported write_register semantics yields missing anomaly and missing threat. Trust may increase slightly under its existing rules, so primary risk may decline slightly despite evaluator-known maliciousness. Report insufficient behavioral/context coverage and high target consequence. Do not force high risk or invent a register threshold. This is an acceptance case for honest uncertainty, not successful threat detection.

## 18. S5 expectations

Use observed HIGH_OUTPUT limits after the mode changes. Higher values within [60,95] give candidate zero, not a NORMAL-limit violation. Trust remains supported and risk must not rise solely because speeds exceed an old regime's maximum. No phase-triggered reset or adaptation is allowed. Frozen default profiles lacking required mode telemetry remain missing; the existing observable-state profile supplies it without a new generator change.

## 19. Leakage boundary

Only the exact existing runtime_observation projection, approved reference objects and public trust inference view may enter risk. Reject raw IndustrialEvent, enriched evaluation rows and unexpected fields. Source/target IDs permit lookup and attribution only, never scenario recognition. All inference must be invariant under mutation of evaluation labels and privileged metadata with approved observations fixed.

Forbidden: ground_truth, expected_safe_action, scenario ID, provenance phase/transition/causal tags, compromise markers, manifest policies, synthetic anomaly/prior trust/attack scores, experimental IDs/sequences/timestamps and raw snapshots. Audit metadata is attached afterward, not used for numeric scoring, coverage or explanations. EventManager continues validating integrity/provenance outside inference; validation does not provide answers. Evaluation alone may later join labels and transitions, with no feedback into inference or configuration selection.

## 20. Future evaluation metrics

Day 3E should use reproducible configurations and seeds, isolated trust state and separate risk outputs. Report per entity/target/operation/mask trajectories, initial/final/min/max/mean risk; observable-violation-aligned and separately evaluator-transition-aligned pre/post statistics; signed risk changes; and component contributions/coverage. Never subtract consecutive scores from unrelated entities as a within-entity response.

Measure onset delay from a supported observable violation to first positive matched risk change, reporting NOT_OBSERVED/null if absent and NOT_APPLICABLE/null when no eligible onset exists. Labels may additionally define offline strata. Missing scores remain missing, not zero; publish eligible denominators and coverage exclusions.

Descriptive benign-increase rate: positive matched deltas on BENIGN events divided by eligible BENIGN events, with a separate S5 regime-change stratum. Call this a diagnostic increase, not a validated false alarm. A “false escalation” threshold/persistence rule requires preregistration and calibration; existing action-named thresholds are not automatically suitable. Separate changes caused by criticality or mask from changes caused by distrust/deviation.

Report multi-seed mean, dispersion and missing counts; dependency exclusions; contribution trajectories; and coverage-stratified associations with evaluation outcomes. Correlation with malicious labels is not calibration, causal proof or general predictive accuracy. Do not report Brier/ECE as if risk were attack probability. Held-out outcomes and an explicit probabilistic target would be required for such a claim.

## 21. Ablation plan

Implement nothing yet. Future comparisons use identical event streams and frozen trust configurations, with separately identified policies:

| Variant | Planned change |
|---|---|
| Full available | All valid components allowed by dependency policy |
| Risk-NoTrust | Exclude TRUST; operational anomaly may become eligible; explicitly a substitution comparison |
| Risk-NoAnomaly | Exclude ANOMALY, including any independent future signal |
| Risk-NoThreat | Exclude THREAT |
| Criticality-only | Include only C, yielding R=C where present |

Renormalize retained original weights and record EXCLUDED_ABLATION separately from missing and correlated status. Also report a fixed-mask NoTrust removal that keeps the full model's anomaly exclusion, to isolate removal from substitution. Retain original-weight contributions alongside normalized scores to expose rescaling effects. Do not interpret scale changes as improved detection. Current NoThreat equals full available, and current NoAnomaly equals full available when trust is present: these are expected degenerate comparisons, not new empirical findings. Nondegenerate threat comparison must await a real signal.

## 22. Limitations

No calibrated threat detector, operation-impact model, independent anomaly detector, confidence probability or risk thresholds exist. S3 and PUMP-01 semantics are missing. Additive compensation can conceal particular hazards and is no safety guarantee. Partial renormalization changes scale; favorable trust priors can depress distrust despite incomplete evidence; dependency exclusion reduces immediate sensitivity. Evidence independence is not established. Snapshot state is pre-command, not a measured consequence of execution.

Existing config thresholds resemble actions but lack calibrated policy semantics; leave them untouched. Earlier TRUST_MODEL_SPEC text describes then-unimplemented trust and a missing S2 mode; later implementation/evaluation documents and the optional observable-state profile describe current capability. These are historical milestone records, not reasons to rewrite frozen code. No defect in trust is repaired by this specification.

## 23. Parameters requiring calibration

**PROVISIONAL PARAMETER / UNCALIBRATED:** risk weights .40/.25/.20/.15; existing action-named thresholds .20/.40/.55/.70/.85; registry criticalities; reused d_sat=1.0; and inherited trust priors, weights, evidence confidence and update rates. Preserve all existing values.

**FUTURE CALIBRATION REQUIREMENT:** held-out weighting/sensitivity studies, dependency-policy comparisons, operation-specific severity scales (especially zero-width limits), threat score validation, target/action consequence references, and threshold/delay/persistence evaluation protocols. Numerical weight-sum tolerance proposed 1e-9 is an engineering validation setting, not a fitted scientific parameter; reject weights outside tolerance rather than silently renormalizing the original configuration. Available-component renormalization is a distinct explicit operation.

## 24. Day-3B/3C implementation requirements

1. Add validated risk input/output/configuration contracts and deterministic arithmetic only when separately requested. Preserve public trust and event interfaces; do not activate existing action thresholds.
2. Use the exact approved observation view, post-observation trust inference contract and explicit dependency policy. Threat stays missing until separately implemented and reviewed. No detector, agent orchestration or runtime hook is authorized by this document alone.
3. Test bounds, invalid/nonfinite values, sums, exact contributions, known zero versus unknown, missing/all-missing inputs, prior-supported trust coverage, correlation exclusions and fixed-mask stability across zero/nonzero deviations.
4. Test source/target mismatch rejection, current assessment pairing, current-mode limits, missing modes/limits, S3 uncertainty and S5 conformance without scenario-dependent inference.
5. Add metamorphic tests that labels, provenance and audit IDs cannot change numeric results, reasons or coverage. Require repeatable normalized outputs/configuration identities and no Day-1 fingerprint changes.
6. Keep risk records separate from event logs. Defer metrics, ablations, calibration and all further agents to their explicitly authorized milestones.

Day 3A adds this document only. Verification results are reported after actual execution in the task response. Markdown-only changes require no Python syntax check. Stop after Day 3A.
