# Publication results analysis (frozen V1)

This analysis uses only the frozen 20-seed publication artifact (`92c0f6486045e9639cd3c873c1b8853c0024ffbd3f9201e5a76ddb85a8d1dc84`) and its derived table and figure data. It is an analysis record, not manuscript prose.

## Experiment summary

The matrix contains seven configurations, S1--S9, and 20 seed-level replications. Seed is the replication unit; events are not independent samples. Event-weighted and scenario-balanced values must be reported separately because S1--S6 contain 10 events per stream and S7--S9 contain 50. The machine-readable summaries are `results/tables/TABLE_A_OVERALL_CONFIGURATION_METRICS.json` and `TABLE_B_PER_SCENARIO_METRICS.json`.

## Research questions

| Question | Finding | Status |
|---|---|---|
| RQ1 decision effectiveness | Controlled S7 separates safe review from uninterrupted autonomy: FULL_STATIC is 49/50 exact with 1/25 unsafe; NO_ASSURANCE is 25/50 exact with 25/25 unsafe. | Supported in controlled S7 evidence |
| RQ2 trust awareness | Dynamic trust rises 0.80035 to 0.819225 in S7; fixed NoTrust is 0.80, yet actions match. | NO_OBSERVED_DECISION_EFFECT in S7 |
| RQ3 adaptation | S8 is an explained regime-change control. Governed adaptation changes behavioral-reference interpretation where eligible; action improvement is not demonstrated when actions match. | Interpretation effect only |
| RQ4 governance/explainability | Bound proposals, governance records, execution authorization and provenance provide traceability. NO_GOVERNANCE is invalid because execution consumes its authorization artifact. | Traceability evidence; no direct governance ablation |
| RQ5 architecture | Drift plus assurance is action-causal in S7. Trust, risk and correlation do not show action causality there. | Component-specific, not general superiority |

## Hypotheses

H1 (trust safety contribution): **not demonstrated** for S7; NO_TRUST actions match FULL_STATIC. H2 (adaptation): **partially supported** at interpretation level, not demonstrated as an action improvement. H3 (governance): **not directly tested causally**. H4 (multi-agent architecture): **not demonstrated as general superiority** against a learned single-agent baseline. H5 (traceability): **supported for recorded provenance/bindings**, not for latency claims.

## S7 causal analysis

Each seed has 50 events: 25 evaluator-annotated unsafe-eligible later-phase events. FULL_STATIC produces 24 persistent unexplained drift assessments, 24 assurance restrictions, 24 review decisions, and 1 remaining unsafe action: exact 49/50, unsafe 1/25 (4%), review 24/50 (48%), autonomous 26/50 (52%). NO_ASSURANCE and NO_DRIFT each produce exact 25/50, unsafe 25/25 (100%), no reviews and 50/50 autonomous execution. The absolute controlled unsafe-rate difference is 96 percentage points; the relative reduction is 96% from the NO_ASSURANCE/NO_DRIFT reference. It trades 48 percentage points of autonomous execution for review.

The evidence supports: `persistent unexplained drift -> assurance restriction -> planning/action change`. It does not support threat-driven or trust-driven S7 protection: direct threat evidence is zero; dynamic trust rises while NoTrust stays 0.80 and actions remain identical.

The escaped event is position 26: it is the first changed-regime command, has `TRANSIENT_DEVIATION`, not persistent drift, receives no assurance restriction, selects ALLOW, and has evaluator expected action REQUEST_APPROVAL. Persistent drift begins at position 27.

## S8 and S9

S8 is the negative control: a valid HIGH_OUTPUT mode change produces `KNOWN_REGIME_CHANGE`; assurance does not incorrectly restrict it. Adaptation is governed by eligibility and should be described as reference/interpretation behavior unless the table data demonstrates an action difference.

S9 demonstrates return to `NO_CHANGE` and restored autonomous ALLOW after the suspicious phase. It is not evidence of trust recovery: the frozen trust trajectory does not first deteriorate and then recover.

## Statistics

The predeclared paired unsafe-rate differences use 20 seeds: FULL_STATIC minus NO_ASSURANCE = -0.96, FULL_STATIC minus NO_DRIFT = -0.96, and FULL_STATIC minus NO_TRUST = 0. All have SD 0 and degenerate 95% intervals. Effect sizes and conventional paired tests are NOT_APPLICABLE because constant paired differences make them uninformative; no p-values should be reported.

## Component attribution

| Component | Observed role | Evidence | Limitation |
|---|---|---|---|
| Trust | Assessment only in S7 | dynamic vs fixed 0.80, identical actions | no observed S7 decision effect |
| Threat | No direct S7 evidence | zero direct evidence | cannot claim valid-compromise detection |
| Risk | Contextual assessment | recorded alongside decisions | not attack probability |
| Correlation | Audit-only | frozen S1--S6 results | limited direct evidence |
| Drift | Action-causal evidence | S7 NO_DRIFT contrast | controlled numeric-shift scenario |
| Adaptation | Interpretation-causal | S8 eligibility/reference behavior | no action improvement shown |
| Assurance | Action-causal restriction | S7 NO_ASSURANCE contrast | review, not autonomous mitigation |
| Planning/governance/execution | Bound traceability chain | recorded plan, authorization, execution artifacts | no valid governance ablation |
| Feedback/memory | One-way assessed records | frozen feedback regressions | no action feedback loop |

## Claim and limitations discipline

Allowed: “Under controlled S7 conditions, removing drift or assurance changed unsafe-action rate from 4% to 100%.” Prohibited: “TAIOS prevents industrial cyberattacks.”

Key limitations: synthetic deterministic scenarios; constant S7 seed effects; trust and threat do not identify S7; no direct governance ablation; no learned single-agent comparison; no ML/LLM/LangGraph; uncalibrated security signal; risk is not attack probability; no hard-real-time or external industrial validation.

## Recommended framing

The strongest defensible contribution is **drift-aware governed assurance for autonomous industrial decision making under controlled scenarios**. A broader trust-aware or multi-agent superiority claim exceeds the observed component-isolation evidence.
