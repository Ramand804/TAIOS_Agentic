# Milestone 6B — independent threat and anomaly evidence

## Objective and boundary

The threat-evidence layer answers which observable facts make a request
security-relevant or uncertain. It does not decide whether an event is
malicious and does not choose, authorize, govern, or execute an action.

Its pipeline position is:

```text
runtime observation
  -> OperationalSemanticModel
  -> AuthorizationEngine
  -> ThreatEvidenceModel
  -> immutable ThreatAssessment

RiskAgent and the existing decision path continue unchanged.
```

Only the allowlisted runtime observation, current OperationalSemanticAssessment,
current AuthorizationAssessment, and source-local history from earlier events
are consumed. Scenario ID, ground truth, expected action, provenance phase,
transition/causal tags, synthetic scores, and formal evaluation output are
excluded.

## Contracts and categories

`ThreatEvidence` contains evidence type/class, source and target, strength,
confidence, observable basis, optional semantic reference, factual reason, and
model version. Strength describes severity of the established signal;
confidence describes confidence that the observable fact was established.
Neither is probability of attack.

`ThreatAssessment` contains the immutable evidence tuple, uncalibrated
`security_signal_score`, evidence coverage, status, observable reasons,
unresolved requirements, causal source-history version, prior violation count,
model version, and configuration fingerprint.

Implemented direct categories:

* `AUTHENTICATION_FAILURE`
* `AUTHORIZATION_FAILURE`
* `OPERATIONAL_CONSTRAINT_VIOLATION`
* `REPEATED_OPERATIONAL_VIOLATION`

Implemented uncertainty categories:

* `AUTHORIZATION_UNRESOLVED`
* `SEMANTIC_UNDERSPECIFICATION`
* `UNSUPPORTED_SEMANTICS`

Authentication success and AUTHORIZED status do not produce benign evidence.
UNKNOWN authorization is uncertainty. Semantic invalidity produces a factual
constraint violation, never an attack verdict. Underspecified and unsupported
semantics produce score-zero uncertainty evidence.

Zone/protocol inconsistency is not emitted because EventManager rejects
registry-integrity violations before inference. Identity/device inconsistency
has no independent attestation signal beyond existing validation. Novel
operation/source-target evidence and coordinated multi-entity correlation are
deferred because no frozen behavioral relationship registry exists.

## Aggregation and score semantics

Configuration `milestone6b-threat-evidence-v1` is declarative, provisional,
and uncalibrated. Aggregation takes the maximum `strength × confidence` among
direct evidence items. This prevents recurrence from becoming an opaque sum
while retaining all evidence items separately for audit.

Assessment status is `DIRECT_EVIDENCE`, `UNCERTAINTY_ONLY`, or
`NO_SECURITY_EVIDENCE`. `security_signal_score` is not attack probability:
zero does not prove benign and one does not prove malicious.

Evidence coverage reports how many of authentication, authorization, and
operational semantics are established. It is evidence availability rather
than classifier confidence.

## Causal history

ThreatEvidenceModel maintains deterministic source-local counts within an
episode. A current known constraint violation is emitted directly. If the same
source already produced one or more observable violations earlier in the
episode, recurrence evidence records the prior count. Current evidence is
constructed before history is updated.

Pipeline reset clears all threat history. Prefix tests confirm that assessment
for event `n` is identical whether later events are present or removed.
Pipeline failure restores the threat-history checkpoint with the existing
trust and execution transaction state.

## Observed coverage

Across S1–S6, five seeds, and 300 events:

| Assessment | Events | Rate |
|---|---:|---:|
| DIRECT_EVIDENCE | 75 | 25% |
| UNCERTAINTY_ONLY | 132 | 44% |
| NO_SECURITY_EVIDENCE | 93 | 31% |

Evidence category counts are 75 operational violations, 65 repeated
violations, 119 unresolved authorizations, 85 semantic underspecifications,
and 32 unsupported-semantic items. The generated scenarios contain no
authentication failure or explicit authorization denial, while deterministic
tests cover both categories.

The security-signal distribution is 225 events at 0 and 75 events at 0.7.
These are evidence-strength outcomes, not attack classifications or accuracy.

## Scenario behavior

**S1:** No event emits direct security evidence. Depending on the randomly
selected source/target, events either have no evidence or score-zero uncertainty
from unresolved authorization or missing target-specific operational limits.

**S2:** Events 1–5 emit no security evidence. Event 6 emits one current
operational-constraint violation at score 0.7. Events 7–10 emit the current
violation plus recurrence evidence with prior counts 1–4. No transition label,
event number, expected action, or ground truth participates.

**S3:** Every write-register request remains uncertainty-only at score zero.
The evidence separately records unresolved authorization and missing
register-level semantics. No value, including 999, is called malicious.

**S4:** Current NORMAL `set_speed=84` requests produce constraint-violation
evidence; later requests also record recurrence. The trace separately retains
trust, authorization, semantic status, and uncertainty rather than replacing
them with a binary verdict.

**S5:** All NORMAL and HIGH_OUTPUT requests emit no direct evidence. The model
uses the current HIGH_OUTPUT semantic assessment and never compares those
values against stale NORMAL limits.

**S6:** Events contain only local per-request evidence or uncertainty.
Cross-source correlation and coordinated-attack detection are not implemented
or claimed.

## Structural isolation and post-freeze evaluation

Before and after Milestone 6B, pipeline structure remains 93 ALLOW and 207
REQUEST_APPROVAL proposals; 93 APPROVED and 207 APPROVAL_REQUIRED governance
outcomes; and 93 SUCCEEDED and 207 PENDING_APPROVAL execution outcomes.

The unchanged formal evaluator was run after the evidence layer was frozen.
Exact agreement remained 47.6667%, unsafe-action rate 0%, false-intervention
rate 43.6364%, review burden 69%, and autonomous execution 31%. No evaluation
label was used to design or alter inference.

## Leakage, determinism, and limitations

Tests alter ground truth, expected action, scenario ID, provenance, transition
and causal metadata, synthetic scores, formal-evaluation-like values, event ID,
and sequence. With equal observables and causal history, complete assessments
remain identical. Input events, observations, semantic assessments,
authorization assessments, trust, risk, state, and DecisionContext remain
unchanged.

Strengths are provisional and uncalibrated. There is no independent network
telemetry, device attestation, register schema, operation-relationship model,
cross-entity correlation, learned anomaly model, outcome feedback, or temporal
decay. Max aggregation preserves auditability but does not estimate likelihood.

The assessment interface is ready for a separately specified risk-integration
milestone. That milestone must define how evidence availability and strength
enter risk without retroactively tuning these evidence rules from labels. ML is
deferred until the evidence contract, training target, data split, calibration,
and leakage controls are specified.
