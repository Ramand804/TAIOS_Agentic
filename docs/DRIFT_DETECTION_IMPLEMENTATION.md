# Milestone 7C: Observable Regime and Drift Detection

## Objective and scientific boundary

Milestone 7C detects whether comparable observable runtime behavior changed and whether explicit operational context explains that change. It does not infer malicious intent, classify attacks, update a baseline online, or adapt any policy or model.

Drift is not attack. A persistent unexplained value shift can arise from many causes. A known operating-mode transition can explain a legitimate distribution shift without requiring adaptation.

## Selected features and scope

The detector uses only:

- Numeric `requested_value` for semantically supported `set_speed`
- Source, target, and operation for comparison scope
- Observable operating mode and production state
- Operational semantic status and current-mode constraints

It excludes risk, trust, threat score, correlation, feedback, decisions, scenario ID, labels, and provenance. Downstream scores would create undesirable coupling and are unnecessary for the operational change question.

Comparable history is scoped as `source_id + target_id + operation`. Different sources, targets, and operations never share a numeric reference.

`write_register` is not numerically compared because the runtime observation lacks register identity and value semantics. Large numeric values without comparable semantics are insufficient evidence of drift.

## Configuration and method

`config/drift_detection.yaml` declares:

- Minimum prior comparable history: 3 observations
- Fixed reference window: first 3 comparable observations in the episode scope
- Recent window: current observation
- Persistence requirement: 2 consecutive changes
- Normalized change threshold: 0.30
- Scope: source, target, operation

The settings are provisional and uncalibrated. They were selected as a transparent proof-of-concept for ten-event streams, not optimized against labels.

For a comparable current value `x`, reference mean `μ`, and current semantic range width `R`:

`change_score = min(1, |x - μ| / R)`

The score is deterministic normalized change magnitude. It is not probability of drift, regime change, malicious behavior, or attack.

The reference is frozen after establishment. Shifted observations do not move the baseline during this audit-only milestone. A score at or above 0.30 increments persistence. The first qualifying observation is transient; the second establishes persistent unexplained drift. Previous assessments are never reclassified.

## Statuses and evidence

Statuses are:

- `INSUFFICIENT_HISTORY`
- `INSUFFICIENT_SEMANTIC_SCOPE`
- `NO_CHANGE`
- `TRANSIENT_DEVIATION`
- `KNOWN_REGIME_CHANGE`
- `UNEXPLAINED_PERSISTENT_DRIFT`

Evidence categories are:

- `NUMERIC_DISTRIBUTION_SHIFT`
- `OPERATING_MODE_CHANGE`
- `PRODUCTION_STATE_CHANGE`
- `CONTEXT_EXPLAINED_SHIFT`
- `UNEXPLAINED_VALID_SHIFT`
- `UNEXPLAINED_INVALID_SHIFT`

Only categories supported by the current event are emitted. Semantic invalidity can support an unexplained change classification, but never an attack conclusion.

## Known context explanation

An explicit operating- or production-state change is checked before unexplained persistence. When the new value is valid under the newly observable current-mode semantics, the assessment is `KNOWN_REGIME_CHANGE`. Subsequent values that remain shifted relative to the fixed pre-change reference and valid under that same context remain context-explained.

The detector does not infer causal mechanisms beyond the observed context transition and current semantic validity.

## Causal history, reset, and rollback

History contains only prior and current runtime observations for the exact behavioral scope. Future events are unavailable. Prefix tests confirm earlier assessments are identical with or without later events.

History, persistence counters, fixed reference windows, and active context explanations reset between episodes. Pipeline failure restores the drift checkpoint alongside trust, threat, correlation, execution, experience, and feedback state. Retry reproduces the same assessment.

Drift runs immediately after operational semantics and before authorization, threat, trust, risk, and actions. `PipelineResult` exposes it as an audit artifact. It is deliberately excluded from `ExperienceRecord`, preserving frozen 7A experience references and diagnostics.

## Frozen 300-event diagnostic

Across S1–S6 and five seeds:

| Status | Events |
|---|---:|
| `INSUFFICIENT_HISTORY` | 78 |
| `INSUFFICIENT_SEMANTIC_SCOPE` | 117 |
| `NO_CHANGE` | 50 |
| `TRANSIENT_DEVIATION` | 10 |
| `KNOWN_REGIME_CHANGE` | 25 |
| `UNEXPLAINED_PERSISTENT_DRIFT` | 20 |

Six comparable numeric scopes were assessed; nine unsupported or underspecified scopes were identified. Evidence totals were 30 numeric shifts, 20 unexplained invalid shifts, 25 context-explained shifts, and five operating-mode changes.

### Scenario observations

- **S1:** 25 insufficient-history and 25 insufficient-semantic-scope events. No unexplained persistent drift occurred. Random activity is distributed across scopes too sparsely for established histories.
- **S2:** 15 insufficient-history, seven no-change, eight transient, and 20 unexplained persistent events across five seeds. For seed 42, event 6 is transient and event 7 first establishes persistence. Events 7–10 remain unexplained persistent change. This is behavioral drift, not an attack verdict.
- **S3:** All 50 events are `INSUFFICIENT_SEMANTIC_SCOPE`. Missing register identity prevents defensible comparison of 55 and 999.
- **S4:** 15 insufficient-history followed by 35 no-change events. Repeated invalid value 84 is constant; semantic invalidity alone is not drift.
- **S5:** 15 insufficient-history, eight no-change, two transient pre-transition deviations, and 25 known-regime observations. All five seeds recognize NORMAL to HIGH_OUTPUT at event 6, and none produce unexplained persistent drift. Seed-42 events 6–10 remain valid, shifted, and context-explained.
- **S6:** Eight insufficient-history and 42 insufficient-semantic-scope events. Post-transition `write_register` activity is evaluated only locally and is not converted from correlation evidence into drift.

## Feedback, leakage, and regressions

Feedback can be recorded alongside drift but does not drive detection. Missing security feedback is not drift. Drift does not feed feedback interpretation or later inference.

Ground truth, expected action, scenario identity, formal correctness, unsafe-action labels, false-intervention labels, attack phases, causal tags, and synthetic scores are absent. Audit metadata is downstream and cannot affect drift.

The unchanged 6C risk, 6D correlation, 7A experience, and 7B feedback diagnostics remain byte-identical. Trust, threat, actions, and formal metrics remain unchanged. Adding drift to `PipelineResult` legitimately changes the outer pipeline and episode fingerprints, while frozen semantic inference artifacts remain identical.

## Limitations and readiness

Ten-event streams cannot support robust statistical concept-drift estimation. The fixed three-observation baseline is deliberately simple and sensitive to early-sample variation. The threshold is provisional, and no statistical confidence or false-positive rate is claimed. Unsupported operations remain unresolved rather than coerced into numeric comparison.

No adaptation, baseline training, ablation, ML classifier, reward, threshold learning, online learning, LLM, or LangGraph was added. This audit-only detector is ready for a separately authorized 7D stage.
