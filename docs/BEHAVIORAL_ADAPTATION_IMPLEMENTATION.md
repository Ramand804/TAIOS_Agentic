# Milestone 7D: Governed Behavioral Baseline Adaptation

## Objective and boundary

Milestone 7D asks whether TAIOS can establish a contextual behavioral reference after observable evidence supports a legitimate operating regime, while refusing to normalize unexplained or invalid behavior. Only the drift detector's comparison reference may adapt. Operational safety limits, semantic validity, trust, threat, correlation, risk, authorization, authority, planning, decision, governance, and execution remain frozen.

The behavioral reference describes observed behavior. `OperationalLimits` remains the authoritative safety envelope. A HIGH_OUTPUT reference centered near 85 does not change the permitted HIGH_OUTPUT range of 60–95.

## Prior 7C reference state

The frozen 7C detector stores the first three comparable observations for each `source + target + operation` scope in `_baselines`. That reference is episode-local and fixed. `_regimes` records an explicitly observed context transition so later valid shifted values remain context-explained. Persistence counters and causal history are separate state.

7D does not mutate these structures in STATIC mode. ADAPTIVE mode consults a separate governed contextual reference bank before falling back to the frozen 7C reference.

## Immutable contracts

`BehavioralReferenceSnapshot` records scope, sample count, count/mean/minimum/maximum summary, operating context, deterministic version, supporting event/feedback provenance, and model version.

`AdaptationProposal` records its trigger drift reference, event, behavioral scope and context, eligibility status, current reference, candidate summary, observable support, semantic and feedback support, unresolved requirements, policy version, and configuration fingerprint.

`AdaptationDecision` records the proposal reference, explicit status, reasons, whether an update was authorized, before/after references, policy version, and configuration fingerprint.

## Contextual reference bank

`BehavioralReferenceStore` is an episode-scoped deterministic in-memory bank keyed by:

`source + target + operation + operating mode + production state`

NORMAL and HIGH_OUTPUT references therefore remain separate. Snapshots are immutable. The first approved snapshot for a context has version 1. This milestone establishes one governed snapshot per context and does not continuously move it in response to later observations.

## Modes

STATIC is the default. It never applies behavioral-reference updates, and its drift statuses, scores, and evidence remain identical to frozen 7C behavior.

ADAPTIVE permits the governed gate to establish a contextual reference. Future drift assessments in the same context use that approved reference. This is the only inference effect of adaptation.

## Eligibility and gate

The provisional, uncalibrated gate requires all of the following:

- `KNOWN_REGIME_CHANGE`
- `SUPPORTED_VALID` operational semantics
- explicit operating mode and production state
- exact comparable source/target/operation scope
- two causally observed valid events in the new regime
- `OBSERVABLE_FEEDBACK`
- execution, state-effect, and operational feedback dimensions
- no already-established governed reference for that context

The value two is a transparent engineering minimum for a ten-event proof-of-concept stream. It was not tuned against evaluator labels.

The first supported event is `DEFERRED`. The second creates an `ELIGIBLE` proposal and an `APPLIED` decision. `PENDING_EXTERNAL_FEEDBACK` never counts as positive support and causes deferral.

Security-correctness feedback is currently unavailable. It is therefore not required, and applied references are explicitly not claimed to be security-validated.

## Poisoning resistance

`TRANSIENT_DEVIATION`, `INSUFFICIENT_HISTORY`, `INSUFFICIENT_SEMANTIC_SCOPE`, and `NO_CHANGE` are not eligible. `UNEXPLAINED_PERSISTENT_DRIFT` produces a `REJECTED` decision. Repetition alone cannot redefine normal behavior.

This prevents S2's invalid high-speed requests and S4's repeated invalid behavior from entering the reference bank. S3 remains underspecified because register identity is unavailable. S6 correlation evidence is not an adaptation authorization signal.

The descriptive unexplained-drift adaptation rejection rate is rejected-or-deferred attempts divided by unexplained-drift attempts. It is not an adversarial robustness probability.

## Causal ordering and provenance

For event n, the pipeline computes semantics and drift, completes the unchanged inference/action path, observes the outcome, commits the immutable experience, interprets current feedback, and then evaluates adaptation. Only current and prior observations, feedback, and references are available.

Each snapshot carries paired event and feedback references for every supporting observation. Identical event content can occur at distinct event positions, so support identity uses the causal drift-assessment reference rather than deduplicating equal event-content hashes.

Future observations cannot alter earlier proposals or decisions. Prefix runs reproduce the same decisions. The baseline store, accumulated support, and adaptation history participate in pipeline checkpoint/rollback. Episode reset clears them.

## Scenario behavior

- **S1:** Normal behavior creates no adaptation.
- **S2:** Transient and unexplained persistent invalid shifts create no baseline. Persistent attempts are rejected.
- **S3:** Incomparable `write_register` activity creates no adaptation.
- **S4:** Repeated invalid behavior creates no adaptation.
- **S5:** NORMAL to HIGH_OUTPUT is explicitly observed. Event 6 supplies the first supported observation and is deferred. Event 7 supplies the second and applies a HIGH_OUTPUT version-1 reference. Events 8–10 use it. Adaptation latency is one event position.
- **S6:** References remain entity-local; correlation does not authorize adaptation.

## Isolation, leakage, and limitations

Adaptation consumes no scenario identifier, ground truth, expected action, formal correctness, unsafe-action label, false-intervention label, attack phase, causal attack tag, or synthetic attack score. It does not rewrite experiences or feedback.

Ten-event episodes and two observations cannot establish robust statistical stationarity or security correctness. The count/mean/minimum/maximum summary and gate are deliberately simple. Cross-episode continual learning, security-policy adaptation, threshold learning, model training, ablations, ML classifiers, LLMs, and LangGraph remain outside this milestone.

The implementation is ready for controlled STATIC-versus-ADAPTIVE experiments, not deployment or autonomous security-policy learning.
