# Day 4C.7 — autonomous authority policy

## Objective and architecture

This milestone answers one question: which action classes may TAIOS autonomously consider under current observable policy facts? It does not select, rank, govern or execute an action.

The implemented flow is:

`safe observation → Trust/Risk/Authorization → DecisionContext → AutonomousAuthorityEngine → AutonomousAuthorityAssessment → enriched DecisionContext → PlanningAgent`

The distinction is strict: authentication establishes credential success; authorization establishes permission to request an operation; autonomous authority establishes which response classes policy permits TAIOS to consider; planning creates eligible alternatives; a future DecisionAgent may propose one; governance must independently authorize it; execution remains absent.

Before implementation, the Day-4A through Day-4C.6 documents, both policy configurations, actions, authorization, context, decision contracts, planning result, builder, planner, capabilities and unresolved policy facts were inspected. Trust/risk models, scenarios and permission rules were not changed.

## Contracts and API

`AuthorityStatus` has exactly `PERMITTED`, `NOT_PERMITTED` and `UNKNOWN`. PERMITTED means eligible for planning consideration under this simulation policy. It never means selected, safe, governance-approved or executable.

`AuthorityRule` is immutable and contains: rule ID, canonical action, named condition, PERMITTED/NOT_PERMITTED result, rationale and policy version. `AuthorityPolicy` contains a canonically sorted unique rule tuple and version. The complete deterministic policy reference fingerprints all rules and rationales.

`AutonomousAuthorityAssessment` is immutable and contains source, identity, target, operation, upstream authorization status, operational-validity status, all six per-action statuses, per-action matched policy IDs and reasons, unresolved requirements, authority policy version/fingerprint and a reference to the exact authority input context. It contains no selected, recommended, preferred or ranked action.

API: `AutonomousAuthorityEngine(policy=None).assess(decision_context)`. It requires an exact DecisionContext with an explicit AuthorizationAssessment. It consumes the upstream authorization fact and never imports or runs AuthorizationEngine. It uses existing trust/risk assessments and capability/validity facts without recomputing their models.

DecisionContext version is `day4c7-context-v1`. It stores the authority assessment and exact policy and validates scope, upstream authorization, operational validity, policy version/fingerprint, matched rule IDs and the authority-input context reference. Authority facts therefore participate in the full context fingerprint. The builder accepts explicit `autonomous_authority_assessment` and `authority_policy` keyword arguments; it never invokes the authority engine.

## Policy rules and simulation assumptions

Configuration is `config/autonomous_authority.yaml`, version `day4c7-authority-v1`. Rule conditions use only explicit authorization, current operational validity, direct trust-evidence categories and existing logical capabilities. They never use scenario, sequence, labels, provenance, transitions, causal tags, synthetic attack scores or numerical trust/risk thresholds.

The following are explicitly **SIMULATION POLICY ASSUMPTIONS**, not industrial standards:

1. `AUTH-ROUTINE-ALLOW`: ALLOW consideration is permitted when the request is explicitly AUTHORIZED, current-mode validity is WITHIN_LIMIT, and direct IDENTITY, DEVICE and BEHAVIOR evidence is positive without a negative sign.
2. `AUTH-ROUTINE-MONITOR`: the same routine request may be considered with a logical monitoring intent. No monitoring subsystem is claimed.
3. `AUTH-VIOLATION-LIMIT`: an AUTHORIZED request outside a known current-mode range may be considered for reviewed constraint. This grants no replacement value or safe transform.
4. `AUTH-UNCERTAINTY-REVIEW`: unresolved authorization/operation semantics or a known range violation may be routed to logical human review. This grants no physical hold or external workflow.

Explicit restrictions complement these assumptions. Non-routine requests cannot receive ALLOW/MONITOR authority. A WITHIN_LIMIT request has no LIMIT authority. A resolved routine request has no REQUEST_APPROVAL authority merely as an always-present alternative. BLOCK is prohibited because no reviewed denial-impact/process-safety envelope exists. ISOLATE is prohibited because technical capability, dependency-impact review and an explicit isolation grant are absent.

## Per-action and incomplete-evidence semantics

| Action | Authority rule |
|---|---|
| ALLOW | PERMITTED only for routine authorized, valid requests with positive direct identity/device/behavior evidence |
| MONITOR | Same permission predicate as ALLOW; remains `LOGICAL_ONLY` |
| LIMIT | PERMITTED only for authorized requests outside a known range and with logical LIMIT capability |
| REQUEST_APPROVAL | PERMITTED for unresolved authorization/operation semantics or known range violations |
| BLOCK | NOT_PERMITTED: denial safety/impact authority is absent |
| ISOLATE | NOT_PERMITTED: capability and isolation authority are absent |

Current risk coverage `.45` is carried as unresolved evidence and never treated as confidence. Missing optional threat/anomaly evidence does not block routine autonomy. No numerical risk or trust cutoff is used. Direct HISTORY and CONTEXT evidence remain disclosed as insufficient but do not eliminate routine autonomy when authorization, direct identity/device/behavior evidence and current-mode semantics are established. Conversely, a trust score alone cannot grant authority.

UNKNOWN remains part of the contract for future patterns with no matching rule. Under the current declarative policy and current generator/capability space, every action is resolved to PERMITTED or NOT_PERMITTED. Capability absence overrides a permission rule. If matching permission and restriction rules conflict, `RESTRICTIVE_PRECEDENCE` deterministically returns NOT_PERMITTED while retaining all matched IDs and reasons; rule order cannot change the result.

## Seed-42 planner differential

The “before” planner uses the Day-4C.6 context with authorization but no authority assessment. The “after” planner uses the same facts plus the authority assessment. No expected action or ground truth participates.

| Event | Authorization / validity | Before | After | Change |
|---|---|---|---|---|
| S1/6 | UNKNOWN / UNKNOWN | REQUEST_APPROVAL | REQUEST_APPROVAL | none |
| S2/5 | AUTHORIZED / WITHIN [20,80] | REQUEST_APPROVAL | ALLOW, MONITOR | add ALLOW/MONITOR; remove unnecessary review |
| S2/6 | AUTHORIZED / OUTSIDE [20,80] | LIMIT, REQUEST_APPROVAL | LIMIT, REQUEST_APPROVAL | none |
| S2/7 | AUTHORIZED / OUTSIDE [20,80] | LIMIT, REQUEST_APPROVAL | LIMIT, REQUEST_APPROVAL | none |
| S2/8 | AUTHORIZED / OUTSIDE [20,80] | LIMIT, REQUEST_APPROVAL | LIMIT, REQUEST_APPROVAL | none |
| S3/6 | UNKNOWN / UNKNOWN | REQUEST_APPROVAL | REQUEST_APPROVAL | none |
| S5/5 | AUTHORIZED / WITHIN [20,80] | REQUEST_APPROVAL | ALLOW, MONITOR | add ALLOW/MONITOR; remove unnecessary review |
| S5/6 | AUTHORIZED / WITHIN [60,95] | REQUEST_APPROVAL | ALLOW, MONITOR | add ALLOW/MONITOR; remove unnecessary review |
| S5/7 | AUTHORIZED / WITHIN [60,95] | REQUEST_APPROVAL | ALLOW, MONITOR | add ALLOW/MONITOR; remove unnecessary review |

S1 retains review because neither authorization nor pump speed semantics is established. S3 retains review because HMI register authorization and operation semantics remain unknown. No LIMIT or ISOLATE is invented.

S2/5 qualifies as routine without knowledge of the later compromise. Events 6–8 retain authorization but lose permissive authority when values violate the current range. LIMIT preserves [20,80], the original 97/97/94 values and a null replacement. Trust declines and risk rises without becoming an authority threshold.

S5 evaluates current state: event 5 uses NORMAL [20,80], while events 6–7 use HIGH_OUTPUT [60,95]. All three qualify as routine. No stale NORMAL range is reused.

ALLOW and MONITOR candidates remain `execution_ready=false`. They require no human approval under this authority policy, but retain governance and executor prerequisites. MONITOR adds only `monitoring_mode=LOGICAL_ONLY`. Candidate ordering remains canonical and is not a preference.

## Five-seed authority coverage

Observed semantic coverage uses seeds 42, 123, 456, 789 and 2026, scenarios S1–S6 and 10 events per run: 300 total. This is policy coverage, not accuracy.

| Action | PERMITTED | NOT_PERMITTED | UNKNOWN |
|---|---:|---:|---:|
| ALLOW | 93 (31%) | 207 (69%) | 0 |
| MONITOR | 93 (31%) | 207 (69%) | 0 |
| LIMIT | 75 (25%) | 225 (75%) | 0 |
| REQUEST_APPROVAL | 207 (69%) | 93 (31%) | 0 |
| BLOCK | 0 | 300 (100%) | 0 |
| ISOLATE | 0 | 300 (100%) | 0 |

Scenario counts are retained in the machine-readable diagnostic. In compact PERMITTED terms: S1 ALLOW/MONITOR 15 and review 35; S2 ALLOW/MONITOR 25, LIMIT 25 and review 25; S3 review 50; S4 LIMIT/review 50; S5 ALLOW/MONITOR 50; S6 ALLOW/MONITOR 3 and review 47. Every scenario has 50 events across the five seeds. All other action/scenario combinations are NOT_PERMITTED; BLOCK and ISOLATE remain NOT_PERMITTED throughout.

## Leakage, reproducibility and verification

Tests mutate ground truth, expected action, scenario ID, provenance phase/transition/causal tags and synthetic scores across S1–S6, then rebuild authorization, authority, context and planning. Complete AuthorityAssessment, DecisionContext and PlanningResult records remain identical. Changed matching trust/risk audit identifiers are stripped before context assembly and do not alter authority or planning. The authority engine cannot invoke upstream authorization and does not mutate its input.

`evaluation/evaluate_autonomous_authority.py` emits the nine requested replay rows, complete assessments/plans and five-seed per-action/per-scenario coverage. Two runs were byte-identical with SHA-256 `d0858693a2bf4c5a2393fd07c45b2aadebde7f926a40bfe95225eabbdc33eb8b`. The authority policy fingerprint is `0da6dc24743121c2d515e8cae7634d9037c44058fe927136a8fe843e14ea652a`.

526 tests passed, 0 failed: all previous 496 plus 30 authority cases. Coverage includes immutable contracts, deterministic policy identity, routine autonomy with incomplete optional evidence, range violations, unknown authorization/semantics, current HIGH_OUTPUT limits, conservative BLOCK/ISOLATE, restrictive conflict precedence and order independence, every context consistency binding, before/after membership, canonical order, no selection fields, six-scenario leakage/audit isolation, upstream independence and repeatable five-seed coverage.

## Limitations and DecisionAgent readiness

These are explicit uncalibrated simulation rules. They do not prove physical safety, reversibility, plant topology, monitoring availability, safe transformation, denial safety, isolation capability, human workflow or execution capability. The current authority policy operationalizes a narrow routine envelope despite incomplete threat/anomaly/history/context evidence; domain review must validate that assumption before any real deployment. P01/P03 prose remains too vague to be an executable threshold policy; this authority configuration is the explicit reviewed simulation predicate layer and does not claim to infer their missing numerical meanings.

The system is ready for a narrow **proposal-only Day-4D DecisionAgent contract** because contexts now produce meaningfully differentiated, deterministic candidate sets with explicit per-action authority and unresolved requirements. It is not ready for governance approval or execution. A future DecisionAgent must not treat candidate order as rank, auto-select between ALLOW and MONITOR, fill a LIMIT replacement, or turn a proposal into authorization. A separately specified deterministic proposal policy is still required.

Final acceptance answer: **YES.** Routine-valid observable requests produce `ALLOW, MONITOR`; authorized operational violations produce `LIMIT, REQUEST_APPROVAL`; unresolved requests produce `REQUEST_APPROVAL`. These patterns arise from authorization, current-mode validity, direct evidence categories, capabilities and declarative authority rules, without labels or scenario predicates.

No DecisionAgent, GovernanceAgent or ExecutionAgent was implemented. Trust/risk mathematics, scenarios and permission rules are unchanged. Stop after Day 4C.7.
