# Day 3E — deterministic risk evaluation

## Objective and boundary

Evaluation only. No inference code, configurations, scenarios, limits or thresholds changed. Inspected the four authoritative risk documents, trust/risk agents and contracts, builder/model, risk.yaml, and the existing Day-2E harness/metrics. Added evaluation/risk_metrics.py, evaluation/evaluate_risk.py, tests/test_risk_evaluation.py and this document. Existing results/ ignore rules suffice.

For every observation the harness obtains only runtime_observation, calls TrustAgent with source-local delivery/count bookkeeping, and immediately passes the resulting TrustAssessment to RiskAgent with its expected version. It completes ALL inference before reading labels, provenance or transition metadata. Afterward EventManager validates the generated experiment, and trajectory_records joins evaluation metadata to immutable inference exports.

experiment_id, scenario_id, sequence_number, phase, ground_truth and expected_safe_action in trajectory records are evaluation-only. Full trust inference exports are retained for boundary verification. Risk records include all component values, availability, coverage, original/effective weights, contributions, reasons, trust version and risk model version. Joined rows must never be passed back to an agent. A guard test raises if the inference loop reads any privileged metadata.

## Protocol and reproducibility

Five frozen seeds: 42, 123, 456, 789, 2026. Scenarios S1, S2, S3, S5. Ten events each, observable-state profile, fresh agents per run: 20 runs. Ten-event diagnostics follow Day 2E; this is not a claim of adequate statistical power. No seed selection, tuning, significance tests or competing baseline is introduced.

Executed from the repository root:

```bash
.venv/bin/python -m evaluation.evaluate_risk --events 10 --output results/day3e.json
.venv/bin/python -m evaluation.evaluate_risk --events 10 --output results/day3e-repeat.json
cmp results/day3e.json results/day3e-repeat.json
```

Both runs completed and files were byte-identical. JSON uses sorted keys, finite numbers and no wall-clock/output-path metadata. Evaluation version is day3e-v1. Each evaluation ID hashes the experiment snapshot plus trust/evidence configuration, risk configuration identity/model version and evaluation tolerance. This identity is separate from frozen Day-1 event identity. Machine-readable output contains trajectories, per-run metrics, aggregate metrics, configurations, seeds and limitations.

## Exact metric definitions

Tolerance epsilon=1e-12 is a numeric comparison tolerance, not an attack/action threshold. An increase means delta > epsilon.

Comparison groups are (source_id, target_id, operation, component-availability pattern). Within each group, delta is current risk minus the previous observation's risk; unrelated intervening events do not change that predecessor. First group observations have no delta. A null score breaks the chain: do not bridge over null. Operating mode is deliberately not in the group key, so legitimate mode changes remain testable. Coverage-pattern changes establish a separate comparison stream and are not silently charged as behavioral escalation.

- Initial/final: equal-group mean of first/last recorded risk for groups with both endpoints defined. The cohort is identical for both. Initial is the first assessed risk, not an invented pre-event risk. Singleton groups contribute equal endpoints. Net change = final - initial.
- Minimum/maximum/mean: over all defined post-observation scores; mean is observation-weighted. These can differ from group-weighted endpoints in mixed-source S1.
- Mean absolute risk update = sum(abs(delta))/number of eligible deltas. For one complete group this is sum over t=2..n divided by n-1. No first-observation change is fabricated. Counts expose exclusions.
- Pre mean: mean defined scores with sequence < tau. Post mean: mean defined scores with sequence >= tau. Signed escalation = post - pre, preserving reductions. These are pooled observation-weighted summaries; use caution if group composition differs.
- Risk before/at transition: exact sequence tau-1/tau score, or null if absent/null. transition_risk_delta is the matched-group delta at tau. In the present single-source/target transition scenarios these are adjacent events of the same group.
- Response delay: earliest post-transition eligible delta > epsilon, minus tau; OBSERVED with delay 0 if immediate. NOT_OBSERVED/null if none; NOT_APPLICABLE/null if no transition. For S5 this is a descriptive increase-onset diagnostic, not an expected attack response. Insufficient eligible post observations cannot establish absence of danger; check eligible counts.
- Legitimate eligibility: ground_truth exactly BENIGN and a defined delta. False escalation count = eligible benign deltas > epsilon; rate divides by eligible benign count. Also report legitimate pre-transition rate. SUSPICIOUS is excluded. This is a descriptive increase under legitimate labels, not a validated false-alarm classifier.
- Malicious eligibility: ground_truth exactly MALICIOUS and a defined delta. Positive response rate = eligible malicious deltas > epsilon divided by eligible malicious count. Missing behavioral evidence does not exclude a defined score/delta, so S3's failure remains visible.
- Component mean: arithmetic mean of defined contributions. Component transition change = post contribution mean - pre contribution mean. Unavailable component contributions are existing accounting zeros for defined risk, not imputed signal values.
- Mean component share: mean(contribution/risk) over records with risk > 0 and defined contribution. This is a mean of per-record ratios, not ratio of means, not configured or effective weight.
- Coverage min/mean/max: over all records, including null-risk records. Availability rate for each component = AVAILABLE count / all records, using explicit status; excluded-correlated is unavailable for fusion.
- Null risk: excluded from score means/extrema, retained in null counts; excludes adjacent deltas and invalid endpoints. Null contributions are excluded from contribution means. Zero risk is a valid score but has undefined contribution shares. Empty denominators yield null, never zero. Counts remain zero.
- Across seeds: equal-run arithmetic mean, population SD sqrt(sum((x-mean)^2)/K), minimum and maximum of defined values; report defined/missing run counts. Null delay is never aggregated as zero. Recursive aggregation includes contributions, shares, coverage and availability; status counts remain explicit.

Phase text remains in trajectory records for optional offline grouping. Canonical pre/post metrics use the explicit manifest transition sequence, so changing phase text alone does not move tau. Tests independently change evaluator tau and verify grouping changes without recomputing inference.

## Seed-42 results

All scores and contributions below are observed command results, rounded only for display. Full trajectories, including S3, are in the JSON.

| Metric | S1 | S2 | S3 | S5 |
|---|---:|---:|---:|---:|
| comparison_group_count | 6.000000000 | 1.000000000 | 1.000000000 | 1.000000000 |
| defined_risk_count | 10.000000000 | 10.000000000 | 10.000000000 | 10.000000000 |
| eligible_benign_count | 4.000000000 | 4.000000000 | 4.000000000 | 9.000000000 |
| eligible_malicious_count | 0.000000000 | 5.000000000 | 5.000000000 | 0.000000000 |
| eligible_update_count | 4.000000000 | 9.000000000 | 9.000000000 | 9.000000000 |
| endpoint_group_count | 6.000000000 | 1.000000000 | 1.000000000 | 1.000000000 |
| false_escalation_count | 0.000000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| false_escalation_rate | 0.000000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| final_risk | 0.504060927 | 0.526340392 | 0.531953641 | 0.513481418 |
| initial_risk | 0.504184245 | 0.515361111 | 0.533208333 | 0.515361111 |
| max_coverage | 0.450000000 | 0.450000000 | 0.450000000 | 0.450000000 |
| maximum_risk | 0.515361111 | 0.526340392 | 0.533208333 | 0.515361111 |
| mean_absolute_risk_update | 0.000184977 | 0.001401784 | 0.000139410 | 0.000208855 |
| mean_coverage | 0.450000000 | 0.450000000 | 0.450000000 | 0.450000000 |
| mean_risk | 0.506305436 | 0.518079034 | 0.532590991 | 0.514431269 |
| min_coverage | 0.450000000 | 0.450000000 | 0.450000000 | 0.450000000 |
| minimum_risk | 0.492668077 | 0.514542725 | 0.531953641 | 0.513481418 |
| net_risk_change | -0.000123318 | 0.010979281 | -0.001254693 | -0.001879693 |
| null_risk_count | 0.000000000 | 0.000000000 | 0.000000000 | 0.000000000 |
| observation_count | 10.000000000 | 10.000000000 | 10.000000000 | 10.000000000 |
| positive_risk_response_count | 0.000000000 | 5.000000000 | 0.000000000 | 0.000000000 |
| positive_risk_response_rate | N/A | 1.000000000 | 0.000000000 | N/A |
| post_mean_risk | N/A | 0.521203147 | 0.532240950 | 0.513907617 |
| pre_benign_false_escalation_rate | N/A | 0.000000000 | 0.000000000 | 0.000000000 |
| pre_mean_risk | N/A | 0.514954921 | 0.532941032 | 0.514954921 |
| risk_at_transition | N/A | 0.516510317 | 0.532526835 | 0.514332391 |
| risk_before_transition | N/A | 0.514542725 | 0.532667725 | 0.514542725 |
| signed_risk_escalation | N/A | 0.006248226 | -0.000700081 | -0.001047304 |
| transition_risk_delta | N/A | 0.001967593 | -0.000140889 | -0.000210334 |

Response delay: S1 NOT_APPLICABLE; S2 OBSERVED, 0; S3 NOT_OBSERVED; S5 NOT_OBSERVED.

| Scenario | Mean distrust contribution | Mean criticality contribution | Mean distrust share | Mean criticality share | Transition distrust change | Transition criticality change |
|---|---:|---:|---:|---:|---:|---:|
| S1 | 0.110749881 | 0.395555556 | 0.218842249 | 0.781157751 | N/A | N/A |
| S2 | 0.113634589 | 0.404444444 | 0.219290844 | 0.780709156 | 0.006248226 | 0.000000000 |
| S3 | 0.110368769 | 0.422222222 | 0.207229432 | 0.792770568 | -0.000700081 | 0.000000000 |
| S5 | 0.109986825 | 0.404444444 | 0.213801685 | 0.786198315 | -0.001047304 | 0.000000000 |

Mean threat/anomaly contributions and shares are zero throughout. Their signal values remain null.

## Five-seed aggregates

| Scenario | Metric | Mean | Population SD | Minimum | Maximum | Defined/missing |
|---|---|---:|---:|---:|---:|---|
| S1 | initial_risk | 0.504322996 | 0.001953337 | 0.502568158 | 0.507955150 | 5/0 |
| S1 | final_risk | 0.504240762 | 0.001933533 | 0.502491397 | 0.507832972 | 5/0 |
| S1 | mean_risk | 0.504160907 | 0.003109228 | 0.499768707 | 0.508615929 | 5/0 |
| S1 | net_risk_change | -0.000082234 | 0.000035920 | -0.000123318 | -0.000032552 | 5/0 |
| S1 | mean_absolute_risk_update | 0.000161815 | 0.000025350 | 0.000130208 | 0.000184977 | 5/0 |
| S1 | pre_mean_risk | N/A | N/A | N/A | N/A | 0/5 |
| S1 | post_mean_risk | N/A | N/A | N/A | N/A | 0/5 |
| S1 | signed_risk_escalation | N/A | N/A | N/A | N/A | 0/5 |
| S1 | false_escalation_rate | 0.000000000 | 0.000000000 | 0.000000000 | 0.000000000 | 5/0 |
| S1 | positive_risk_response_rate | N/A | N/A | N/A | N/A | 0/5 |
| S2 | initial_risk | 0.515361111 | 0.000000000 | 0.515361111 | 0.515361111 | 5/0 |
| S2 | final_risk | 0.530664502 | 0.003027087 | 0.526340392 | 0.534679196 | 5/0 |
| S2 | mean_risk | 0.519297310 | 0.000989493 | 0.518079034 | 0.520707022 | 5/0 |
| S2 | net_risk_change | 0.015303391 | 0.003027087 | 0.010979281 | 0.019318085 | 5/0 |
| S2 | mean_absolute_risk_update | 0.001882240 | 0.000336343 | 0.001401784 | 0.002328318 | 5/0 |
| S2 | pre_mean_risk | 0.514954921 | 0.000000000 | 0.514954921 | 0.514954921 | 5/0 |
| S2 | post_mean_risk | 0.523639699 | 0.001978986 | 0.521203147 | 0.526459124 | 5/0 |
| S2 | signed_risk_escalation | 0.008684778 | 0.001978986 | 0.006248226 | 0.011504203 | 5/0 |
| S2 | false_escalation_rate | 0.000000000 | 0.000000000 | 0.000000000 | 0.000000000 | 5/0 |
| S2 | positive_risk_response_rate | 1.000000000 | 0.000000000 | 1.000000000 | 1.000000000 | 5/0 |
| S3 | initial_risk | 0.533208333 | 0.000000000 | 0.533208333 | 0.533208333 | 5/0 |
| S3 | final_risk | 0.531953641 | 0.000000000 | 0.531953641 | 0.531953641 | 5/0 |
| S3 | mean_risk | 0.532590991 | 0.000000000 | 0.532590991 | 0.532590991 | 5/0 |
| S3 | net_risk_change | -0.001254693 | 0.000000000 | -0.001254693 | -0.001254693 | 5/0 |
| S3 | mean_absolute_risk_update | 0.000139410 | 0.000000000 | 0.000139410 | 0.000139410 | 5/0 |
| S3 | pre_mean_risk | 0.532941032 | 0.000000000 | 0.532941032 | 0.532941032 | 5/0 |
| S3 | post_mean_risk | 0.532240950 | 0.000000000 | 0.532240950 | 0.532240950 | 5/0 |
| S3 | signed_risk_escalation | -0.000700081 | 0.000000000 | -0.000700081 | -0.000700081 | 5/0 |
| S3 | false_escalation_rate | 0.000000000 | 0.000000000 | 0.000000000 | 0.000000000 | 5/0 |
| S3 | positive_risk_response_rate | 0.000000000 | 0.000000000 | 0.000000000 | 0.000000000 | 5/0 |
| S5 | initial_risk | 0.515361111 | 0.000000000 | 0.515361111 | 0.515361111 | 5/0 |
| S5 | final_risk | 0.513481418 | 0.000000000 | 0.513481418 | 0.513481418 | 5/0 |
| S5 | mean_risk | 0.514431269 | 0.000000000 | 0.514431269 | 0.514431269 | 5/0 |
| S5 | net_risk_change | -0.001879693 | 0.000000000 | -0.001879693 | -0.001879693 | 5/0 |
| S5 | mean_absolute_risk_update | 0.000208855 | 0.000000000 | 0.000208855 | 0.000208855 | 5/0 |
| S5 | pre_mean_risk | 0.514954921 | 0.000000000 | 0.514954921 | 0.514954921 | 5/0 |
| S5 | post_mean_risk | 0.513907617 | 0.000000000 | 0.513907617 | 0.513907617 | 5/0 |
| S5 | signed_risk_escalation | -0.001047304 | 0.000000000 | -0.001047304 | -0.001047304 | 5/0 |
| S5 | false_escalation_rate | 0.000000000 | 0.000000000 | 0.000000000 | 0.000000000 | 5/0 |
| S5 | positive_risk_response_rate | N/A | N/A | N/A | N/A | 0/5 |

## Coverage and exact attribution

Observed all 200 records: min/mean/max weighted coverage .45. Trust and criticality availability 100%; threat and anomaly availability 0%. No unexpected availability deviation occurred. No risk was null in these scenario runs; null handling is verified with independent fixtures.

S2 seed 42 post-minus-pre mean risk change is +.006248226020954317; distrust contribution change is +.006248226020954317; criticality contribution change is exactly zero. At event 5→6, risk increases .001967592592592604. All five seeds show positive post-mean escalation and immediate response, and every post-transition observation has increasing risk with declining trust. All 25 eligible malicious S2 observations show positive risk response. This is algebraic attribution, not a cross-scenario correlation or causal detection claim.

S5: 0/5 seeds have a positive transition delta or any false escalation; all 45 eligible benign deltas are nonpositive. S1: 0/5 runs have false escalation among eligible matched-group updates. Group-first exclusions and changing S1 targets explain why eligible count is less than event count.

S3 numeric risk trajectories, component contributions and coverage are identical across all five seeds, explicitly checked. All 25 eligible malicious observations have no positive response; delay is NOT_OBSERVED for every seed. Identical effective evidence can produce identical outputs despite varied synthetic values; this is not validation.

## Scientific interpretation

**S1 — OBSERVATION:** seed-42 mean risk .506305436, false count/rate 0/0, mean absolute update .000184977; criticality contributes about 78.12% of risk on average. **INTERPRETATION:** stable matched conduct coexists with nonzero consequence potential. **LIMITATION:** heterogeneous targets and short streams make pooled levels unsuitable as attack indicators; some operations lack limits.

**S2 — OBSERVATION:** seed-42 pre/post means .514954921/.521203147, immediate risk .514542725→.516510317, final/max .526340392, delay 0, malicious positive-response rate 1, legitimate pre false rate 0. **INTERPRETATION:** rising distrust accounts for escalation with fixed criticality. **LIMITATION:** threat and independent anomaly are unavailable; responding to operational-limit violations does not demonstrate general attack detection.

**S3 — OBSERVATION:** pre/post means .532941032/.532240950, signed escalation -.000700081, malicious positive-response rate 0, no observed positive-response delay. **INTERPRETATION:** high target criticality dominates the absolute score while available trust improves slightly. **LIMITATION: BEHAVIORAL SEMANTICS INSUFFICIENT; THREAT SIGNAL UNAVAILABLE.** No credential-compromise detection was established.

**S5 — OBSERVATION:** pre/post means .514954921/.513907617, signed change -.001047304, immediate risk .514542725→.514332391, false escalation 0/9 eligible observations. **INTERPRETATION:** legitimate HIGH_OUTPUT change adds no stale-mode anomaly; supported trust slightly reduces concern. **LIMITATION:** this fixture does not establish robustness to arbitrary process change or safety.

Risk_score is NOT attack probability. S3's higher absolute score can reflect target criticality, not better detection. No risk>.5 classification, action threshold evaluation, probabilistic calibration or accuracy claim is made.

## Verification and future work

411 tests passed, 0 failed, including all prior 400 tests. Eleven new cases cover hand-calculable equations, signed changes, delay/tolerance, rates, shares, coverage, null/empty/zero denominators, matched-group deltas, metadata guard, leakage invariance for all four scenarios, deterministic complete 20-run replay and empty-run behavior. Label mutation changes evaluation denominators without changing TrustAssessment or RiskAssessment. Phase mutation changes joined labels only; evaluator transition changes affect grouping only. Syntax and whitespace checks passed for added files.

All seeds and results are retained. No null is disguised as zero. Scores and parameters remain UNCALIBRATED. Ten-event synthetic runs, incomplete operational semantics, matched-group eligibility and favorable trust priors limit interpretation. No baseline comparison, significance test, adaptation or parameter calibration was performed.

Future Risk-Full/NoTrust/NoThreat/NoAnomaly/criticality-only evaluations can reuse trajectory records, generic contribution/availability metrics and configuration-specific evaluation identities. No ablation is implemented; contract restrictions and correlated-source eligibility must be addressed explicitly in a later task. Threshold sensitivity remains deferred to Decision/Governance evaluation.

RiskModel/RiskAgent, TrustModel/TrustAgent, scenarios, limits, weights and thresholds are unchanged. No other agents, detectors, adaptation, authorization or LLM/LangGraph were implemented. Stop after Day 3E.
