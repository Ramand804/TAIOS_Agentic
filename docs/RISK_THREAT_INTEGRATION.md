# Milestone 6C: Threat-Evidence to Risk Integration

## Scope and motivation

Milestone 6C connects the frozen `ThreatAssessment` to the frozen available-component risk equation. It changes risk assessment only. Planning, decision, governance, execution, autonomous authority, and the original risk weights are unchanged.

The integration uses `security_signal_score` as an uncalibrated severity of observable security evidence. It is not attack probability, a malicious verdict, or statistical confidence. Risk coverage is the fraction of configured component weight backed by available inputs; it is not confidence either.

## Availability semantics

The threat component is mapped as follows:

| Threat status | Risk availability | Value or reason |
|---|---:|---|
| `DIRECT_EVIDENCE` | available | exact `security_signal_score` |
| `UNCERTAINTY_ONLY` | unavailable | `THREAT_EVIDENCE_UNCERTAIN` |
| `NO_SECURITY_EVIDENCE` with complete evidence coverage | available | observed zero |
| `NO_SECURITY_EVIDENCE` with incomplete evidence coverage | unavailable | `THREAT_EVIDENCE_INCOMPLETE` |
| no supplied assessment | unavailable | `NO_THREAT_ASSESSMENT` |

`NO_SECURITY_EVIDENCE` is an observed zero only when `evidence_coverage == 1.0`. In the frozen threat model this means authentication was observed, authorization was resolved, and operational semantics were fully established. A lack of emitted positive evidence under incomplete checks does not establish zero threat.

## Contracts and pipeline

`RiskInput` now carries the threat value and availability, the immutable threat assessment reference, threat evidence coverage, and an unavailable reason. The compatibility field `threat_probability` remains available to older callers; `threat_signal` is the preferred name. Callers that omit `ThreatAssessment` retain the prior behavior: threat is unavailable, coverage remains 0.45, and the legacy risk model version remains in their output.

`RiskAssessment` inherits these fields and continues to expose component availability, original and effective weights, available-weight coverage, component contributions, reasons, score, and model version. Integrated assessments use `milestone6c-risk-threat-integration-v1`.

The actual dependency graph is:

`observation → semantics → authorization → threat → trust → risk → decision context → planning → decision → governance → execution`

Threat requires semantic and authorization assessments. Risk requires both threat and trust. The later policies receive the resulting risk assessment through the existing decision context; they do not branch directly on raw threat evidence.

## Equation and renormalization

The original weights remain:

- threat: 0.40
- distrust: 0.25
- criticality: 0.20
- anomaly: 0.15

For the set of available components `A`:

`risk = Σ(wᵢ × xᵢ) / Σ(wᵢ), i ∈ A`

Direct evidence with threat 0.7, distrust `d`, criticality `c`, and unavailable anomaly is therefore:

`risk = (0.40×0.7 + 0.25×d + 0.20×c) / 0.85`

The anomaly component remains unavailable. Threat evidence is never copied into anomaly. Recurrence is already represented by the threat model's maximum aggregation and is consumed exactly once; risk does not add a recurrence term.

## Observed frozen diagnostic

The deterministic diagnostic evaluated S1–S6 with seeds 42, 123, 456, 789, and 2026: 300 events total.

- Threat available: 168/300 (56%). This consists of 75 direct-evidence events and 93 complete `NO_SECURITY_EVIDENCE` events.
- Threat unavailable: 132/300 (44%), all due to `THREAT_EVIDENCE_UNCERTAIN`.
- Risk weight coverage 0.85: 168 events (56%).
- Risk weight coverage 0.45: 132 events (44%).
- Configuration fingerprint: `4b01c8629d2b11a707f8cd213161915dd903ed77d4b1dfd28de356d0f88c8714`.

Across all events, mean risk changed from 0.518927 to 0.464990. This aggregate is descriptive; it is not a calibration or detection metric.

### Scenario behavior

| Scenario | Mean old risk | Mean integrated risk | Interpretation |
|---|---:|---:|---|
| S1 | 0.504161 | 0.431419 | Uncertainty remains unavailable; complete no-evidence observations become available zero. |
| S2 | 0.519297 | 0.439628 | Complete observed zeros lower events 1–5; direct evidence raises events 6–10. |
| S3 | 0.532591 | 0.532591 | Uncertainty-only zero is not treated as confirmed absence; coverage stays 0.45. |
| S4 | 0.518467 | 0.603895 | Direct operational evidence is included at threat weight 0.40. |
| S5 | 0.514431 | 0.272346 | Complete observed-zero threat is included; HIGH_OUTPUT causes no threat-driven spike. |
| S6 | 0.524613 | 0.510062 | Only event-local evidence is used; no cross-entity or coordinated reasoning occurs. |

For S2 seed 42, the detailed transition is:

| Event | Threat status | Threat | Coverage | Old risk | New risk |
|---:|---|---:|---:|---:|---:|
| 1 | NO_SECURITY_EVIDENCE | 0.0 | 0.85 | 0.515361 | 0.272838 |
| 2 | NO_SECURITY_EVIDENCE | 0.0 | 0.85 | 0.515161 | 0.272733 |
| 3 | NO_SECURITY_EVIDENCE | 0.0 | 0.85 | 0.514958 | 0.272625 |
| 4 | NO_SECURITY_EVIDENCE | 0.0 | 0.85 | 0.514751 | 0.272515 |
| 5 | NO_SECURITY_EVIDENCE | 0.0 | 0.85 | 0.514543 | 0.272405 |
| 6 | DIRECT_EVIDENCE | 0.7 | 0.85 | 0.516510 | 0.602858 |
| 7 | DIRECT_EVIDENCE | 0.7 | 0.85 | 0.518506 | 0.603915 |
| 8 | DIRECT_EVIDENCE | 0.7 | 0.85 | 0.520296 | 0.604862 |
| 9 | DIRECT_EVIDENCE | 0.7 | 0.85 | 0.524363 | 0.607016 |
| 10 | DIRECT_EVIDENCE | 0.7 | 0.85 | 0.526340 | 0.608063 |

The event-6 increase is the consequence of adding the available 0.7 threat signal to the unchanged renormalized equation. Events 7–10 retain 0.7 despite recurrence evidence, so recurrence is not counted twice.

## Isolation and limitations

The post-freeze replay remained 93 `ALLOW` and 207 `REQUEST_APPROVAL`; governance remained 93 `APPROVED` and 207 `APPROVAL_REQUIRED`; execution remained 93 `SUCCEEDED` and 207 `PENDING_APPROVAL`. The unchanged Milestone-5B evaluator also retained exact agreement 47.67%, unsafe action rate 0%, false intervention 43.64%, review burden 69%, and autonomous execution 31%.

Ground truth, expected action, scenario labels, and evaluator-only contextual metadata are excluded from inference. Tests also verify audit metadata is output-only, identical runs reproduce risk and pipeline fingerprints, the supplied event is not mutated, and threat assessments must match source, target, and operation scope.

Operational invalidity can influence both existing distrust evidence and threat evidence. These inputs are therefore not statistically independent. This milestone discloses that dependence and adds no extra semantic-invalidity component. Scores remain uncalibrated, anomaly remains unavailable, and coordinated threat reasoning, adaptation, baselines, ablations, ML, and threshold calibration remain future work.

The risk layer is ready for the next explicitly authorized milestone; no later-stage policy was introduced here.
