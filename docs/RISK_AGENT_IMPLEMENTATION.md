# Day 3D — RiskAgent orchestration boundary

## Responsibility and inspected interfaces

RiskAgent subclasses the existing BaseAgent and delegates safe observation plus TrustAssessment to build_risk_input, then delegates that RiskInput to RiskModel.evaluate. It returns the existing immutable RiskAssessment. No mathematical formula, detector, decision or independent risk history is added.

Inspected RISK_MODEL_SPEC.md, RISK_INPUT_IMPLEMENTATION.md, RISK_MODEL_IMPLEMENTATION.md; BaseAgent, TrustAgent, TrustAssessment, RiskInput/RiskConfig, RiskAssessment, builder, RiskModel, canonical risk.yaml and existing risk test conventions. Added agents/risk_agent.py, tests/test_risk_agent.py and this document. No existing file or contract changed.

## API

```python
agent = RiskAgent()  # or RiskAgent(config=validated_risk_config)
assessment = agent.assess(
    safe_observation,
    trust_assessment,
    expected_trust_state_version=None,
    correlation_metadata=None,
)
```

The two optional arguments are keyword-only. `correlation_metadata` uses the existing immutable AuditCorrelation(event_id, sequence_number), matching TrustAgent naming. There is no delivery_token parameter: TrustAssessment does not expose the input delivery token, so a new unchecked token would not establish pairing.

## Consistency and freshness

The agent requires the exact public TrustAssessment type. Source/entity consistency, target criticality/asset integrity, safe projection schema and context validation remain delegated to the existing builder. Errors propagate without dropped inputs or silent recovery.

An optional expected_trust_state_version must be a nonnegative integer (not boolean) and must equal the supplied assessment's version. The caller supplies this expectation from its current transaction. A mismatched version raises a deterministic ValueError before inference.

Optional correlation_metadata must be AuditCorrelation. If TrustAssessment also contains audit metadata, the two complete records must match exactly. Their strings and sequence values are compared only as correlation data; no event ID is parsed and no scenario, phase or experimental label is consulted. A mismatch raises ValueError before inference. Consistent changes to both audit records do not change numeric components, coverage, reasons or other inference output.

If the trust record lacks audit, caller-supplied correlation is only output attachment, not a verified pairing. If no correlation is explicitly supplied to RiskAgent, its output audit remains None even when upstream trust has audit. This keeps audit attachment explicit.

**Limitation:** the safe observation contains no audit identifier, delivery token or observation fingerprint. TrustAssessment has a version and optional caller-attached audit, but no content binding. Matching records/version are caller assertions, not cryptographic proof or an independent determination of currentness. Same-source stale trust without an accurate expected version/correlation cannot be detected. A dedicated test records this limitation. No timestamp freshness, hidden metadata heuristic or contract extension was invented. Stronger content-bound pairing would require a separately authorized contract change.

## Statefulness and duplicate delivery

The agent retains only immutable configuration and a stateless RiskModel instance. No per-entity counters, delivery ledger, risk trajectory or reset mechanism is needed. Duplicate submission safely recomputes the same assessment; it does not update trust or risk history. Tests compare serialized semantic outputs on repeats and on fresh agent instances. A rejected call cannot advance state or poison subsequent valid calls.

## Configuration and output

The validated RiskConfig is loaded once at agent construction, or supplied explicitly. It is passed to the builder and carried inside RiskInput into RiskModel. RiskModel has no second configuration. Thus builder-config/model-config mismatch is structurally unavailable through this API; an extra model_config argument is rejected. Tests verify custom-config equivalence to the direct pipeline, fingerprint preservation and invalid configuration rejection.

The output preserves source/target/operation, trust and distrust, target criticality, nullable signals, component availability, coverage, original/effective weights, contributions, reasons, trust version and configuration identity. RiskModel version remains day3c-model-v1; input configuration version remains day3b-input-v1. No versions are rewritten and no event identity changes.

Audit is attached with dataclasses.replace only after inference. It is immutable and exported as an independent copy. The existing to_inference_dict() excludes audit. No second output contract is introduced.

## Missing signals, coverage and reasons

Current threat_probability and anomaly_score remain null, with both availability flags false. Correlated operational anomaly exclusion is preserved from the builder. The agent does not inspect requested values to reconstruct anomaly or inspect trust evidence to derive new scores.

Weighted coverage remains .45 from original distrust .25 plus criticality .20. Effective weights and contributions are exactly those calculated by RiskModel. This coverage is incomplete evidence availability, not a confidence probability. S3 retains insufficient BEHAVIOR/CONTEXT coverage and the builder reason that behavioral evidence is insufficient; no credential-compromise conclusion is introduced.

Reasons are unchanged from the direct builder/model pipeline. The agent adds no classifications, threshold interpretations, action suggestions or assertions of attack detection. Existing .20/.40/.55/.70/.85 thresholds remain unused, unchanged and UNCALIBRATED.

## Leakage boundary

Raw events, event dictionaries and additional evaluation fields fail builder validation. Only the existing safe projection enters input preparation. Optional correlation checks happen outside inference. The model receives RiskInput without audit. Tests mutate ground_truth, expected_safe_action, scenario ID, provenance phase/transition/causal tags and synthetic anomaly/threat/prior-trust/compromise fields, then recompute through the agents. Semantic risk assessments remain identical. Separate tests alter matching audit identifiers and confirm the same inference outputs and reasons.

## Actual seed-42 diagnostics

Ten events per observable-state scenario. All ten selected agent outputs were compared against saved results/day3c-risk.json and matched exactly, not merely after rounding. Repeated serialization was identical. Outputs are saved in ignored results/day3d-risk-agent.json. Diagnostic scenario/event labels are external annotations.

Every row has coverage .45, target criticality as shown, threat=null/false and anomaly=null/false. Values below are rounded to nine decimal places.

| Scenario/event | Source | Target | Trust | Distrust | Criticality | Risk |
|---|---|---|---:|---:|---:|---:|
| S1/6 | SERVICE-03 | PUMP-01 | 0.800950781 | 0.199049219 | 0.86 | 0.492805122 |
| S2/4 | PLC-07 | MOTOR-02 | 0.801447461 | 0.198552539 | 0.91 | 0.514751411 |
| S2/5 | PLC-07 | MOTOR-02 | 0.801823096 | 0.198176904 | 0.91 | 0.514542725 |
| S2/6 | PLC-07 | MOTOR-02 | 0.798281429 | 0.201718571 | 0.91 | 0.516510317 |
| S2/7 | PLC-07 | MOTOR-02 | 0.794688645 | 0.205311355 | 0.91 | 0.518506308 |
| S2/8 | PLC-07 | MOTOR-02 | 0.791468016 | 0.208531984 | 0.91 | 0.520295547 |
| S3/6 | HMI-02 | PLC-03 | 0.801451697 | 0.198548303 | 0.95 | 0.532526835 |
| S5/5 | PLC-01 | MOTOR-02 | 0.801823096 | 0.198176904 | 0.91 | 0.514542725 |
| S5/6 | PLC-01 | MOTOR-02 | 0.802201697 | 0.197798303 | 0.91 | 0.514332391 |
| S5/7 | PLC-01 | MOTOR-02 | 0.802582523 | 0.197417477 | 0.91 | 0.514120821 |

S1 event 6 has a nonzero target-consequence baseline. S2 events 5→6→7→8 preserve declining trust, rising distrust and increasing risk at fixed .91 criticality, without independent threat/anomaly. This is not attack-detection validation. S3 retains incomplete semantics despite a numerically larger .532526835 score and .95 criticality; no credential compromise was detected. S5 events 5→6→7 decline slightly as trust increases, with no stale NORMAL-mode anomaly added.

## Verification, limitations and scope

Complete suite: **400 passed, 0 failed**, including all existing 378 tests and 22 new parameterized cases. Tests cover exact direct-pipeline equivalence, replay, immutable inputs/outputs, audit isolation/copy safety, correlation mismatch, expected-version mismatch, the unverified same-source freshness limitation, source/target validation delegation, single configuration path, preserved missing signals, leakage invariance and scenario diagnostics. Syntax checks passed for both new Python files; whitespace checks cover git diff and all three added files.

No existing bugs were fixed and no existing contract changed. The agent adds explicit rejection of verifiable pairing inconsistencies. Limitations inherited from earlier stages remain: incomplete threat/anomaly and S3 semantics, required trust/criticality inputs, uncalibrated scores, caller-owned observation binding, future full run configuration identity, and no predictive validation. Correlation records are trusted caller metadata; validation is not a security boundary against arbitrary malicious Python callers.

TrustModel and RiskModel mathematics, TrustAgent behavior, scenarios, weights and thresholds are unchanged. No other agents, detectors, adaptation, authorization, action selection, LLM or LangGraph were implemented. No hook was added to main.py or Orchestrator. Stop after Day 3D.
