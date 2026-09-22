# Day 2E — trust evaluation harness and metrics

## Scope and reproducible execution

Measurement only: no trust equations, parameters, scenarios, evidence rules or agents changed. All parameters remain UNCALIBRATED. Trust is not a probability; no calibration scores, ECE/Brier measures, significance tests or claims of validated detection performance are produced.

From the repository root:

```bash
.venv/bin/python -m evaluation.evaluate_trust --events 10 --output results/day2e.json
.venv/bin/python -m evaluation.evaluate_trust --events 10 --output results/day2e-repeat.json
cmp results/day2e.json results/day2e-repeat.json
```

Defaults are S1/S2/S3/S5, seeds 42/123/456/789/2026 and ten events per run, with observable-state enrichment. Ten is the explicit diagnostic protocol, not a claim of sufficient sample size; use --events to run a separately identified larger study. The five seeds match the existing experiment seed list. Both commands were executed: 20 runs each, byte-identical output. Results are ignored by Git; code, formulas and compact tables here are retained. No Day-1 experiment files are overwritten.

## Boundary and data contract

`assess_observations` first projects every event and calls a fresh TrustAgent with source-local ordinal/delivery tokens. It completes all inference before the evaluator reads any labels or manifest/provenance metadata. `trajectory_records` then joins assessment inference exports to experiment_id, scenario_id, experimental sequence, phase, ground_truth, expected_safe_action and observable request/mode for offline analysis. Those joined records are evaluation-only and fail the agent's exact input schema. Original event IDs are not needed by the inference harness.

The output includes all dimension scores, composite and delta, previous composite, reasons, direct evidence, direction counts, coverage, observation count/version and joined evaluation fields. Raw generated events are validated against the existing manifest/experiment after assessments, separately from inference. Validation does not select a score or feed back any corrections. The input generator is the unchanged deterministic observable-state profile.

Top-level JSON includes runs and five-seed aggregates. Each run includes full experiment/configuration snapshots, manifest, trajectory, run metrics, per-entity metrics and limitations. Evaluation identity hashes experiment metadata plus model/evidence configurations and evaluation version (`day2e-v1`), separate from frozen experiment identity. JSON keys are sorted, nonfinite output is rejected, and no wall-clock time or output path participates in identity/results.

## Exact metric definitions

Let T_i be post-observation composite trust; delta_i is TrustAssessment.trust_delta for that source entity. Labels and intervention tau are evaluation-only. All comparisons use strict delta_i<0 without a tuned threshold. N is the number of records. Q is the set of observed entities.

- Initial trust I: mean over Q of the first record's previous_composite_trust, i.e. actual initialization before observations. Final F: mean over Q of each entity's last post-observation composite. Change=F-I. These are equal-entity means, not the last score of an arbitrary source in S1.
- Minimum/maximum: min/max T_i across post-observation records (initial priors are not included). Mean trust=ΣT_i/N, an observation-weighted mean. Per-entity outputs expose heterogeneous trajectories explicitly.
- Pre mean: mean T_i where sequence<tau. Post mean: mean T_i where sequence>=tau. These are sequence-defined, not guessed from phase text. Phase remains available for optional offline grouping only.
- Reference: mean last pre-intervention score over entities with both pre and post records. First post trust: mean first post score for that same cohort. For single-source S2/S3/S5 these are exactly tau-1 and tau. In multi-source runs they are nearest observations per entity, not necessarily adjacent global events.
- Degradation magnitude=mean over that cohort of (last pre score - final post score). Signed: positive means loss; negative means gain. Never clip gains to zero or label them as attacks. No common pre/post entity means null.
- Degradation delay: choose the earliest post-intervention record with delta<0; sequence_delay=its sequence-tau. Also report zero-based entity_observation_delay from that entity's first post-intervention observation. Status is OBSERVED, NOT_OBSERVED when no post decrease occurs, or NOT_APPLICABLE with no intervention. This measures onset of any trust loss, not a detection threshold. The frozen model can decrease only from current/prior negative evidence; direct-negative coverage is reported separately.
- Eligible legitimate observations: records whose evaluation ground_truth is exactly BENIGN, including the first observation and both S5 regimes. False count=Σ1(BENIGN and delta<0); false rate=count/number of BENIGN records. SUSPICIOUS records are not included. Historical penalties on a currently benign event count as false degradation under this descriptive definition; it does not establish causation.
- Negative-response count=Σ1(MALICIOUS and delta<0); rate=count/number of MALICIOUS records. The denominator includes malicious observations with missing evidence, so coverage gaps are not hidden by selecting favorable observations. Also count malicious records lacking direct negative evidence.
- Volatility=Σ|delta_i|/N, including the first prior-to-observation update. It does not subtract scores of unrelated entities. This is mean absolute update, not standard deviation of scores.
- Direct evidence coverage for each dimension: positive/negative/insufficient count is the number of observations whose effective coverage list contains that status; rates divide by N. NEUTRAL count is the number with at least one direct neutral record for that dimension. Neutral and insufficient overlap deliberately; positive/negative can overlap if both are present. These four rates are not a probability partition. Internal synthesized HISTORY may change TH despite insufficient direct HISTORY coverage.
- Empty sets/zero denominators return null, not zero. Counts remain zero. Intervention statistics are null when unavailable. NOT_OBSERVED delays are never replaced by zero in aggregation.
- Across seeds: equal-run arithmetic mean, population standard deviation sqrt(Σ(x-mean)^2/K), minimum and maximum of defined scalar values; include defined/missing run counts. Aggregate coverage rates and delay availability are retained. No significance tests.

## Recovery and calibration

Current scenarios do not contain a defined negative-then-legitimate recovery period. Recovery is reported as NOT_MEASURABLE_WITH_CURRENT_SCENARIOS with null delay, not NOT_OBSERVED or zero. No generic recovery-time algorithm was added without an agreed recovery window/threshold. NOT_OBSERVED is used for measurable degradation onset that did not occur (S3/S5). No outcomes or new recovery scenarios were fabricated.

Known prior .80, unknown prior .50, weights .20/.25/.25/.15/.15, positive .01, negative .10, recovery .005 and recency .25 remain unchanged. No probability interpretation, parameter fitting or calibration is justified by this harness.

## Observations: seed 42

| Scenario | Initial | Final | Mean | Minimum | Pre mean | Post mean | Degradation | False rate | Negative response | Delay |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| S1 | 0.800000000 | 0.800770654 | 0.800650215 | 0.800225000 | N/A | N/A | N/A | 0.000000000 | N/A | {'entity_observation_delay': None, 'sequence_delay': None, 'status': 'NOT_APPLICABLE'} |
| S2 | 0.800000000 | 0.780587294 | 0.795457739 | 0.780587294 | 0.801081143 | 0.789834336 | 0.021235802 | 0.000000000 | 1.000000000 | {'entity_observation_delay': 0, 'sequence_delay': 0, 'status': 'OBSERVED'} |
| S3 | 0.800000000 | 0.802483447 | 0.801336216 | 0.800225000 | 0.800706143 | 0.801966289 | -0.001285351 | 0.000000000 | 0.000000000 | {'entity_observation_delay': None, 'sequence_delay': None, 'status': 'NOT_OBSERVED'} |
| S5 | 0.800000000 | 0.803733447 | 0.802023716 | 0.800350000 | 0.801081143 | 0.802966289 | -0.001910351 | 0.000000000 | N/A | {'entity_observation_delay': None, 'sequence_delay': None, 'status': 'NOT_OBSERVED'} |

S2 immediately before intervention: .801823096; at intervention: .798281429. S5 immediately before: .801823096; at transition: .802201697. S1 mean absolute update: .000308262. S1 behavioral coverage was 60% positive/40% insufficient (PUMP-01 has no configured speed limits). S3 behavioral and contextual coverage was 100% insufficient despite 100% positive identity evidence. S2 behavior was 50% positive/50% negative. S5 behavior was 100% positive and 0% negative. Direct history/context coverage remained insufficient throughout.

## Observations: events 4–8, seed 42

| Scenario/event | Value | Mode | Behavior coverage | TB | Composite | Delta | Observable reason |
|---|---:|---|---|---:|---:|---:|---|
| S2/4 | 63 | NORMAL | POSITIVE | 0.802000000 | 0.801447461 | +0.000371680 | set_speed: WITHIN_LIMIT: Value 63 in NORMAL; inclusive limit [20, 80], deviation 0. |
| S2/5 | 48 | NORMAL | POSITIVE | 0.802500000 | 0.801823096 | +0.000375635 | set_speed: WITHIN_LIMIT: Value 48 in NORMAL; inclusive limit [20, 80], deviation 0. |
| S2/6 | 97 | NORMAL | NEGATIVE | 0.788333333 | 0.798281429 | -0.003541667 | set_speed: OUTSIDE_LIMIT: Value 97 in NORMAL; inclusive limit [20, 80], deviation 0.283333333333. |
| S2/7 | 97 | NORMAL | NEGATIVE | 0.774166667 | 0.794688645 | -0.003592784 | set_speed: OUTSIDE_LIMIT: Value 97 in NORMAL; inclusive limit [20, 80], deviation 0.283333333333. |
| S2/8 | 94 | NORMAL | NEGATIVE | 0.762500000 | 0.791468016 | -0.003220629 | set_speed: OUTSIDE_LIMIT: Value 94 in NORMAL; inclusive limit [20, 80], deviation 0.233333333333. |
| S3/4 | 55 | NORMAL | INSUFFICIENT | 0.800000000 | 0.800947461 | +0.000246680 | write_register: MISSING_LIMIT: No approved target/operation limits; no conformance conclusion. |
| S3/5 | 55 | NORMAL | INSUFFICIENT | 0.800000000 | 0.801198096 | +0.000250635 | write_register: MISSING_LIMIT: No approved target/operation limits; no conformance conclusion. |
| S3/6 | 999 | NORMAL | INSUFFICIENT | 0.800000000 | 0.801451697 | +0.000253601 | write_register: MISSING_LIMIT: No approved target/operation limits; no conformance conclusion. |
| S3/7 | 999 | NORMAL | INSUFFICIENT | 0.800000000 | 0.801707523 | +0.000255826 | write_register: MISSING_LIMIT: No approved target/operation limits; no conformance conclusion. |
| S3/8 | 999 | NORMAL | INSUFFICIENT | 0.800000000 | 0.801965017 | +0.000257494 | write_register: MISSING_LIMIT: No approved target/operation limits; no conformance conclusion. |
| S5/4 | 68 | NORMAL | POSITIVE | 0.802000000 | 0.801447461 | +0.000371680 | set_speed: WITHIN_LIMIT: Value 68 in NORMAL; inclusive limit [20, 80], deviation 0. |
| S5/5 | 53 | NORMAL | POSITIVE | 0.802500000 | 0.801823096 | +0.000375635 | set_speed: WITHIN_LIMIT: Value 53 in NORMAL; inclusive limit [20, 80], deviation 0. |
| S5/6 | 85 | HIGH_OUTPUT | POSITIVE | 0.803000000 | 0.802201697 | +0.000378601 | set_speed: WITHIN_LIMIT: Value 85 in HIGH_OUTPUT; inclusive limit [60, 95], deviation 0. |
| S5/7 | 85 | HIGH_OUTPUT | POSITIVE | 0.803500000 | 0.802582523 | +0.000380826 | set_speed: WITHIN_LIMIT: Value 85 in HIGH_OUTPUT; inclusive limit [60, 95], deviation 0. |
| S5/8 | 84 | HIGH_OUTPUT | POSITIVE | 0.804000000 | 0.802965017 | +0.000382494 | set_speed: WITHIN_LIMIT: Value 84 in HIGH_OUTPUT; inclusive limit [60, 95], deviation 0. |

## Observations: five-seed aggregates

All five seeds included. Each statistic has K=5 unless shown as unavailable. Full aggregate statistics for every scalar metric and coverage rate are in reproducible JSON.

| Scenario | Metric | Mean | Population SD | Minimum | Maximum |
|---|---|---:|---:|---:|---:|
| S1 | final_trust | 0.800629241 | 0.000116639 | 0.800464583 | 0.800770654 |
| S1 | mean_trust | 0.800510367 | 0.000111363 | 0.800368750 | 0.800650215 |
| S1 | degradation_magnitude | N/A | N/A | N/A | N/A |
| S1 | false_degradation_rate | 0.000000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| S1 | negative_response_rate | N/A | N/A | N/A | N/A |
| S1 | degradation_sequence_delay | N/A | N/A | N/A | N/A |
| S1 | volatility_mean_absolute_update | 0.000293711 | 0.000018391 | 0.000267891 | 0.000317891 |
| S2 | final_trust | 0.772803896 | 0.005448757 | 0.765577447 | 0.780587294 |
| S2 | mean_trust | 0.793264842 | 0.001781087 | 0.790727360 | 0.795457739 |
| S2 | degradation_magnitude | 0.029019200 | 0.005448757 | 0.021235802 | 0.036245649 |
| S2 | false_degradation_rate | 0.000000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| S2 | negative_response_rate | 1.000000000 | 0.000000000 | 1.000000000 | 1.000000000 |
| S2 | degradation_sequence_delay | 0.000000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| S2 | volatility_mean_absolute_update | 0.003084230 | 0.000544876 | 0.002305890 | 0.003806874 |
| S3 | final_trust | 0.802483447 | 0.000000000 | 0.802483447 | 0.802483447 |
| S3 | mean_trust | 0.801336216 | 0.000000000 | 0.801336216 | 0.801336216 |
| S3 | degradation_magnitude | -0.001285351 | 0.000000000 | -0.001285351 | -0.001285351 |
| S3 | false_degradation_rate | 0.000000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| S3 | negative_response_rate | 0.000000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| S3 | degradation_sequence_delay | N/A | N/A | N/A | N/A |
| S3 | volatility_mean_absolute_update | 0.000248345 | 0.000000000 | 0.000248345 | 0.000248345 |
| S5 | final_trust | 0.803733447 | 0.000000000 | 0.803733447 | 0.803733447 |
| S5 | mean_trust | 0.802023716 | 0.000000000 | 0.802023716 | 0.802023716 |
| S5 | degradation_magnitude | -0.001910351 | 0.000000000 | -0.001910351 | -0.001910351 |
| S5 | false_degradation_rate | 0.000000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| S5 | negative_response_rate | N/A | N/A | N/A | N/A |
| S5 | degradation_sequence_delay | N/A | N/A | N/A | N/A |
| S5 | volatility_mean_absolute_update | 0.000373345 | 0.000000000 | 0.000373345 | 0.000373345 |

## Interpretation and limitations

Observation: all 25 malicious-labeled S2 observations across five runs had negative deltas; measured onset delay was zero for all five seeds. Interpretation: the current trust subsystem responds to these observable NORMAL-limit violations. Limitation: this is not a general compromised-device detector evaluation; the scenarios are synthetic, short, and parameters uncalibrated.

Observation: S3 has zero negative responses to its 25 malicious-labeled observations, with 100% insufficient behavior/context coverage. **BEHAVIORAL SEMANTICS INSUFFICIENT**: write_register lacks approved range or authorization rules. Rising trust reflects repeated authentication/device-reference support and associated history, not evidence that the request is authorized or safe. No S3 rule was introduced.

Observation: S1/S5 had zero false degradation for every seed, and S5 had no negative behavioral evidence under HIGH_OUTPUT. Interpretation: mode-aware limits preserve these legitimate fixture values. Limitation: no claim of robustness to arbitrary drift, calibration or complete safety follows. S1 additionally lacks PUMP-01 operational semantics. S3/S5 final scores are identical across seeds because their effective evidence sequences are identical, even where generated values differ; this is not evidence of statistical certainty.

Recovery remains unmeasurable. No baseline comparison, classification threshold, probabilistic calibration, ECE/Brier score, significance test or trust tuning was performed. Large-scale/long-duration experiments remain future work. Mean trust is observation-weighted whereas initial/final summaries are entity-weighted; use per-entity metrics to avoid misleading mixed-source conclusions.

## Files, tests and boundary verification

Inspected all five authoritative documents and agent/assessment/state/evidence/model/extractor, generator/manifest/provenance/experiment and evaluation scaffolding. Added evaluation/trust_metrics.py, evaluation/evaluate_trust.py, tests/test_trust_metrics.py and this document. Modified only .gitignore to exclude generated results/. No existing tests or inference implementation changed.

278 tests passed, 0 failed, including all previous 264 tests. Tests verify equations, denominators, missing intervention, unobserved delay, recovery-not-measurable, entity-aware summaries, coverage overlap, five-seed aggregation, individually deterministic runs and label-mutation invariance. A guard raises if inference accesses evaluation-only fields; it passed. Altering labels changes evaluation counts but not assessments; phase metadata is joined only afterward. Changing the evaluator's intervention partition changes only pre/post metrics. Enriched trajectory records are rejected by the agent input schema. Complete repeated CLI output was byte-identical.

Run syntax checks for the new Python files and git diff --check as reported in the task response. No Risk/Threat/Planning/Decision/Governance/adaptation/authorization/LLM implementation was added. Stop after Day 2E.
