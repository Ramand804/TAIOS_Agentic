# Day 4E — deterministic GovernanceAgent

## Responsibility and boundary

`GovernanceAgent.review(decision_context, planning_result, proposed_decision)` independently decides whether the exact proposal may proceed. It returns an immutable GovernanceDecision and never generates another proposal, substitutes an action, executes a payload, mutates state, recalculates trust/risk/authorization/authority, or reads evaluator labels.

Planning enumerates candidates. Decision proposes one. Governance independently validates the complete inference chain and normative constraints. A future ExecutionAgent may accept only an APPROVED governance artifact and must revalidate current state and execution support.

The Day-4A through Day-4D documents, actions, context, authorization, authority, planning/decision/governance contracts, planner and decider, policy configurations, governance placeholder, operational limits/state and related tests were inspected before implementation.

## Contract and API

The existing GovernanceDecision statuses remain unchanged: APPROVED, APPROVAL_REQUIRED, VETOED and OVERRIDDEN. The contract received two narrow compatible changes:

* `proposed_action` may be null for a fail-closed empty/no-decision review.
* Optional immutable `check_reasons` maps every policy-check ID to its deterministic explanation. When supplied, its keys must exactly match `policy_checks`.

Existing callers may omit `check_reasons`. APPROVED/OVERRIDDEN still require an action, payload, authorization reference, all checks PASS and no violations. VETOED/APPROVAL_REQUIRED carry no authorized action, payload or authorization reference.

Governance policy version: `day4e-governance-v1` — **PROVISIONAL / UNCALIBRATED**. `GovernanceDecision.reference` is the deterministic governance fingerprint. For APPROVED results, `authorization_reference` is a deterministic internal binding over context, plan, proposal, action, exact payload, checks and governance version. It is not a secret or external token; the GovernanceDecision remains the authorization artifact.

## Independent checks

Every review records these canonical checks and reasons:

| Check | Meaning |
|---|---|
| PROPOSAL_BOUND | Context reference, plan context/version, proposal context, planning reference/version and exact candidate set match |
| PLANNER_CANDIDATE | Proposed action/reference/payload is the exact plan candidate and capability reference matches context |
| AUTHORIZATION_VALID | Request authorization is present when the action permits/constrains the operation |
| AUTHORITY_VALID | Bound autonomous authority explicitly permits the proposed action |
| OPERATIONAL_VALIDITY | Current bound semantics support the action; no range recomputation occurs |
| ACTION_PAYLOAD_COMPLETE | Required exact action fields and action-specific semantics exist |
| REVIEW_REQUIREMENT | Human approval is absent, pending or not required |
| POLICY_CONFLICT | No explicit current authority-policy prohibition conflicts with the action |
| EXECUTION_PREREQUISITES | Governance artifact is complete; future executor capability remains separately mandatory |

Binding and candidate-integrity failures fail closed as VETOED before governance attempts semantic repair. Governance never reconstructs a plan or proposal.

## Status semantics

**APPROVED** means all nine checks pass for the exact context/action/payload. It provides a deterministic authorization artifact for a future executor. It does not mean execution occurred or physical outcome is safe.

**APPROVAL_REQUIRED** means a legitimate review path exists but external human approval, required information or transformation remains unresolved. No action/payload is authorized. REQUEST_APPROVAL always yields this status. A current LIMIT with null replacement and explicit approval prerequisite also yields this status.

**VETOED** means a hard binding, capability, authorization, authority, validity, payload or policy constraint failed. Governance does not repair the proposal. Empty/no-decision input is vetoed because there is no action to authorize and no fallback is injected.

**OVERRIDDEN** is supported by the frozen contract but never emitted in Day 4E. No reviewed override rule exists, so GovernanceAgent never substitutes MONITOR, LIMIT, BLOCK or any other action.

## Per-action rules

* **ALLOW:** requires exact plan/proposal binding, AUTHORIZED request, PERMITTED ALLOW authority, bound WITHIN_LIMIT semantics, complete exact payload, no human-review prerequisite and no policy conflict. Trust/risk scores do not control approval.
* **MONITOR:** applies the same authorization/authority/validity rules and requires `monitoring_mode=LOGICAL_ONLY`. Governance may approve the logical candidate while explicitly retaining future monitoring/executor support as a later check; no physical monitoring subsystem is claimed.
* **LIMIT:** requires an established bound OUTSIDE_LIMIT context, PERMITTED authority, exact current range, a non-boolean numeric replacement inside that range, and no unresolved approval prerequisite. Current candidates have `replacement_value=null` and `requires_approval=true`, so they cannot be approved. Governance never fills a value.
* **REQUEST_APPROVAL:** exact review payload is verified, then status is APPROVAL_REQUIRED. It never becomes an execution approval and no human response is fabricated.
* **BLOCK:** current authority prohibits it and denial safety/payload semantics are absent, so synthetic proposals are VETOED.
* **ISOLATE:** current capability/authority prohibits it and isolation impact/payload semantics are absent, so synthetic proposals are VETOED.

UNKNOWN authorization or operational semantics cannot pass permissive governance. Insufficient information generally routes to APPROVAL_REQUIRED when the action and policy offer a meaningful review path. Explicit prohibitions, outside-limit permissive proposals and integrity failures are VETOED.

Trust and risk remain evidence only. The reason records the exact trust estimate and risk estimate with weighted coverage, followed by “no score threshold applied.” Risk coverage `.45` is not interpreted as confidence. Governance accepts the authority policy’s prior determination that incomplete optional evidence does not block routine autonomy.

## Seed-42 replay

| Event | Proposal | Governance | Authorized action |
|---|---|---|---|
| S1/6 | REQUEST_APPROVAL | APPROVAL_REQUIRED | none |
| S2/5 | ALLOW | APPROVED | ALLOW |
| S2/6 | REQUEST_APPROVAL | APPROVAL_REQUIRED | none |
| S2/7 | REQUEST_APPROVAL | APPROVAL_REQUIRED | none |
| S2/8 | REQUEST_APPROVAL | APPROVAL_REQUIRED | none |
| S3/6 | REQUEST_APPROVAL | APPROVAL_REQUIRED | none |
| S5/5 | ALLOW | APPROVED | ALLOW |
| S5/6 | ALLOW | APPROVED | ALLOW |
| S5/7 | ALLOW | APPROVED | ALLOW |

S2/5 passes all checks using NORMAL [20,80]. S2/6–8 preserve review because safe LIMIT transformation is unresolved; governance never changes the proposal to LIMIT. S3 retains UNKNOWN authorization/operation semantics and no approval response is invented. S5/6–7 use the bound HIGH_OUTPUT [60,95] range; no NORMAL range is reconstructed.

Governance fingerprints in row order:

* S1/6 `fbb389c720f984a2e511d6058495402ec50f3cb6c2a09e6036a57cdf615d8c6e`
* S2/5 `3a25ce63374e691a732e5d49bb17de6e3576b85fab083392bfb96c3df004c875`
* S2/6 `a12db44a000bea869d78c326e1a168d3a0747b5419eecef7eb955fea32d9c784`
* S2/7 `4bd6beca051d60833d8a5e9f04de51b2f80e2ba69800b9652d94fc2ab34b3c9f`
* S2/8 `012e959c7d80ee25b49a41f8ef873e1aaab53499f89804c923f1f780d41cba55`
* S3/6 `85825d6bf7e37ec4c1205cb64ea73b6cf0d3571e68e022fd4337faae12d8e273`
* S5/5 `819f254e4767d6ae5255caf7ba992826005f9a5d915572584bcc5c55fba96d02`
* S5/6 `df39c552c955d779ca8260887ac9a2ab0f77695f6e7f637df361c2d823431cf7`
* S5/7 `f7bd7102d5db4d674eab73295006a5abef202c4cfdb8d4d25cb92c79e001aa53`

## Five-seed distribution and structural metrics

Across S1–S6, seeds 42/123/456/789/2026 and 10 events per run:

| Status | Count | Rate |
|---|---:|---:|
| APPROVED | 93 | 31% |
| APPROVAL_REQUIRED | 207 | 69% |
| VETOED | 0 | 0% |
| OVERRIDDEN | 0 | 0% |

All 93 ALLOW proposals were APPROVED. All 207 REQUEST_APPROVAL proposals remained APPROVAL_REQUIRED. Normal replay has no malformed or unsupported proposal, so its veto rate is zero. Separate deterministic synthetic probes prevented 2/2 binding failures and 2/2 unsupported action injections (BLOCK and ISOLATE), all by VETO. These are structural policy metrics, not claims of effectiveness against attacks or evaluator-label accuracy.

## Tampering, leakage and determinism

Tests cover wrong context, planning reference/version, plan/context binding, candidate-set substitution, capability mismatch, proposal outside plan, UNKNOWN authorization for ALLOW, NOT_PERMITTED authority, outside-limit ALLOW, null LIMIT replacement, MONITOR handling, injected BLOCK/ISOLATE and empty proposals. None is incorrectly approved. Hard binding failures are vetoed rather than raised or repaired once valid contract objects reach review.

Changing ground truth, expected action, scenario ID, provenance phase/transition/causal tags and synthetic scores across S1–S6 leaves the complete GovernanceDecision unchanged. Matching changed audit IDs are stripped upstream and cannot change status, authorized action, checks or fingerprint. Trust values 0, 1 and .25 and different valid risk weighting configurations leave routine ALLOW governance APPROVED when semantic prerequisites remain identical.

584 tests passed, 0 failed: all previous 549 plus 35 governance cases. The suite also verifies immutability, non-mutation, deterministic fingerprints, capability-reference binding, a synthetic complete bounded LIMIT, and no override behavior.

Two complete `evaluation/evaluate_governance_agent.py` runs were byte-identical with SHA-256 `d774f97adcb54dbb07566d65cc3d0e8ff92baf660a95ec7d9cd90148f3b2196d`.

## Limitations and future ExecutionAgent contract

Governance rules are provisional and uncalibrated. APPROVED establishes policy permission for the exact artifact; it does not prove physical safety or executor support. Logical MONITOR has no monitoring service. No complete LIMIT payload currently exists. REQUEST_APPROVAL has no external workflow or physical hold. BLOCK/ISOLATE lack safety envelopes and technical semantics. Policy prose P01/P03 remains non-numeric; governance relies on the explicit authorization/authority facts already bound into context rather than inventing thresholds.

A future ExecutionAgent must accept only an APPROVED GovernanceDecision with non-null authorized action/payload/reference, all policy checks PASS, no violations and a valid governance fingerprint. It must resolve and verify the exact referenced ProposedDecision, PlanningResult and DecisionContext; verify the authorized action/payload exactly matches the proposal candidate; re-read current state/mode/limits and invalidate stale authorization; verify action-specific simulated executor support; enforce caller-owned single-use/idempotency; and return an explicit unsupported/failure outcome without mutation when any check fails. VETOED and APPROVAL_REQUIRED artifacts are never executable.

No action was executed and IndustrialState was never passed to or mutated by GovernanceAgent. No ExecutionAgent was implemented. Upstream trust/risk/authorization/authority/planning/decision policies and scenarios are unchanged. Stop after Day 4E.
