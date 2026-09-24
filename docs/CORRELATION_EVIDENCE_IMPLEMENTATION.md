# Milestone 6D: Cross-Entity Security Correlation Evidence

## Objective and boundary

Milestone 6D asks whether the current observable security-relevant event and causal prior events involving distinct sources form an auditable relationship. It produces coordination evidence only. It does not classify attacks, change risk, select an action, or implement an S6-specific detector.

`ThreatAssessment` remains local to the current event and source. `CorrelationAssessment` records relationships between that local assessment and prior local assessments from distinct sources. `coordination_signal_score` is an uncalibrated evidence-severity score. It is not probability of coordination, compromise, or attack.

## Observable inputs

The model receives only the allowlisted runtime observation, the current frozen `ThreatAssessment`, and causal model history. Available relationship fields are source, target, identity, source and target types, source zone, protocol, operation, requested value, local threat status and categories, and event order. Semantic and authorization facts enter only through the local threat assessment.

Scenario ID, ground truth, expected safe action, provenance phases and causal labels, simulator-only anomaly or coordination fields, synthetic attack scores, and formal evaluation output are excluded. Network zones are observable, but cross-zone evidence is deferred because the repository has no authoritative policy that makes a zone relationship security-relevant.

## Contracts

`CorrelationEvidence` is immutable and records its category and class, current and related sources and targets, relationship type, supporting prior event references, provisional strength and confidence, observable basis, reason, and model version.

`CorrelationAssessment` is immutable and records the current event reference, scope, evidence, coordination signal, evidence coverage, status, participating entities, supporting references, causal history version, unresolved requirements, reasons, configuration fingerprint, and model version. Both contracts derive deterministic references from canonical content; they use no UUID or wall clock.

Statuses are:

- `DIRECT_EVIDENCE`: at least one direct cross-entity relationship is supported.
- `UNCERTAINTY_ONLY`: a cross-entity relationship exists only among uncertainty-only local assessments; signal remains zero.
- `NO_CORRELATION_EVIDENCE`: no qualifying relationship exists.

## History and causal window

The model keeps a simple ordered in-memory list containing event reference, source, target, identity, local threat status, and local evidence coverage. It examines only the previous five event positions plus the current event. Future events are unavailable. The history resets at every episode and has checkpoint/restore operations used by pipeline rollback.

The five-event window and minimum of two distinct sources are explicit in `config/correlation_evidence.yaml`. They are provisional research settings and were not tuned from scenario labels.

## Evidence categories

Two directly defensible relationship families are implemented:

- `MULTI_SOURCE_SAME_TARGET_SECURITY_ACTIVITY`: the current and prior distinct sources both have direct local evidence against the same canonical target.
- `SHARED_IDENTITY_MULTI_SOURCE_SECURITY_ACTIVITY`: the current and prior distinct sources both have direct local evidence while using the same observable identity.

Matched uncertainty is recorded separately as:

- `MULTI_SOURCE_SAME_TARGET_UNCERTAINTY`
- `SHARED_IDENTITY_MULTI_SOURCE_UNCERTAINTY`

Uncertainty categories have strength zero and cannot produce positive coordination signal. Ordinary shared-target or shared-identity activity without matching security-relevant local assessments creates no evidence. Repeated activity from one source never meets the cross-entity requirement.

Direct evidence strengths are provisional and uncalibrated: 0.70 for same-target activity and 0.65 for shared identity. Aggregation is the maximum effective direct strength. Evidence items remain available individually for audit.

## Pipeline and rollback

The pipeline order is:

`observation → semantics → authorization → local threat → correlation → trust → risk → remaining decision pipeline`

`PipelineResult` records the correlation assessment and binds its current-event reference into the pipeline audit chain. Correlation is not placed in `RiskInput` or decision context. A later pipeline failure restores correlation history alongside threat, trust, and execution state.

## Frozen diagnostic

The diagnostic evaluated S1–S6 with seeds 42, 123, 456, 789, and 2026, for 300 events:

- Direct cross-entity evidence: 0/300 (0%).
- Cross-entity uncertainty: 61/300 (20.33%).
- No correlation evidence: 239/300 (79.67%).
- `MULTI_SOURCE_SAME_TARGET_UNCERTAINTY`: 57 evidence items.
- `SHARED_IDENTITY_MULTI_SOURCE_UNCERTAINTY`: 48 evidence items.

No direct category occurred because the frozen scenarios contain no event where direct local evidence from distinct sources meets either configured relationship within the causal window. This is a data-supported absence, not a configuration change made after evaluation.

### Scenario results

- **S1:** 0 direct, 24 uncertainty-only, 26 no-evidence events across five seeds. Random normal operations sometimes share targets or identities while local semantics remain uncertain. These relationships remain signal-zero uncertainty and are not positive coordination evidence.
- **S2:** 0 direct, 0 uncertainty, 50 no-evidence events. PLC-07 recurrence remains local because only one source participates.
- **S3:** 0 direct, 0 correlation uncertainty, 50 no-evidence events. Repeated semantic/authorization uncertainty belongs to one source and never satisfies entity diversity.
- **S4:** 0 direct, 0 uncertainty, 50 no-evidence events. Direct operational violations repeat from one source only.
- **S5:** 0 direct, 0 uncertainty, 50 no-evidence events. Legitimate HIGH_OUTPUT behavior creates no coordination signal.
- **S6:** 0 direct, 37 uncertainty-only, 13 no-evidence events. Multiple sources share observable relationships, but their local evidence is uncertainty-only; the model therefore makes no coordinated-attack claim.

For S6 seed 42, events 1–3 have no correlation evidence. Event 4 is the first cross-entity relationship: HMI-02 and prior SERVICE-03 use identity `user-17`, producing `SHARED_IDENTITY_MULTI_SOURCE_UNCERTAINTY` with signal zero. Event 5 adds PLC-04 and supports both same-target and shared-identity uncertainty against PLC-03. Events 6–10 continue to provide one or both uncertainty relationships among HMI-02, PLC-04, and SERVICE-03. The complete references and per-event categories are stored in the diagnostic artifact.

## Regression and limitations

Risk weights, inputs, coverage, and assessments are unchanged. The unchanged Milestone-6C diagnostic remains byte-identical. Proposal, governance, and execution distributions remain 93/207, and formal action metrics remain unchanged.

The current scenarios exercise uncertainty relationships but no positive multi-source direct-evidence relationship. The model does not infer topology, temporal causality beyond sequence proximity, identity ownership, cross-zone policy, or coordinated intent. Shared identity can reflect legitimate operation, so it requires matching local evidence and still does not establish an attack. Correlation-to-risk and correlation-to-action integration are explicitly deferred.

The audit-only evidence layer is ready for a separately authorized integration milestone. Adaptation, baselines, ablations, ML training, LLMs, and graph databases were not introduced.
