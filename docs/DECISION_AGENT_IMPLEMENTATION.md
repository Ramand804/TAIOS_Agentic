# Day 4D — deterministic proposal-only DecisionAgent

## Responsibility and boundaries

`DecisionAgent.decide(decision_context, planning_result)` deterministically selects exactly one supplied candidate for proposal, or returns the existing explicit no-admissible-action representation when the plan is empty. It never approves, executes, mutates state, recalculates evidence, calls authorization/authority engines or reads evaluator labels.

Planning answers which alternatives satisfy current candidate prerequisites. Decision chooses one candidate under a declared semantic proposal policy. Future Governance must independently verify the exact context, plan, proposal, policy and payload before authorizing anything. Execution must accept only that future governance authorization.

Before implementation, the Day-4A through Day-4C.7 documents, actions, context, authority, decision contracts, PlanningResult, PlanningAgent, context builder, authority engine, both policy configurations and related tests were inspected.

## Contract and binding

The existing immutable `ProposedDecision` was scientifically adequate and already supported `selected_action=None` only with an empty candidate set, yielding `NO_ADMISSIBLE_ACTION`. It was extended compatibly with optional `planning_reference` and `planning_policy_version`. Existing callers may omit both; supplying only one is rejected. Real DecisionAgent outputs always bind both.

Every proposal contains the exact canonical candidate objects, selected action/reference, primary reason, evidence summary, trust/risk descriptions, uncertainty, policy basis, deterministic alternatives, context reference, planning reference/version and decision policy version. `selected_payload` is exported from the exact selected candidate. `ProposedDecision.reference` is the decision fingerprint because it hashes the complete deterministic record.

Decision policy version: `day4d-decision-v1` — **PROVISIONAL / UNCALIBRATED**. No time, randomness or UUID affects inference.

DecisionAgent rejects raw objects, wrong contract types, a planning context fingerprint that differs from `DecisionContext.reference`, or a context-version mismatch. It canonicalizes candidate action order before applying semantic rules, verifies action uniqueness, and never chooses an action outside the plan.

## Semantic selection policy

1. **Empty plan:** return ProposedDecision with no action, no candidate reference and status `NO_ADMISSIBLE_ACTION`. Never inject ALLOW.
2. **Single candidate:** propose that exact candidate. This makes REQUEST_APPROVAL a legitimate proposal rather than a failure.
3. **ALLOW + MONITOR:** require bound AUTHORIZED status, WITHIN_LIMIT current-mode validity, explicit ALLOW authority and an ALLOW candidate without a human-approval prerequisite. Propose ALLOW; retain MONITOR as the alternative. Nonzero/partial risk does not force MONITOR.
4. **LIMIT + REQUEST_APPROVAL:** require the bound OUTSIDE_LIMIT check and explicit LIMIT authority. The existing Day-4C candidate has `requires_approval=true`, `replacement_value=null`, and unresolved reviewed-transform requirements. Therefore propose REQUEST_APPROVAL and retain LIMIT as the alternative. DecisionAgent does not clamp or invent a replacement.
5. **Other future multi-candidate sets:** if REQUEST_APPROVAL exists and another candidate explicitly requires human approval, propose review. Otherwise reject the unsupported combination until a reviewed semantic rule is added. Candidate tuple position is never a fallback preference.

BLOCK and ISOLATE cannot be manufactured. They could only be proposed if a future PlanningResult actually contained them and an applicable decision rule covered the set. Current PlanningAgent never supplies either.

## Evidence and explanation

Every proposal deterministically answers:

* WHAT: selected action, selected candidate reference and exact candidate payload.
* WHY: the semantic selection rule in `primary_reason`.
* EVIDENCE: authorization, autonomous authority policy, current-mode validity, exact trust estimate/direct coverage, exact risk estimate/weighted coverage and planning reference.
* ALTERNATIVES: every non-selected candidate with its rationale, in canonical order.
* UNRESOLVED: de-duplicated PlanningResult constraints and selected-candidate prerequisites.

Trust values are reported without high/low classes. Risk is described as an estimate with weighted evidence coverage and explicitly not as attack probability or calibrated severity. Neither score participates in selection. Authorization and authority are consumed from DecisionContext; their engines are never rerun. Operational limits are consumed from the bound capability validity; DecisionAgent never reconstructs ranges or modes.

The fingerprint changes when the context reference, candidate set, selected candidate/action or proposal content changes. Identical context and plan produce the same fingerprint. Audit identifiers remain outside context and proposal fingerprints.

## Seed-42 diagnostic replay

| Event | Candidates | Proposal | Alternatives | Reason |
|---|---|---|---|---|
| S1/6 | REQUEST_APPROVAL | REQUEST_APPROVAL | none | sole admissible candidate |
| S2/5 | ALLOW, MONITOR | ALLOW | MONITOR | authorized routine request is valid in NORMAL [20,80] |
| S2/6 | LIMIT, REQUEST_APPROVAL | REQUEST_APPROVAL | LIMIT | LIMIT requires approval and exact reviewed transform |
| S2/7 | LIMIT, REQUEST_APPROVAL | REQUEST_APPROVAL | LIMIT | same; no value inferred |
| S2/8 | LIMIT, REQUEST_APPROVAL | REQUEST_APPROVAL | LIMIT | same; no value inferred |
| S3/6 | REQUEST_APPROVAL | REQUEST_APPROVAL | none | permission and register semantics unresolved |
| S5/5 | ALLOW, MONITOR | ALLOW | MONITOR | valid NORMAL request in [20,80] |
| S5/6 | ALLOW, MONITOR | ALLOW | MONITOR | valid HIGH_OUTPUT request in [60,95] |
| S5/7 | ALLOW, MONITOR | ALLOW | MONITOR | valid HIGH_OUTPUT request in [60,95] |

S2 events 6–8 remain range violations while authorization stays valid and trust/risk change. DecisionAgent does not reinterpret those scores as attack evidence. S5 events 6–7 use the bound HIGH_OUTPUT range; no stale NORMAL limit is reconstructed.

Observed decision fingerprints for the nine rows, in table order:

* S1/6 `b6c92406610c1f5697b7f22fd947c90a55696a1889790deb9067fa049455ea6a`
* S2/5 `de6f92b82df7defa836756fdd85fa2b3a9a98eb703e59113af40d6ff46804309`
* S2/6 `38c9435fe1b893835c4f806ad325f44ba31fe580bfb8a269d4aa2872aeffd9a7`
* S2/7 `fe000fc92b203a9ab071ac0de0ef5be15df885389e2a49f6702a358374f0d644`
* S2/8 `2fc91930bd05cde037c34f29506e465401d27017470bd3fcea2e25e0b0694052`
* S3/6 `9071f9a210b336373a8ff23fc4a06960d4f7b8401e90f0a12d37e9f2ab2a53ef`
* S5/5 `86877ad6aabf5151c9486523c6396d331156ea36384034b27083e435a27a47a6`
* S5/6 `147ebe52569a01e37849a8ab7a45e3fc7a5528202e02e7b23ebc876c66440bfb`
* S5/7 `b2b1f1c5459dd31cfb7891aa764834a007eaf350980ee56c69bb6bdb835cd2f4`

## Five-seed proposal distribution

Across S1–S6, seeds 42/123/456/789/2026 and 10 events per run, 300 proposals were generated. This is a policy distribution, not accuracy and not post-label agreement.

| Proposal | Count |
|---|---:|
| ALLOW | 93 |
| MONITOR | 0 |
| LIMIT | 0 |
| REQUEST_APPROVAL | 207 |
| BLOCK | 0 |
| ISOLATE | 0 |
| NO_DECISION | 0 |

Per scenario: S1 15 ALLOW / 35 REQUEST_APPROVAL; S2 25 / 25; S3 0 / 50; S4 0 / 50; S5 50 / 0; S6 3 / 47. LIMIT authority/candidacy does not become a LIMIT proposal because its exact current candidate contract requires approval and lacks a transformation payload. No evaluator agreement was calculated, avoiding any risk of policy tuning from labels.

## Verification and leakage boundary

549 tests passed, 0 failed: all prior 526 plus 23 DecisionAgent cases. Tests cover construction, binding, immutable deterministic outputs, fingerprint sensitivity, sole candidate, routine ALLOW/MONITOR, LIMIT/review semantics, explicit empty-plan behavior, membership invariants, alternatives, mismatch rejection, permutation invariance, multiple trust values/risk configurations with unchanged semantic proposal, current HIGH_OUTPUT behavior, no BLOCK/ISOLATE manufacture, six-scenario leakage/audit isolation, upstream-engine non-use and repeatable five-seed evaluation.

Changing ground truth, expected action, scenario ID, provenance phase/transition/causal tags and synthetic scores does not change ProposedDecision. Matching changed audit metadata is stripped upstream and does not change action, alternatives, reason or fingerprint. Equivalent semantic candidate sets passed in reverse order produce the same action and reason after canonicalization. Trust values 0, 1 and .25 and materially different valid risk weight configurations do not change routine ALLOW selection while evidence text reflects the supplied values.

Two `evaluation/evaluate_decision_agent.py` executions were byte-identical. SHA-256 for each complete diagnostic: `2b99bc996b520943c4e362ee313277eb48b68f4b9648880d590f668f8552148e`.

## Limitations and GovernanceAgent input

The proposal policy is provisional and uncalibrated. It handles the three candidate patterns currently produced plus empty plans and explicit human-approval prerequisites. It deliberately rejects unknown future ambiguous multi-action sets. It has no utility model, learned preference, outcome prediction, cost model or physical-safety proof. ALLOW is a proposal, not execution permission. REQUEST_APPROVAL does not create a physical hold or contact a person. No LIMIT transform exists.

A future GovernanceAgent will receive the immutable ProposedDecision containing the exact candidate set, selected candidate reference/action/payload, reason/evidence/uncertainty/alternatives, context reference, planning reference/version and decision policy version. It must also receive or resolve the exact immutable DecisionContext and PlanningResult identified by those references. Governance must independently revalidate permission, authority, current state/mode, policy, payload and all mandatory constraints; it must not trust the proposal as approval.

No governance approval occurred and nothing was executed or mutated. No GovernanceAgent or ExecutionAgent was implemented. Trust/risk/scenario/authorization/authority/planning policies and mathematics are unchanged. Stop after Day 4D.
