# TAIOS autonomous decision and governance specification — Day 4A

Specification version: `day4a-spec-v1`. Documentation only.

**FROZEN DESIGN PRINCIPLE** denotes a required architectural/safety boundary for later implementation. **PROVISIONAL POLICY** denotes a proposed deterministic policy needing review and evaluation. **UNCALIBRATED PARAMETER** denotes a value without validated operational meaning. **FUTURE EVALUATION REQUIREMENT** denotes a study or acceptance test, not a current result. No new runtime capability is implied.

## 1. Scope

Specify Context + TrustAssessment + RiskAssessment → candidates → proposed decision → governance review → authorized simulated action. Do not implement agents, detectors, authorization, adaptation, calibration, LLMs or new trust/risk mathematics. Existing milestones remain frozen.

Inspected directory inventories under agents/, governance/, core/, config/; config/risk.yaml, policies.yaml, system.yaml; core/decision_record.py; governance/policy_engine.py; environment/scenarios.py, event.py and expected_safe_action assignments in event_generator.py. Consulted TRUST_MODEL_SPEC.md, TRUST_AGENT_IMPLEMENTATION.md, TRUST_EVALUATION.md, RISK_MODEL_SPEC.md, RISK_AGENT_IMPLEMENTATION.md and RISK_EVALUATION.md.

Only BaseAgent, TrustAgent and RiskAgent currently exist. Planning/Decision/Governance/Execution agents are absent. policy_engine.py is a docstring placeholder; safety_constraints.py and human_approval.py do not exist. No operational control or approval service is available.

## 2. Architectural boundaries

**FROZEN DESIGN PRINCIPLE:** Planning enumerates conditionally admissible actions and explicit prerequisites; Decision proposes one; Governance independently verifies permission and safety constraints; Execution accepts only a valid governance authorization. No stage merges into a single risk-threshold function. Governance is logically independent validation, not a claim of separate infrastructure or formal verification.

Neither planning nor decision may mutate plant state. Governance may reject even the highest-ranked candidate. Executor cannot reinterpret a proposal as permission. Human approval does not bypass non-waivable constraints or replace governance revalidation.

## 3. Canonical action vocabulary

The same six strings appear in system.yaml, event.py and DecisionRecord. Preserve them exactly.

| Action | Operational semantics for later simulation | Prerequisites and limits |
|---|---|---|
| ALLOW | Permit the exact requested operation once | Explicit permission envelope, valid current-mode semantics and execution capability; permission does not guarantee physical safety |
| MONITOR | Permit the operation once with specified enhanced observation/audit | All ALLOW prerequisites plus an available monitoring plan; monitoring does not make an otherwise unsafe command permissible |
| LIMIT | Permit an explicitly transformed/constrained operation | Named safe constraint/transform, resulting payload, current-mode validation and capability; do not blindly clamp values |
| REQUEST_APPROVAL | Hold this requested operation pending scoped human authorization | No original operation executes while pending; define hold feasibility and disposition |
| BLOCK | Deny this requested operation | Does not stop the process, isolate a source, or reverse an earlier action; impact of denying the request must be assessed |
| ISOLATE | Deny the operation and logically restrict a specifically identified responsible source/entity | Separate isolation capability, justified scope, impact/dependency review and explicit authority; never automatically isolate the target victim |

No seventh action is introduced. Error, pending, rejected and unsupported are workflow statuses, not action labels. A failed hold or absent execution capability cannot silently become ALLOW.

## 4. DecisionContext

**FROZEN DESIGN PRINCIPLE:** Immutable, validated, label-safe context containing the existing exact safe observation; public trust/risk inference views; explicit policy bundle/version; trusted operational-limit reference/version; declared action capabilities; and a minimal approved observable state view. Source/target and trust/risk versions must agree across inputs. Preserve score, component contributions, availability and evidence coverage separately.

Current safe context exposes production_state and operating_mode only. Full IndustrialState snapshots additionally contain maintenance/emergency flags, health/status and versions, but are not approved agent inputs. Later use requires a narrow reviewed projection with a reliable source and freshness contract. Do not fetch raw state_snapshot to bypass the allowlist or infer NORMAL from ACTIVE.

Request/assessment pairing remains an orchestration obligation: current version/audit checks do not prove content binding. A later immutable context reference must bind the exact safe payload, relevant state/reference versions, trust/risk versions and policy/capability configuration; runtime delivery and original event IDs remain outside inference. No timestamp-based freshness inference is specified.

Forbidden: ground_truth, expected_safe_action, scenario ID, provenance phase/transition/causal tags, compromise markers, synthetic attack/anomaly fixtures and full ExperimentRun configuration containing manifests. Audit metadata may reject mispaired transactions but must not change the semantic choice for equivalent valid context.

## 5. CandidateAction

Future immutable contract: action; exact action payload/scope; rationale; expected safety effect; operational impact; reversibility description; requires_approval; policy_constraints; evidence_basis; unresolved_prerequisites; capability reference; planning_policy_version; deterministic candidate reference.

Safety effect and impact are qualitative, explicitly assumed predictions, not observed outcomes. No numeric utility is invented. Evidence basis contains approved observable facts and references, not raw labels or free-form hidden metadata. LIMIT must contain the proposed bounded payload; ISOLATE must identify source scope and restoration prerequisites.

An approval-required candidate is admissible to propose, not executable. Candidates whose hard prerequisites fail must not appear as executable choices; keep rejected alternatives and reasons separately. REQUEST_APPROVAL itself never smuggles in an implicitly approved original command.

## 6. PlanningAgent responsibility

**PROVISIONAL POLICY:** Deterministically enumerate the canonical vocabulary in fixed order, test capabilities, hard constraints and evidence prerequisites, and return candidates plus exclusions. No final selection or plant modification. ALLOW/MONITOR require known current-mode conformance and an explicit operation permission envelope. LIMIT requires a reviewed safe transformation. ISOLATE requires an explicit containment envelope, not just high distrust.

Missing permission/capability information is UNKNOWN, not PASS. Candidate ordering is for stable serialization, not a safety ranking. If none is supportable, return no executable candidates and the blocking prerequisites; later orchestration may present a non-executing review request if supported.

## 7. DecisionAgent responsibility

Input: validated DecisionContext and candidates. Output: ProposedDecision, never execution.

**PROVISIONAL POLICY:** Apply ordered, explainable rules rather than scoring actions with a second utility formula:

1. Reject invalid/mispaired context and noncanonical or payload-inconsistent candidates.
2. A verified non-waivable constraint violation excludes permissive execution. Prefer a validated LIMIT only where policy explicitly permits the transformation; otherwise propose BLOCK if denying this request has an approved envelope. If consequences cannot be established, defer for review without pretending a safe physical stop has occurred.
3. Unknown behavior/permission or conflicting required evidence excludes confident ALLOW/MONITOR. Prefer REQUEST_APPROVAL when a hold/review path exists. Known authentication failure cannot be directly permitted (P02); distinguish it from missing authentication evidence.
4. Within a reviewed low-impact permission envelope, known conformance and no unresolved adverse evidence permit ALLOW; choose MONITOR if policy requires and capability provides additional observation. Incomplete optional signals remain disclosed.
5. ISOLATE is eligible only under a separately explicit containment rule or an approved human request, with impact checks. One limit violation or a low composite score is insufficient.

Risk/trust values and their contributions enter evidence summaries and later reviewed policy predicates; they do not independently create authority. Escalating distrust may require review within an approved policy, but there is no newly calibrated cutoff or mandatory S2 action sequence. If rules cannot resolve competing candidates, use explicit approval-required deferral, not arbitrary action ordering. Policy authors must define precedence before enabling autonomy.

## 8. ProposedDecision

Future immutable fields: selected_action (nullable only for no admissible proposal); selected_candidate_reference; candidate_actions; primary_reason; evidence_summary; trust_basis; risk_basis; uncertainty/coverage; policy_basis; alternatives_considered; exact payload; context_reference; decision_policy_version; status PROPOSED or NO_ADMISSIBLE_ACTION.

A proposal carries no execution authority. Include numeric risk and decomposition, not a fabricated risk class. Alternatives include excluded options and their failed prerequisites. The selected candidate must be an exact member of the supplied candidate set.

## 9. GovernanceAgent responsibility

Independently verify context/payload binding, capability, approval requirements, state/reference versions and invariant constraints against the trusted policy bundle. Do not just accept DecisionAgent's claimed checks or repeat its preference ranking. Recompute normative constraint checks from approved references; do not recalculate trust/risk scores.

- APPROVE: authorize this exact candidate/payload in this context after all mandatory checks pass.
- VETO: prohibit the proposal; no authorized action or executable token.
- REQUIRE_APPROVAL: hold the operation; no execution authorization until a scoped approval is validated and governance reruns.
- OVERRIDE_TO_SAFER_ACTION: authorize a different validated candidate only where a named policy establishes safer behavior for this context and all prerequisites pass. No universal action ranking justifies an override.

Governance may instead require approval if safety dominance is unknown. It must never upgrade BLOCK to ALLOW merely to keep production moving or relabel ISOLATE as MONITOR without checking the operational implications.

## 10. GovernanceDecision

Future immutable fields: status APPROVED/VETOED/APPROVAL_REQUIRED/OVERRIDDEN; proposed_action; authorized_action; authorized_payload; context/proposal reference; policy_checks with PASS/FAIL/UNKNOWN; violations; reason; governance_policy_version; approval evidence reference when applicable; scoped authorization reference.

APPROVED and OVERRIDDEN may carry an authorization only if mandatory checks pass and no human approval remains outstanding. VETOED and APPROVAL_REQUIRED have authorized_action=null and no executable authorization. APPROVAL_REQUIRED records pending_action=REQUEST_APPROVAL separately as workflow routing. An approved REQUEST_APPROVAL can at most create a logical hold/review record, never execute the underlying industrial command.

## 11. ExecutionAgent responsibility

Later simulation only: accept governance authorization, exact payload and current state; reject raw ProposedDecision. Check authorization scope, policy/context/state binding and single-use delivery before mutation. If relevant state/mode/limits changed, invalidate and return for re-evaluation; never silently execute with stale approval.

ALLOW/MONITOR/LIMIT may apply only explicitly supported simulated operation semantics. BLOCK records denial without altering target process state. REQUEST_APPROVAL records a hold. ISOLATE requires a separately defined logical isolation representation. Current IndustrialState has no isolation/approval state; do not equate OFFLINE with ISOLATED or invent writes now. Unsupported operations yield an explicit not-executed result.

Retries must be idempotent under a caller-owned execution reference. Real PLC/network actuation is outside this prototype specification. A failure cannot be reported as successful enforcement.

## 12. ExecutionResult

Future immutable fields: requested_action; authorized_action; executed_payload; execution_status (SUCCEEDED, DENIED, PENDING_APPROVAL, REJECTED, UNSUPPORTED, FAILED); state_before/state_after as approved simulation views; reason; governance_reference; outcome facts; execution_policy_version.

Separate “request denied” from a process-state change and separate intended safety effect from observed outcome. On no mutation, state_after equals state_before or is explicitly unavailable if state cannot be read. Never infer success from expected_safe_action. Latency is measured runtime metadata, not a deterministic decision feature.

## 13. DecisionRecord

Existing DecisionRecord is a mutable Day-1 record with event_id, selected_action, context, trust dimensions, attack_probability, risk_score, candidate string list, policy_checks, governance_status, explanation, execution status/outcome, latency, versions, random UUID and datetime.now defaults. It validates only selected_action. It is not an authorization object and cannot represent all new nested contracts or no-selected-action states safely without later explicit evolution.

**FROZEN DESIGN PRINCIPLE:** Preserve the existing interface now. A future versioned record/envelope should combine approved observation/context, trust/risk exports, candidates, proposal, governance and execution/outcome, plus all policy/model/reference versions. Keep original event records and evaluator labels in a separate post-pipeline join keyed by an outer audit reference. Never pass DecisionRecord's unconstrained context into inference.

For future deterministic experimental mode, use a canonical-content identity and explicit simulation ordering; keep legacy standalone UUID/time behavior compatible. Exclude real latency, wall-clock metadata and audit IDs from semantic fingerprints. Do not overload selected_action to hide proposed versus authorized versus executed actions. No record migration is performed in Day 4A.

## 14. Risk/trust coverage handling

Current risk coverage .45 means only distrust and target criticality contribute; it is not 45% certainty. Risk .53 at .45 coverage and risk .53 at full component availability must carry different evidence/authority assessments. Even full component availability is not validated safety or calibrated confidence.

Trust's numeric composite must travel with direct evidence coverage and prior-only dimensions. Successful authentication or favorable .8 prior cannot substitute for behavioral semantics or authorization. Direct HISTORY may be insufficient despite internal history updates; do not manufacture independent evidence.

**PROVISIONAL POLICY:** Action-specific evidence requirements determine eligibility. Unknown optional threat/anomaly need not forbid all routine, explicitly permitted, low-impact simulated operations. Missing essential behavioral/permission/impact evidence does exclude autonomous permissive or disruptive execution. Do not raise risk numerically because coverage is missing or set a global minimum coverage threshold without calibration.

## 15. Uncertainty handling

Track known conformance, known violation and unknown separately for each required predicate. UNKNOWN cannot pass a mandatory safety check. Missing evidence is neither proof of attack nor evidence of safety. Null risk is unavailable information, not zero danger. Request human review when required evidence is unavailable and a reviewed hold path exists.

Deferral is not inherently physically safe: withholding a needed command can itself cause harm. Record whether delay/denial has an approved safe operating envelope. With no such envelope, report unsupported/unresolved handling and require external intervention; do not autonomously improvise actuation or isolation. This prototype cannot supply a real plant fail-safe design.

## 16. Autonomous authority

**PROVISIONAL POLICY:** Autonomous execution requires an explicit versioned envelope for the operation, target, current mode, action capability, impact/reversibility and required evidence. No such complete envelope exists in current YAML. Human/operation authorization is not inferred from authentication.

Permissive action requires conformance and permission; bounded LIMIT additionally requires safe transformation semantics; restrictive BLOCK requires a reviewed denial impact; disruptive ISOLATE requires an explicit isolation grant and dependency/impact evidence or validated scoped human approval. No autonomous isolation is enabled by current coverage or the existing prose policies. Emergency exceptions require an explicit reviewed policy and approved emergency observation source; neither exists now.

Criticality informs consequence review, not a numeric “critical” cutoff invented from .91/.95 fixtures. Isolation impact concerns the source and dependent equipment, not just target asset_criticality. Decisions cannot reuse target criticality as an isolation-cost estimate.

## 17. Reversibility

ALLOW and MONITOR are permissive; LIMIT is constrained-permissive/cautionary; REQUEST_APPROVAL is cautionary deferral; BLOCK is restrictive; ISOLATE is disruptive containment. These are semantic categories, not numerical ranks.

Permission to operate can produce irreversible physical change; ALLOW is not inherently highly reversible. MONITOR shares those consequences. A software limit may be removable while an applied actuator change is not undoable. BLOCK may have serious consequences by omitting a required action. Isolation may interrupt a safety dependency. Review payload-specific reversibility, restoration procedure and interruption risk. Prefer lower demonstrated disruption only among actions that independently satisfy safety constraints; unknown reversibility does not imply reversible.

## 18. Safety invariants

**FROZEN DESIGN PRINCIPLES:**

1. No operation execution without valid governance authorization for the exact current payload/context.
2. Labels and privileged simulator metadata never enter decision inference.
3. Missing evidence never counts as satisfied safety/permission requirements.
4. Governance can veto or require approval regardless of DecisionAgent preference.
5. Disruptive actions need explicit scope, evidence, impact review and authority.
6. Every proposal, review and execution outcome is traceable; versions are recorded.
7. Current observed mode and trusted limits determine conformance; stale mode approvals are invalidated.
8. Uncalibrated thresholds cannot be presented as validated policies or automatically enabled.
9. Audit identifiers do not change valid-context semantic choices; mismatches reject pairing rather than alter scores/actions.
10. Authentication alone does not establish behavioral authorization.
11. Human approval does not waive non-waivable constraints; it is scoped, checked and re-reviewed after material context change.
12. LIMIT never silently transforms a request and ISOLATE never silently expands its scope.
13. Failure/unsupported capability is not successful enforcement; retry cannot execute twice.
14. No stage claims physical safety, outcome or attack detection not supported by observed evidence.

## 19. Policy conflicts

Existing P01 (“high-risk” commands targeting “critical” assets require restriction), P02 (unauthenticated control not directly allowed), P03 (critical/conflicting evidence may require approval) are enabled prose. P01/P03 lack predicates, coverage requirements, impact definitions and precedence; P02 lacks a defined control-operation classification. Enabled prose must not be mistaken for an executable reviewed rule set.

**PROVISIONAL POLICY:** Non-waivable safety prohibitions dominate grants; explicit approval requirements dominate autonomous permissions; unresolved contradictory rules prohibit autonomous execution and route to review. An unknown mandatory policy predicate cannot default to allow. Governance checks rule IDs/versions and records conflicts rather than resolving them via risk thresholds.

ALLOW versus approval-required → APPROVAL_REQUIRED, no original execution. ISOLATE versus insufficient authority → VETOED or APPROVAL_REQUIRED; override to a narrower denial only when an approved context-specific rule proves it acceptable. Governance wins in both cases. Do not claim BLOCK is universally safer than ISOLATE or ALLOW.

## 20. Human approval

REQUEST_APPROVAL is an explicit decision under uncertainty, not pipeline failure. Bind a future human decision to exact payload/scope, approver authority, context/policy versions and a deterministic approval reference. No approval is inferred from silence. A timeout/denial leaves the original operation unexecuted and triggers a reviewed hold/denial disposition; timeout duration and operational consequences remain unspecified pending policy review.

A changed mode, payload, target, relevant state or policy invalidates prior approval and requires governance recheck. Approval provider, identity verification, role/operation authority and persistence are future prerequisites; no authorization model or external notification is implemented here. Separate appropriate approval from unnecessary burden in evaluation.

## 21. Explainability and versioning

Records must answer WHAT (proposed/authorized/executed), WHY (observable reasons), EVIDENCE (trust/risk decomposition and uncertainties), POLICY (rule IDs and check outcomes), ALTERNATIVES (candidate/exclusion rationale), OUTCOME (observed result). Deterministic structured templates suffice; no LLM is required.

Proposed initial versions: `day4-planning-v1`, `day4-decision-v1`, `day4-governance-v1`, `day4-execution-v1`, recorded only when corresponding reviewed implementations exist. Fingerprint canonical policy/capability/reference configuration separately from these version names; version changes or parameter changes must change identity. No wall-clock or random identifiers determine semantic decisions. Current system version 0.1.0 and DecisionRecord policy_version 1.0 do not certify these future policies.

## 22. S1 expected behavior

Normal-operation intent suggests avoiding unnecessary intervention. Known mode-specific conformance, no unresolved adverse evidence, explicit permission and low-impact capability can justify ALLOW/MONITOR candidates. Current PUMP-01 semantics are missing; do not force permissive action just because S1's evaluator label is BENIGN/ALLOW. Coverage/permission gaps can legitimately require review, which future evaluation must report as burden rather than conceal.

## 23. S2 expected behavior

Observable violations of current MOTOR-02 limits, declining trust and increased distrust contribution justify greater caution. A reviewed transformation may support LIMIT; absent safe transformation, a known violated constraint may justify blocking the request within a reviewed denial envelope or requesting review. Do not require a predetermined ALLOW→LIMIT→BLOCK sequence. One out-of-range request does not prove compromise or justify ISOLATE. Transition labels and the PLC-07 name are not decision predicates.

## 24. S3 expected behavior

Authentication succeeds, behavioral semantics for write_register are insufficient, target criticality is substantial, and risk coverage is incomplete. High trust cannot establish authorization. **PROVISIONAL POLICY:** prefer REQUEST_APPROVAL for this unsupported command if the hold path is supported; otherwise no autonomous execution authorization. MONITOR is permissive and is appropriate only if a separately reviewed policy explicitly permits the uncertain operation with monitoring; current absence of semantics does not establish that permission. Do not isolate because offline labels say malicious. Both pre/post commands share this observability limitation and must be treated consistently.

## 25. S5 expected behavior

Known HIGH_OUTPUT limits make the higher requested values conforming. With the same reviewed permission envelope and capabilities, the mode change alone must not introduce restrictive intervention. Trust/risk trends support this interpretation but do not grant authority. No NORMAL-limit reuse, phase-triggered action or learned adaptation is specified. Missing independent permissions may still require approval; future false-intervention evaluation must distinguish this gap from erroneous regime-change detection.

## 26. Future Day-4F evaluation plan

**FUTURE EVALUATION REQUIREMENT:** complete inference first, then join expected_safe_action/labels. Specify eligible denominators, null/unsupported handling, per-scenario/seed results, and stage-specific proposal/authorized/executed distributions.

- Decision agreement: exact canonical-action match to expected_safe_action among evaluable records, separately at proposal and authorized-action stages; missing final actions count separately and coverage is reported. Agreement is not proof of safety.
- Unsafe action rate: executed actions violating independently specified safety constraints divided by eligible executions. Do not equate MALICIOUS label or oracle disagreement with measured physical harm. Missing safety semantics make cases unassessable, not safe.
- False intervention: restrictive/disruptive executed actions on evaluator-labeled legitimate requests divided by eligible legitimate requests; report LIMIT, BLOCK and ISOLATE separately, with regime-change strata.
- Approval rate and burden: approval-required count over valid requests; appropriate/unnecessary judgments require a reviewed offline need-for-approval reference, not current expected action alone.
- Governance veto/override rates: each status count over reviewed valid proposals; policy compliance: satisfied mandatory rules over applicable checks, with UNKNOWN and unevaluable counts exposed.
- Unnecessary disruption: disruptive action without an offline justified need, measured under a separately approved impact/reference model; do not fabricate costs from labels.
- Action distribution: counts by stage and action/status, including unexecuted/unsupported/pending cases.
- Latency: measured stage/end-to-end processing duration, with human wait separated; real timing is excluded from deterministic content fingerprints.
- Explanation coverage: fraction with required WHAT/WHY/EVIDENCE/POLICY/ALTERNATIVES/OUTCOME fields and traceable references; structural completeness is not explanation correctness.

Use frozen seeds and identical streams across comparisons. Pre-register evaluation rules and tolerances. S3 honest deferral can disagree with evaluator BLOCK while being scientifically defensible; report that disagreement, never tune inference from the label.

## 27. Cost/utility plan

Future versioned cost matrix distinguishes intended/authorized/executed action, operational impact and independently evaluated adverse outcome. False permission may be costly; unnecessary ISOLATE can also be costly. No numerical costs or universal cost ordering are fixed here. Approval burden, delays, availability and harm require separate quantities and explicit aggregation assumptions. Conduct sensitivity and held-out calibration rather than optimize on frozen test labels. Accuracy alone is insufficient.

## 28. Baselines

Future B1 rule-based threshold policy; B2 ML/risk-only policy; B3 single-agent policy; B4 static multi-agent/no adaptive feedback; B5 full TAIOS. Specify identical data, available observations, action capabilities and external evaluation rules. B1 thresholds are declared provisional benchmark settings, not production policy. No ML, adaptation or full TAIOS implementation exists now; B4/B5 may be indistinguishable until adaptation is separately designed. Do not claim comparative results yet.

## 29. Ablations

Future TAIOS-Full, NoTrust, NoGovernance, NoContext, NoMemory and Single. Record exactly which component/input is removed and how missingness/authority changes; do not substitute zero evidence. NoGovernance is an offline simulation comparison only, never permission to bypass the execution invariant in a live path. Define what “memory” means before removal: current trust history is not a generic memory agent. Some variants require future contract changes. No ablation is implemented.

## 30. Calibration requirements

**UNCALIBRATED PARAMETERS:** existing risk thresholds .20/.40/.55/.70/.85, risk/trust weights and registry criticalities retain their current values. No LOW/MEDIUM/HIGH classes or action mapping is activated. Absolute S1/S2/S3/S5 risk overlaps around .50–.53 and cannot justify risk>.5→BLOCK.

**FUTURE EVALUATION REQUIREMENTS:** action-specific evidence requirements, safe permission/denial/hold/isolation envelopes, operational transformations, criticality/impact categories, approval deadlines and escalation rules, cost matrices, tie resolution and outcome measurement need domain review and sensitivity studies. No new quantitative utility, minimum coverage percentage or trust cutoff is assigned.

## 31. Known limitations and conflicts

Current policies are prose only; authorization and capabilities are absent. Current-mode limits exist for MOTOR-02 speed, not PLC register writes or PUMP-01. Pre-command state is not a validated physical-process simulator. Denial and isolation safety are unknown without process dependencies. Risk coverage is .45 and not calibrated confidence. Audit/version checks do not bind observation content. Additional observable state requires projection review. Logical isolation, approval workflow and exactly-once execution do not yet exist.

Existing DecisionRecord's mutable arbitrary context, string candidates, weak validation and random/time defaults conflict with a future immutable deterministic decision pipeline. Document now; evolve via an explicit compatibility plan later. Original expected_safe_action values (S1/S5 ALLOW, S2/S3 post BLOCK, S4 REQUEST_APPROVAL, S6 post ISOLATE) are evaluation annotations, not policies. No reference gap is repaired by copying them. Earlier documents describe historical implementation stages; current code and later evaluation reports establish present capabilities.

## 32. Day-4B implementation requirements

1. Begin with immutable label-safe DecisionContext/CandidateAction contracts and validation only, under a separately authorized task; do not infer permission to implement every stage from this specification.
2. Preserve six actions, existing trust/risk mathematics, scenarios, thresholds and public interfaces; retain exact missing/unknown semantics.
3. Define reviewed observable context projection and pairing/reference version checks before consuming additional plant state. Keep audit separate.
4. Validate conditional candidate prerequisites, exact payloads, capability/approval declarations and deterministic identities without inventing utility values.
5. Test raw-event/label rejection, metadata invariance, source/target/version consistency, current-mode checks and unknown-essential-evidence handling.
6. Before later policy activation, replace prose with reviewed deterministic predicates, authority envelopes and conflict resolution; unresolved policies cannot default to autonomy.
7. Before later execution, specify authorization binding, approved simulation effects, changed-context invalidation, hold/denial impact and retry idempotency. No real industrial actuation.
8. Evaluate S1/S2/S3/S5 qualitative properties from observable evidence, including honest non-permission where references are missing; do not force oracle agreement.

Day 4A adds only this document. No decision/governance/execution code is implemented. Test and whitespace results are reported after actual execution. Stop after Day 4A.
