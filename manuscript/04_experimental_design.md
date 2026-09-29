# 4. Experimental Design

## 4.1 Research questions and hypotheses

We evaluate decision effectiveness (RQ1), dynamic-trust contribution (RQ2), governed adaptation (RQ3), governance and traceability (RQ4), and component-level architectural contribution (RQ5). The pre-specified hypotheses are: H1, trust-aware decisions reduce unsafe actions from compromised or unreliable entities; H2, adaptive operation recovers faster after drift than static operation; H3, governance reduces policy-violating autonomous actions; H4, multi-component decomposition improves decision quality under heterogeneous conditions relative to a selected single-agent baseline; and H5, provenance/explanation is available without prohibitive latency. The experimental design does not presuppose support for any hypothesis.

## 4.2 Controlled industrial scenarios

S1--S6 cover normal operation, compromised-device behavior, credential misuse, conflicting evidence, legitimate operating change, and coordinated activity. S7--S9 are later discriminating controls. S7 holds authentication, authorization, semantic support, and operating limits permissive while introducing an unexplained persistent behavioral shift. S8 is a legitimate-regime negative control with observable contextual explanation. S9 returns to baseline after a suspicious valid period to examine whether restrictive behavior ceases when drift is no longer persistent.

The assurance mechanism was frozen before S7--S9 were introduced. Earlier S1--S6 diagnostics produced no assurance-created restrictions because adverse cases were already restricted upstream. S7--S9 were added to distinguish component effects; policies and thresholds were not subsequently tuned.

## 4.3 Configurations and ablations

We compare seven frozen configurations: FULL_STATIC, FULL_ADAPTIVE, NO_ASSURANCE, NO_DRIFT, NO_ADAPT, NO_TRUST, and RULE_BASED (Table 1). FULL_STATIC is the static-reference configuration; FULL_ADAPTIVE enables governed adaptation. NO_ASSURANCE disables only assurance restriction while retaining upstream assessment. NO_DRIFT uses an explicit drift-unavailable adapter, rather than asserting `NO_CHANGE`. NO_ADAPT uses static behavioral references while retaining drift detection. NO_TRUST replaces dynamic trust with fixed neutral trust 0.80 while preserving other contracts. RULE_BASED uses frozen observable-fact rule planning and decision adapters.

NO_GOVERNANCE is excluded. Governance emits the authorization artifact consumed by execution; bypassing it would alter execution-integrity protection rather than cleanly isolate governance reasoning.

## 4.4 Evaluation protocol

The publication matrix uses seeds 42, 123, 456, 789, 2026, and 3001--3015. It contains 7 configurations × 9 scenarios × 20 seeds = 1,260 episodes and 4,200 unique scenario/seed events. Each scenario/seed event stream is generated once and reused unchanged for every configuration, enabling paired comparisons. The seed, rather than the individual event, is the replication unit; events are not treated as independent replicates.

## 4.5 Metrics

Exact agreement is the fraction of evaluated events whose selected action equals evaluator-only expected action. Unsafe-action rate is the number of unsafe autonomous actions divided by events for which autonomous allowance is evaluator-defined unsafe. False-intervention rate is restrictive intervention divided by events whose expected safe action is `ALLOW`. Review burden is the fraction proposed for `REQUEST_APPROVAL`; autonomous-execution rate is the fraction of successful autonomous executions. Undefined denominators are reported as not applicable, never zero. Ground truth, expected action, scenario identifiers, phase annotations, causal annotations, and provenance are evaluator-only metadata.

## 4.6 Aggregation and statistics

Event-weighted summaries pool eligible events: \(\sum_i n_i r_i / \sum_i n_i\). Scenario-balanced summaries assign equal weight to applicable scenario-level rates: \(S^{-1}\sum_s r_s\). Both are reported because S1--S6 have 10 events per stream and S7--S9 have 50.

Predeclared comparisons use paired seed-level differences. We report mean, sample standard deviation, median, minimum, maximum, and a normal-approximation 95% confidence interval. When all paired differences are constant, standardized effect sizes and conventional paired tests are not reported as informative and no p-value is manufactured.

## 4.7 Experimental integrity

Runtime inference receives only an allowlisted observable projection. Dedicated tests mutate labels and evaluator metadata to verify they cannot reach inference. Deterministic configuration, scenario, event-stream, and result fingerprints support replay and frozen regression checks. The frozen release is commit `e1812bbc19ea85874bbb639157540951b0689dbb`, tag `taios-implementation-v1`; publication and validation artifacts are retained by their recorded SHA-256 identifiers.

## 4.8 Reproducibility

Detailed configuration definitions are retained in the publication configuration table and the frozen artifact. The publication artifact records the seed list, stream fingerprints, scenario fingerprints, configuration fingerprints, seed-level metrics, and paired comparisons. The validation artifact and final publication artifact provide compact reproducibility references without requiring inference during analysis.
