# Evidence and claims freeze — TAIOS V1

**Authority:** frozen publication artifact `92c0f6486045e9639cd3c873c1b8853c0024ffbd3f9201e5a76ddb85a8d1dc84`. This is the manuscript claim boundary.

## Central contribution

TAIOS implements a governed multi-component decision architecture in which **observable persistent behavioral drift can become decision-causal through decision assurance**, restricting autonomous execution when controlled S7 commands remain authenticated, authorized and operationally valid. This is controlled synthetic-scenario evidence, not a real-world attack-prevention claim.

## Research questions

| RQ | Answer | Strength | Evidence and limit |
|---|---|---|---|
| RQ1 | Drift-aware assurance changes unsafe autonomous behavior in S7. | STRONG CONTROLLED EVIDENCE | FULL 1/25 unsafe vs NO_ASSURANCE/NO_DRIFT 25/25; controlled scope only. |
| RQ2 | Trust is assessed but has no observed S7 action effect. | NOT DEMONSTRATED | Dynamic endpoint 0.80035→0.819225; NoTrust 0.80; actions identical. |
| RQ3 | Adaptation supports governed interpretation of legitimate regime change. | PARTIALLY SUPPORTED | S5/S8 interpretation/reference evidence; no demonstrated action improvement. |
| RQ4 | Governance provides bound validation, authorization artifacts and traceability. | SUPPORTED | No valid NO_GOVERNANCE causal ablation. |
| RQ5 | Component isolation identifies drift and assurance as action-causal in S7. | SUPPORTED | Does not establish general multi-agent superiority. |

## Hypotheses

| Hypothesis | Status | Reason |
|---|---|---|
| H1 trust-aware decisions reduce unsafe actions | NOT DEMONSTRATED | FULL and NO_TRUST S7 actions match. |
| H2 adaptation recovers faster than static | NOT DEMONSTRATED | Interpretation changes are observed; recovery-speed/action benefit is not established. |
| H3 governance reduces policy-violating actions | NOT DIRECTLY TESTED | NO_GOVERNANCE is methodologically invalid. |
| H4 decomposition improves quality over selected single-agent baseline | NOT DEMONSTRATED | RULE_BASED is not a learned single-agent baseline. |
| H5 provenance/explanation without prohibitive latency | PARTIALLY SUPPORTED | Traceability records exist; no hard latency claim. |

## Locked S7 claims

| Claim ID | Allowed claim | Evidence | Forbidden wording |
|---|---|---|---|
| C1 | In controlled S7, removing drift evidence or assurance increased unsafe-action rate from 1/25 (4%) to 25/25 (100%). | Table 4 / Figure 3 | “TAIOS prevents 96% of cyberattacks.” |
| C2 | The controlled effect accompanies 24/50 review decisions and autonomous execution of 26/50 commands. | Table 4 / Figure 2 | “Review burden is universally beneficial.” |
| C3 | Dynamic trust changed but FULL and NO_TRUST actions were identical in S7. | Figure 4 | “Trust reduced unsafe actions by 96%.” |
| C4 | S8 is a legitimate-regime negative control for governed adaptation interpretation. | Tables 3 and 6 | “Adaptation improves final action accuracy.” |
| C5 | Governance supplies traceable authorization artifacts. | V1 records | “Governance alone reduced unsafe actions.” |

Threat is a security signal/evidence score, never attack probability. Risk is estimated danger under available evidence, never attack probability. Correlation has no demonstrated direct multi-source effect in the evaluated original scenarios.

## Statistics and aggregation

Seed is the replication unit. Events are not independent replicates. S7 paired unsafe-rate differences: FULL−NO_ASSURANCE = −0.96, FULL−NO_DRIFT = −0.96, FULL−NO_TRUST = 0; SD is zero. Standardized effect sizes and paired tests are NOT_APPLICABLE for these constant differences. Report event-weighted and scenario-balanced aggregates separately because scenario lengths differ.

## Contributions

1. A traceable governed architecture binding observable assessments, planning, governance and execution.
2. A controlled mechanism result: persistent unexplained drift becomes action-causal only through assurance restriction.
3. A reproducible frozen experiment package with deterministic streams, seed-level comparisons and policy fingerprints.
4. A negative result: dynamic trust is not action-causal for controlled S7.
5. A scope boundary: adaptation is interpretation-level evidence here, not demonstrated action improvement.

## Abstract-safe quantitative statements

1. In controlled S7, FULL_STATIC had 1/25 unsafe actions (4%) versus 25/25 (100%) after removing assurance.
2. Removing drift produced 25/25 unsafe S7 actions (100%).
3. The FULL S7 result introduced 24/50 review decisions (48%) and retained 26/50 autonomous executions (52%).
4. Dynamic and fixed-neutral trust produced identical S7 final actions despite dynamic trust changing from approximately 0.80035 to 0.819225.

## Conclusion-safe boundaries

Demonstrated: controlled drift/assurance causal evidence and traceable records. Suggested: governed adaptation can distinguish contextual regime changes. Not demonstrated: trust-driven S7 protection, governance-only causal benefit, general multi-agent superiority, real-world protection, or hard real-time viability. External industrial validation is required.

## Title assessment

“Agentic AI” and “Operating System” may create reviewer expectations for LLMs, broad autonomy and OS-like services not evaluated here. “Trust-Aware” is architecturally accurate but should not imply trust-driven S7 protection. “Adaptive” is accurate at interpretation level. “Explainable” is supported as provenance/traceability, not a human-subject explanation study. A safer empirical subtitle is: **“TAIOS: Drift-Aware Governed Assurance for Autonomous Industrial Decision Making.”**

## Limitations

Synthetic deterministic scenarios; constant S7 seed effects; no direct S7 threat evidence; trust not action-causal in S7; no valid governance ablation; no learned single-agent baseline; no ML/LLM/LangGraph; uncalibrated security signals; risk is not attack probability; limited correlation evidence; no real-world or hard-real-time validation.
