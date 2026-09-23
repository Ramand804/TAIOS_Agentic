# Day 4C — deterministic PlanningAgent

## Responsibility, API and scope

`PlanningAgent().plan(decision_context)` returns an immutable PlanningResult containing a canonical tuple of existing CandidateAction objects. The agent subclasses BaseAgent, is stateless, and accepts only the exact DecisionContext type. It never accepts raw events, assessment objects or evaluation dictionaries. No final action is chosen, recommended or scored.

Read AUTONOMOUS_DECISION_SPEC.md and DECISION_CONTEXT_IMPLEMENTATION.md first; inspected Action, DecisionContext/capability/policy contracts, future-stage contracts, context builder and its tests, plus established trust/risk coverage and missing-signal behavior. Added agents/planning_agent.py, core/planning_result.py, tests/test_planning_agent.py and this document. No existing source, contract, configuration or specification changed.

## Candidate policy — PROVISIONAL / UNCALIBRATED

These rules implement the current context's limited semantics. They are not validated industrial operating policy. Frozen invariants still apply: missing permission is not permission, no execution without governance, no hidden-label inference, and no implied isolation authority.

| Action | Current generation rule | Result under current contracts |
|---|---|---|
| ALLOW | Requires a permission envelope and policy clearance in addition to valid operation | Excluded: explicit authorization/envelope are not established |
| MONITOR | Permissive operation requires the same authority; logical monitoring alone is insufficient | Excluded: monitoring cannot substitute for permission or safe operation |
| LIMIT | Logical LIMIT support plus an observed OUTSIDE_LIMIT check with a current range | Conditional range-only review candidate; requires approval and unresolved transformation prerequisites |
| REQUEST_APPROVAL | Logical approval support and unresolved authority/policy/execution prerequisites | Conditional review/deferral candidate, without permitting the original operation |
| BLOCK | Logical denial is insufficient without reviewed denial-impact/safety and policy authority | Excluded: no such envelope exists |
| ISOLATE | Requires established capability and impact/authority semantics | Excluded: capability is UNKNOWN and unsupported |

Unsupported actions are excluded before further rules. Every excluded action has an explicit reason. No prose policy is converted into an executable predicate. No scalar risk/trust threshold controls membership. Current PolicyContext always reports authorization UNKNOWN; the planner does not invent future authorized branches or grant tables. Supporting a future permission envelope will require a separately reviewed policy change.

This deliberately distinguishes technical representation from admissibility for review, and from execution permission. Logical ALLOW/MONITOR/BLOCK support in Day 4B does not automatically produce candidates. Incomplete essential prerequisites exclude permissive and disruptive operations. REQUEST_APPROVAL and LIMIT use the existing unresolved_prerequisites field to represent conditional review, never executable actions.

## LIMIT and approval semantics

The Day-4C request explicitly asks for LIMIT candidates on range violations without choosing a replacement value. This refines the earlier fully specified execution-payload expectation: a Day-4C LIMIT is an incomplete planning alternative, not a ready-to-execute transformation. Its payload has original request/source/target/mode, allowed_min, allowed_max, limit_reference, replacement_value=null and execution_ready=false. Original request values are preserved. A later reviewed safe transformation and exact bounded payload remain unresolved. A range alone does not establish safety, and human approval alone cannot fill missing safety semantics.

LIMIT is not generated for a within-range request merely because the capability exists. It is not fabricated for unknown write_register or PUMP-01 semantics. The planner reads OperationalValidity from DecisionContext and imports no limit engine; it never recalculates ranges or reconstructs NORMAL mode.

REQUEST_APPROVAL represents logical deferral/review. Its payload preserves the request, has purpose=DEFER_FOR_REVIEW and execution_ready=false. requires_approval=true describes the unresolved human/authority prerequisite; it does not assert that an implemented human workflow or physical hold exists. A reviewed hold/disposition envelope and external approval workflow remain explicitly unresolved. No approval request is sent and no operation is executed.

BLOCK is excluded even when a range violation is observed: the current context has no reviewed denial-safety envelope. It is not described as physically safe by default. ISOLATE cannot be enabled by labels, criticality, distrust or risk.

## Evidence, uncertainty and rationale

Every candidate retains deterministic safe facts: authorization, validity, mode, original operation/value, trust score and all direct evidence coverage, risk value and weighted coverage, and current range/deviation when present. These facts are explanatory, not utility scores. Coverage .45 remains weighted risk evidence coverage, not decision confidence. Risk is not attack probability.

Common unresolved constraints record UNKNOWN authorization, absent governance/execution capability, UNKNOWN operation validity where applicable, and each enabled policy's unresolved applicability. LIMIT additionally records safe-transform/exact-payload and scoped approval requirements. REQUEST_APPROVAL records the absent hold/workflow prerequisite. Safety effect, operational impact and reversibility are qualitative and explicitly uncertain. No arbitrary numeric ranking is introduced.

## PlanningResult and ordering

PlanningResult fields: candidates, context_fingerprint, context_version, planning_policy_version, unresolved_constraints and exclusions. A small wrapper is necessary to retain context binding, exclusions and unresolved status even with an empty tuple. Status is CANDIDATES_FOR_REVIEW when nonempty or NO_ADMISSIBLE_CANDIDATES otherwise.

Version is day4c-planning-v1 for the wrapper and every candidate. The context fingerprint is the existing DecisionContext.reference. Each candidate also binds its capability reference. No timestamp, random UUID or audit field affects planning. Serialization uses the existing copy-safe Record conventions.

Candidates use Action declaration order: ALLOW, MONITOR, LIMIT, REQUEST_APPROVAL, BLOCK, ISOLATE. Ordering is for reproducibility only; earlier does not mean safer, better or preferred. At most one candidate per action is permitted, and exclusions must account for every non-candidate action. The result validates canonical order, uniqueness and version agreement. No selected_action, recommended_action, best_action or preferred_action exists.

If no prerequisites support a candidate, return an empty tuple with explicit status, exclusions and unresolved constraints. Never inject ALLOW. Real Day-4B envelopes always include logical approval; the empty-path test uses an isolated capability-property seam to simulate no supported actions without changing frozen contracts.

## Actual seed-42 diagnostics

Ten events per observable-state scenario through the unchanged TrustAgent → RiskAgent → DecisionContext builder pipeline. Nine requested events were planned and repeated; every replay was identical. Full contexts, supported capabilities, candidate payloads/rationales and unresolved prerequisites are saved in ignored results/day4c-planning.json. Scenario/event annotations are evaluation-only and never planner inputs.

All rows: authorization UNKNOWN, risk coverage .45, planning version day4c-planning-v1, isolation UNKNOWN/absent. Supported logical capabilities B are ALLOW, MONITOR, REQUEST_APPROVAL, BLOCK; B+L adds LIMIT range representation. Identity/device direct evidence is POSITIVE; direct HISTORY/CONTEXT evidence is INSUFFICIENT throughout.

| Scenario/event | Source → target | Operation/value | Mode | Validity/range | Trust | Behavior evidence | Risk | Supported | Candidates |
|---|---|---|---|---|---:|---|---:|---|---|
| S1/6 | SERVICE-03 → PUMP-01 | set_speed 63 | NORMAL | UNKNOWN | 0.800950781 | INSUFFICIENT | 0.492805122 | B | REQUEST_APPROVAL |
| S2/5 | PLC-07 → MOTOR-02 | set_speed 48 | NORMAL | WITHIN_LIMIT [20,80] | 0.801823096 | POSITIVE | 0.514542725 | B+L | REQUEST_APPROVAL |
| S2/6 | PLC-07 → MOTOR-02 | set_speed 97 | NORMAL | OUTSIDE_LIMIT [20,80] | 0.798281429 | NEGATIVE | 0.516510317 | B+L | LIMIT, REQUEST_APPROVAL |
| S2/7 | PLC-07 → MOTOR-02 | set_speed 97 | NORMAL | OUTSIDE_LIMIT [20,80] | 0.794688645 | NEGATIVE | 0.518506308 | B+L | LIMIT, REQUEST_APPROVAL |
| S2/8 | PLC-07 → MOTOR-02 | set_speed 94 | NORMAL | OUTSIDE_LIMIT [20,80] | 0.791468016 | NEGATIVE | 0.520295547 | B+L | LIMIT, REQUEST_APPROVAL |
| S3/6 | HMI-02 → PLC-03 | write_register 999 | NORMAL | UNKNOWN | 0.801451697 | INSUFFICIENT | 0.532526835 | B | REQUEST_APPROVAL |
| S5/5 | PLC-01 → MOTOR-02 | set_speed 53 | NORMAL | WITHIN_LIMIT [20,80] | 0.801823096 | POSITIVE | 0.514542725 | B+L | REQUEST_APPROVAL |
| S5/6 | PLC-01 → MOTOR-02 | set_speed 85 | HIGH_OUTPUT | WITHIN_LIMIT [60,95] | 0.802201697 | POSITIVE | 0.514332391 | B+L | REQUEST_APPROVAL |
| S5/7 | PLC-01 → MOTOR-02 | set_speed 85 | HIGH_OUTPUT | WITHIN_LIMIT [60,95] | 0.802582523 | POSITIVE | 0.514120821 | B+L | REQUEST_APPROVAL |

S1/6 and S3/6 both retain unknown operational semantics and authorization; only logical approval review is generated. Authentication and trust near .8 do not grant permission. S2/5 is operationally valid but still not authorized. S2/6–8 have concrete range violations and therefore support conditional LIMIT alongside approval review, without clamping 97/94 or selecting either candidate. S5/6–7 inherit HIGH_OUTPUT [60,95] and remain within range; no LIMIT rationale using stale NORMAL limits appears. Approval remains a candidate due to unresolved authorization, not a claim of regime-change danger.

For every row, unresolved prerequisites include authorization, governance/executor absence and P01/P02/P03 applicability. Every approval candidate additionally requires reviewed hold/disposition and workflow support. Each S2 LIMIT candidate additionally requires safe transformation, exact replacement payload and scoped permission review. No candidate is execution-ready.

## Verification and boundaries

453 tests passed, 0 failed, including all prior 440 tests and 13 new parameterized cases. Tests cover stateless deterministic planning, canonical order, no duplicates/selection fields, immutable copies, context/version binding, real S1/S2/S3/S5 semantic properties, unsupported capability exclusion, empty-set behavior, current-mode range inheritance, missing authority, high/low trust and alternative risk weights without membership changes, null risk, label/audit invariance, raw-input rejection and invalid PlanningResult construction. Syntax and whitespace checks cover all added files.

Hidden mutations of ground_truth, expected_safe_action, scenario ID, provenance phase/transition/causal tags and synthetic scores leave whole PlanningResults identical after rebuilding through the real pipeline. Matching changed audit metadata is stripped by the context builder and cannot change planning membership, rationale, prerequisites or status. The planner itself has no raw event/evaluation input path. Input contexts and trust/risk assessments remain unchanged.

## Limitations and Day-4D requirements

All generation policy is PROVISIONAL / UNCALIBRATED. Conditional candidates are not policy compliance or safety proof. Authorization grants, reviewed denial/hold/transform envelopes, executable monitoring/approval/isolation and complete upstream observation binding remain absent. Deterministic hashes bind artifacts, not the truth of their evidence. No oracle agreement or predictive validation is claimed.

A separately authorized DecisionAgent must consume the exact bound context/candidate set, distinguish conditional review from executable action, retain unresolved prerequisites and alternatives, and propose without execution. It must not treat the first candidate as preferred, silently choose a LIMIT replacement value, promote UNKNOWN authorization to permission, or infer a governance grant from candidate presence. Governance and execution remain mandatory future stages. Enabling permissive or disruptive candidates requires explicit new semantics and tests, not a threshold adjustment.

No action was selected or recommended. Decision/Governance/Execution agents, detectors, adaptation, optimization, calibration and LLM/LangGraph were not implemented. Trust/risk mathematics, scenarios, policies, thresholds and existing contracts remain unchanged. Stop after Day 4C.
