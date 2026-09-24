# Milestone 8A: Experimental Baseline Framework

## Objective

Milestone 8A provides a controlled, deterministic comparison framework for a minimal rule mechanism, frozen static TAIOS, frozen adaptive TAIOS, and a fixed-trust ablation. It measures behavior without retuning TAIOS or claiming superiority.

## Configurations

- **RULE_BASED (B1):** `milestone8a-rule-baseline-v1`. The decision adapter consumes only authentication, the existing authorization assessment, and operational semantic status. It proposes ALLOW only when authentication is true, authorization is explicit, and semantics are `SUPPORTED_VALID`; otherwise it requests approval. It never consumes scenario identity or evaluator labels.
- **TAIOS_STATIC (B2):** Full frozen TAIOS with behavioral adaptation disabled.
- **TAIOS_ADAPTIVE (B3):** Full frozen TAIOS with governed contextual adaptation enabled. This is the sole difference from B2.
- **TAIOS_NO_TRUST (B4):** Full static TAIOS with numeric trust fixed at the canonical documented known-entity prior of 0.80. Observable evidence coverage is retained because the frozen authority contract requires those factual prerequisites. Trust dimensions and deltas do not vary.

## Shared and differing components

All configurations receive the exact same event objects, event order, seeds, initial industrial state, simulator, evaluator annotations, governance, execution, and formal evaluator. B1 replaces planning and proposal selection with one exact rule-generated candidate so common governance and execution can validate the same bound payload contract. Its rules do not inspect trust or risk. B4 replaces only numeric dynamic trust state. B2/B3 differ only in the adaptation mode.

Each of the 120 configuration/scenario/seed episodes creates a fresh pipeline. Trust, threat, correlation, drift, experience, feedback, behavioral references, execution ledger, and industrial state cannot cross configuration boundaries.

## Experiment matrix and evaluator

The matrix is four configurations × six scenarios × five seeds × ten events: 120 episodes and 1,200 event-level evaluations. Events are not treated as independent replicates. The five seeds are the replication units.

The frozen Day-5B evaluator supplies exact action agreement, unsafe action rate, false intervention rate, proposal review burden, and autonomous execution rate. Every rate includes its numerator and denominator. Per-seed mean, sample standard deviation, and exploratory 95% t interval use the existing evaluator implementation. Paired seed differences use the same scenario streams and seeds; no significance test is performed.

## Observed aggregate comparison

All four configurations produced the same action measurements:

- Exact agreement: 143/300 = 47.67%
- Unsafe actions: 0/135 = 0%
- False interventions: 72/165 = 43.64%
- Review proposals: 207/300 = 69%
- Autonomous executions: 93/300 = 31%

Each produced 93 ALLOW and 207 REQUEST_APPROVAL proposals, 93 APPROVED and 207 APPROVAL_REQUIRED governance outcomes, and 93 SUCCEEDED and 207 PENDING_APPROVAL executions. This equality is an observed architectural result, not evidence of equivalence or superiority.

## Scenario observations

- **S1:** All configurations retain the same mixture of routine execution and review.
- **S2:** Dynamic TAIOS trust rises slightly during events 1–5 and falls to approximately 0.7806 by event 10. NoTrust remains 0.80. Risk trajectories therefore differ, while the action trajectory remains five ALLOW followed by five REQUEST_APPROVAL.
- **S3:** All configurations request review because `write_register` semantics remain underspecified. The rule baseline does not invent register identity.
- **S4:** Repeated invalid behavior remains subject to review; repetition does not create validity.
- **S5:** STATIC reports `KNOWN_REGIME_CHANGE` through events 6–10. ADAPTIVE defers at event 6, applies at event 7, and reports `NO_CHANGE` at events 8–10 using the governed reference. Actions remain ALLOW throughout.
- **S6:** Current local and correlation evidence does not establish coordinated-attack causality. No configuration claims otherwise.

## Determinism, provenance, and leakage

Every episode summary binds configuration, scenario, seed, experiment ID, shared stream fingerprint, pipeline version, initial state, and episode fingerprint. Every event summary binds configuration and pipeline/event references. Configuration definitions have deterministic fingerprints and stable versions.

Inference receives no ground truth, expected safe action, scenario identity as a feature, correctness result, unsafe/false-intervention label, attack provenance, or synthetic attack score. Evaluator annotations are joined only after each configuration completes inference.

## Interpretation limits

Five seeds support only exploratory uncertainty intervals. The simulator annotations are not physical-world outcomes. The rule baseline is intentionally small and was frozen before comparison; it is not an optimized classical controller. The fixed-trust adapter is an ablation rather than a calibrated alternative. Current decision policy does not consume drift adaptation or numeric trust/risk thresholds, explaining why assessment trajectories can change without changing actions.

No significance tests, domain-reviewed cost model, calibration study, sensitivity analysis, ablation beyond NoTrust, learned model, LLM, or LangGraph component was added. The framework is ready for controlled analysis, not a publication-grade superiority claim.
