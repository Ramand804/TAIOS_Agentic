# Day 4C.6 — authorization integration and planner replay

## Objective and architecture

This milestone connects the existing authorization subsystem to the decision substrate without changing permission rules or planning policy:

`safe observation → AuthorizationEngine → AuthorizationAssessment → build_decision_context → DecisionContext → PlanningAgent`

AuthorizationEngine remains the sole permission evaluator. The context builder only validates and assembles the supplied result. PlanningAgent reads `DecisionContext.authorization_status`; it does not import or invoke the engine. Trust and risk remain independent upstream assessments.

Files inspected before implementation: the four Day-4 decision and authorization documents; `core/authorization.py`, `intelligence/authorization_engine.py`, `config/permissions.yaml`, `core/decision_context.py`, `intelligence/decision_context_builder.py`, `agents/planning_agent.py`, `core/planning_result.py`; and their relevant tests.

## API and contract changes

The canonical builder API is now:

```python
build_decision_context(
    safe_observation,
    trust_assessment,
    risk_assessment,
    authorization_assessment=None,
    *,
    permission_policy=None,
    ...,
)
```

The positional optional assessment is an explicit upstream dependency. The builder never calls AuthorizationEngine. Supplying `permission_policy` without an assessment is rejected.

DecisionContext version is `day4c6-context-v1`. It stores the immutable `AuthorizationAssessment` and the exact immutable `PermissionPolicy` used to validate it. It exposes `authorization_status` and `authorization_policy_version`; serialization also records `authorization_basis` as `ASSESSMENT` or `LEGACY_UNKNOWN`. Assessment status, matched rules, reasons, request reference, policy version and policy fingerprint are retained through the structured object.

The context validates identity, source, target and operation against the current safe observation. It recomputes the permission-scope request reference from authentication, source metadata and authoritative registry facts. It verifies authorization policy version/fingerprint and that all reported matched rule IDs exist in the supplied policy. Stale registry bindings, mismatched authentication, substituted scopes and policy/configuration mismatches are rejected.

The assessment intentionally does not bind requested value or operating mode because permission is value/mode independent in the current policy. The complete safe observation, including value and mode, is independently included in the DecisionContext fingerprint. Thus a payload or mode change changes context identity even when permission remains stable.

## Fingerprints and compatibility

Same complete inputs produce the same context fingerprint. Adding an assessment, changing its authorization fact, changing permission configuration, or changing the safe observation deterministically changes context identity. No time, randomness, audit identifier or evaluator label participates.

Backward compatibility uses an explicit UNKNOWN fallback. Existing callers may omit AuthorizationAssessment; the resulting context records `authorization_basis=LEGACY_UNKNOWN`, a null authorization policy version and status UNKNOWN. This preserves existing fixtures and does not silently run the engine or grant permission. New canonical pipelines should always supply the explicit assessment and policy. The context-version change makes this schema migration visible even for legacy calls.

## Planner compatibility change

PlanningAgent candidate rules are unchanged. One narrow explanatory correction was necessary: the global unresolved list now says operation permission is absent only when the supplied status is not AUTHORIZED. Previously that sentence was unconditional because authorization could only be UNKNOWN. Candidate eligibility, exclusions, payloads, ordering and planning version remain unchanged.

AUTHORIZATION alone does not satisfy the planner's existing ALLOW/MONITOR prerequisites. Applicable executable policy clearance and an executable permission envelope remain absent. It also does not erase operational violations, create safe transformations, prove denial safety, or enable isolation.

## Seed-42 before/after replay

The baseline uses the new context schema with the legacy UNKNOWN fallback. The enriched path supplies the Day-4C.5 assessment. Both paths use the existing PlanningAgent candidate policy.

| Event | Old → new authorization | Old candidates | New candidates | Operational validity |
|---|---|---|---|---|
| S1/6 | UNKNOWN → UNKNOWN | REQUEST_APPROVAL | REQUEST_APPROVAL | UNKNOWN |
| S2/5 | UNKNOWN → AUTHORIZED | REQUEST_APPROVAL | REQUEST_APPROVAL | WITHIN_LIMIT [20,80] |
| S2/6 | UNKNOWN → AUTHORIZED | LIMIT, REQUEST_APPROVAL | LIMIT, REQUEST_APPROVAL | OUTSIDE_LIMIT [20,80] |
| S2/7 | UNKNOWN → AUTHORIZED | LIMIT, REQUEST_APPROVAL | LIMIT, REQUEST_APPROVAL | OUTSIDE_LIMIT [20,80] |
| S2/8 | UNKNOWN → AUTHORIZED | LIMIT, REQUEST_APPROVAL | LIMIT, REQUEST_APPROVAL | OUTSIDE_LIMIT [20,80] |
| S3/6 | UNKNOWN → UNKNOWN | REQUEST_APPROVAL | REQUEST_APPROVAL | UNKNOWN |
| S5/5 | UNKNOWN → AUTHORIZED | REQUEST_APPROVAL | REQUEST_APPROVAL | WITHIN_LIMIT [20,80] |
| S5/6 | UNKNOWN → AUTHORIZED | REQUEST_APPROVAL | REQUEST_APPROVAL | WITHIN_LIMIT [60,95] |
| S5/7 | UNKNOWN → AUTHORIZED | REQUEST_APPROVAL | REQUEST_APPROVAL | WITHIN_LIMIT [60,95] |

No candidates were added or removed. For authorized requests, permission-related uncertainty disappears from PlanningResult, and evidence now reports AUTHORIZED. Candidate membership remains unchanged because the other permissive prerequisites are still missing. This is an observed result rather than a tuned outcome.

S1 stays conservative because service-to-pump permission and operational limits remain unknown. S3 stays conservative because HMI register permission and register semantics remain unknown. No LIMIT or ISOLATE is fabricated in either case.

## Scientific invariants

For S2 events 5–8, authorization is identically AUTHORIZED while operational validity changes from within range to outside range. Trust changes `0.801823095703 → 0.798281429036 → 0.794688645426 → 0.791468016052`; risk changes `0.514542724609 → 0.516510317202 → 0.518506308096 → 0.520295546638`. Authorization therefore remains independent of compromise behavior, process validity and trust/risk trajectories. Events 6–8 retain actual NORMAL limits [20,80], original requested values, and `replacement_value=null`; ALLOW never appears.

For S5 events 5–7, authorization remains AUTHORIZED while mode changes NORMAL → HIGH_OUTPUT. Current limits change [20,80] → [60,95], all three values remain within range, and membership remains REQUEST_APPROVAL. Permission is not invalidated by regime change, and NORMAL limits are not reused after the change.

## Leakage, audit isolation and reproducibility

Tests mutate ground truth, expected action, scenario ID, provenance phase/transition/causal tags and synthetic scores across S1–S6, then rebuild the complete authorization/context/planning pipeline. AuthorizationAssessment, DecisionContext and PlanningResult remain identical. Enriched raw inputs remain rejected by the safe projection.

Matching changed trust/risk audit identifiers are stripped during context assembly and do not change context serialization, candidate membership, rationale or prerequisites. Mismatched audit pairs remain rejected by the pre-existing builder validation. AuthorizationAssessment has no audit field.

The machine-readable differential is generated by `evaluation/replay_authorization_planning.py` as ignored `results/day4c6-planner-diff.json`. It records both context/planning records, added/removed/unchanged candidates, explanations, operational validity, trust, risk and risk coverage for all nine requested events. Two executions were byte-identical; both files had SHA-256 `a2c54701d83634ef4d49ba093301ca240b39ef96a603ab45cf188523c8d2501c`. Re-running the five-seed authorization diagnostic retained SHA-256 `e6882a55ce1ccd124ed179a6a7bc452b5c54c1c76bc1e68a0e346705b257f4d2`.

## Verification, limitations and next step

496 tests passed, 0 failed: all previous 478 plus 18 integration cases. New coverage includes structured integration, every scope mismatch, request and registry binding, policy version/configuration preservation, authentication semantics, deterministic and changed fingerprints, legacy fallback, engine/planner separation, S2/S5 invariants, six-scenario leakage, audit isolation and deterministic replay.

Authorization remains a simulation permission to request an operation, not an executable grant, governance authorization or safety proof. The current prose policies have no executable applicability predicates. No complete operation execution envelope exists. LIMIT still lacks a reviewed transformation; REQUEST_APPROVAL still lacks a safe hold and external workflow; BLOCK lacks denial-impact review; ISOLATE remains unavailable. The upstream trust/risk contracts still do not fully bind their assessments to observation content.

For Day 4D, retain the observed candidate sets and design a DecisionAgent that consumes the exact bound PlanningResult and DecisionContext, can represent no proposal, and preserves unresolved prerequisites. It must not treat canonical candidate order as preference, manufacture an ALLOW because permission is AUTHORIZED, select an incomplete LIMIT transform, or collapse proposal into governance authorization. Any future change intended to enable ALLOW/MONITOR belongs in separately reviewed executable policy and capability semantics, not DecisionAgent scoring.

No DecisionAgent, GovernanceAgent or ExecutionAgent was implemented. Permission rules, trust/risk mathematics, scenarios and planning candidate policy were unchanged. Stop after Day 4C.6.
