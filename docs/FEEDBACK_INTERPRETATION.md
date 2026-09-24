# Milestone 7B: Observable Feedback Interpretation

## Objective and boundary

Milestone 7B interprets each completed immutable experience using only its bound execution and observed-outcome artifacts:

`ExperienceRecord → FeedbackInterpreter → FeedbackAssessment → FeedbackMemory`

Feedback describes what runtime facts can be established. It does not prescribe a change and does not feed any current inference or action component.

Technical execution success is not security correctness. Observing that an authorized speed was applied proves a software-state transition occurred; it does not prove that `ALLOW` was the correct security decision.

## Feedback contract

`FeedbackAssessment` is immutable and binds the experience, event, execution, and outcome references plus source, target, and operation. It exposes:

- Overall feedback status
- Technical execution feedback
- State-effect feedback
- Security feedback
- Operational feedback
- Explicit factual evidence items
- Available dimensions and feedback coverage
- Unresolved feedback requirements
- Stable feedback version and deterministic configuration fingerprint

The version is `milestone7b-feedback-v1`. No tunable numeric weights or fabricated configuration file were introduced.

Statuses are `OBSERVABLE_FEEDBACK`, `PARTIAL_FEEDBACK`, `INSUFFICIENT_FEEDBACK`, and `PENDING_EXTERNAL_FEEDBACK`. Current frozen episodes produce observable or pending feedback only.

## Dimensions and evidence

Four dimensions are evaluated independently:

1. **Execution:** technical success, successful no-op, pending external approval, prevented execution, or partial result.
2. **State effect:** expected mutation, expected no-op, absent effect, partial effect, or pending effect.
3. **Security:** always `UNAVAILABLE` under the current runtime because no evaluator or external security confirmation is permitted.
4. **Operational:** requested state observed, authorized no-op observed, pending effect, or unavailable effect.

Evidence categories are:

- `AUTHORIZED_PAYLOAD_APPLIED`
- `EXPECTED_STATE_VALUE_OBSERVED`
- `REQUESTED_OPERATIONAL_STATE_OBSERVED`
- `NOOP_STATE_CONFIRMED`
- `AUTHORIZED_NOOP_OBSERVED`
- `EXTERNAL_APPROVAL_PENDING`
- `EXECUTION_PREVENTED_OR_PARTIAL` for supported non-success cases

There are no `GOOD_ACTION`, `BAD_ACTION`, `ATTACK_BLOCKED`, reward, utility, or policy-quality fields.

## Coverage

Feedback coverage is the fraction of four dimensions backed by observable facts. It is not confidence.

- Successful mutation or no-op: execution, state effect, and operational dimensions are available, so coverage is 0.75. Security remains unavailable.
- Pending approval: only the technical fact that execution is pending is available, so coverage is 0.25.

## Pending approval and successful no-op

`PENDING_EXTERNAL_FEEDBACK` records `EXTERNAL_APPROVAL_PENDING`. Human approval, subsequent execution, subsequent state effect, and security correctness remain unresolved. The interpreter does not infer that requesting review was correct.

A successful repeated-value execution produces `SUCCESSFUL_NOOP_CONFIRMED`, `EXPECTED_NOOP_OBSERVED`, and `AUTHORIZED_NOOP_OBSERVED`. Equal state versions and the resulting target value provide valid operational feedback without implying adaptive or security success.

## Feedback memory and idempotency

`FeedbackMemory` is separate from `EpisodicMemory`. It supports append, retrieval by experience, event, source, and target, recent causal feedback, count, reset, transactional checkpoint/restore, and an ordered deterministic fingerprint.

The same canonical experience, outcome, execution, version, and interpretation policy produce the same feedback reference. Appending the same canonical feedback twice does not create a duplicate. Memory resets between episodes.

## Pipeline integration and rollback

Feedback interpretation occurs immediately after experience commit and before the completed `PipelineResult` is exposed. Pipeline and episode results carry feedback references, feedback count, and feedback-memory fingerprint without embedding mutable memory.

If interpretation or feedback commit fails, the pipeline restores experience memory, feedback memory, trust, threat history, correlation history, execution ledger, and entity counters. Exact event replay retains the original canonical feedback reference and does not append another record.

Future-event inference never reads feedback. Interpretation is current-experience-only, so later experiences cannot change an earlier assessment.

## Frozen diagnostic

Across 300 experiences from S1–S6 and five seeds:

- `OBSERVABLE_FEEDBACK`: 93 (31%)
- `PENDING_EXTERNAL_FEEDBACK`: 207 (69%)
- Execution feedback available: 300 (100%)
- State-effect feedback available: 93 (31%)
- Operational feedback available: 93 (31%)
- Genuine security-correctness feedback available: 0 (0%)
- Coverage 0.75: 93 experiences
- Coverage 0.25: 207 experiences
- Fully observed across all four dimensions: 0 experiences
- Partially observed: 300 experiences, including 207 with pending external feedback
- Insufficiently observed: 0 experiences

Evidence totals are 93 authorized payload applications, 88 observed expected state values, 88 requested operational states, five confirmed no-ops, five authorized operational no-ops, and 207 pending external approvals.

The ordered 30-run feedback-memory fingerprint is `4798b33cf2ac2bd11d38c335a80d8750b13294329a613e6e70230e0bb3569c99`.

### Scenario observations

- **S1:** 15 observable and 35 pending feedback assessments. One observable experience is a successful no-op. Security feedback remains unavailable.
- **S2:** 25 observable and 25 pending assessments across five seeds. Seed-42 events 1–5 expose technical execution and state effects at coverage 0.75 without proving the `ALLOW` decisions correct. Events 6–10 remain pending at coverage 0.25 without proving review correct.
- **S3:** All 50 assessments remain pending external feedback.
- **S4:** All 50 assessments remain pending; conflicting evidence and review do not establish correctness.
- **S5:** All 50 assessments expose technical, state, and operational feedback. Four are successful no-ops, including seed-42 event 7 under HIGH_OUTPUT. No adaptation is inferred.
- **S6:** Three assessments expose successful technical/state feedback and 47 remain pending. Correlation uncertainty is never converted into security confirmation.

## Leakage and regression boundary

Feedback interpretation consumes no scenario ID, ground truth, expected safe action, formal correctness, unsafe-action label, false-intervention label, attack phase, causal attack tag, or synthetic score. Audit correlation is excluded by the experience’s inference-only trust and risk references.

The unchanged 6C risk, 6D correlation, and 7A experience diagnostics remain byte-identical. Trust trajectories and action distributions remain unchanged. The formal evaluator retains its previous metrics.

## Limitations and readiness

Feedback covers immediate simulator-visible effects only. It cannot determine long-term process quality, safety, malicious intent, attack prevention, compromise, or decision correctness. Pending approvals have no external callback. Feedback memory is volatile and episode-scoped.

No adaptation, drift detection, policy update, reward, threshold change, baseline, ablation, ML, LLM, or LangGraph was introduced. The structured feedback layer is ready to support a separately authorized 7C research stage without yet performing adaptation.
