# Day 4B — decision contracts, capabilities and policy semantics

## Purpose and scope

This milestone prepares deterministic, immutable inputs for future planning. It does not generate candidate lists, select an action, authorize a command or mutate industrial state. Both supplied task attachments were byte-identical. The Day-4A specification was read before implementation.

Inspected AUTONOMOUS_DECISION_SPEC.md; existing DecisionRecord, agents/governance/core/environment/config inventories; policies/system/risk configuration; assets, industrial state, operational limits, scenario semantics, validators, safe projection and trust/risk contracts. Existing policies are prose-only and no identity-operation authorization rules or isolation executor exist.

Added core/actions.py, core/decision_contracts.py, core/decision_context.py, intelligence/decision_context_builder.py, tests/test_decision_context.py and this document. Existing source/configuration/specification files remain unchanged. Related small contracts share modules rather than introducing one file per dataclass.

## Canonical actions

`core.actions.Action` is the authoritative enum for new decision modules: ALLOW, MONITOR, LIMIT, REQUEST_APPROVAL, BLOCK, ISOLATE. New modules import this enum rather than duplicate action strings. Frozen event labels and DecisionRecord constants remain unchanged for compatibility; a test verifies exact agreement with those constants and config/system.yaml. Enum declaration order is deterministic serialization order, not a safety ranking.

## DecisionContext and builder

```python
context = build_decision_context(
    safe_observation,
    trust_assessment,
    risk_assessment,
    industrial_state=None,
    operational_limits=None,
    policy_context=None,
    capability_context=None,
)
```

Optional arguments are keyword-only. Defaults use the existing central OperationalLimits and canonical policy file. DecisionContext holds the exact safe observation, audit-free TrustAssessment and RiskAssessment, CapabilityEnvelope, PolicyContext, optional state_version and context_version=day4b-context-v1. Source/target convenience properties expose the observation identifiers.

The observation preserves source/type, target/type, identity, event_type, operation/requested_value, source zone/protocol, authentication and target criticality; approved context includes production_state and operating_mode only. Nested observation objects are copied/frozen. Assessments retain numeric scores, evidence coverage, trust state version, risk coverage/contributions, configuration identity and model version. Audit is stripped from assessment copies before storage and excluded from serialization. No aggregate decision confidence exists.

The builder reuses build_risk_input's exact projection and Day-1 registry validation. DecisionContext compares the supplied risk source, target, operation, composite trust, distrust, target criticality, trust state version, trust evidence coverage and prior-only dimensions with the supplied observable/trust contract. It does not invoke TrustModel or RiskModel or calculate another risk score. Existing input preparation computes only the established complement for consistency checking.

Mismatch is rejected, never silently repaired. Direct context construction also performs these checks. When a caller supplies a capability envelope, it must equal the envelope derived from the current observation and chosen central limits. Supplied policy context must carry the matching observation reference.

## Operational validity and current state

OperationalValidity contains current operating_mode, a deterministic fingerprint of the operational-limit reference, optional existing LimitCheck, and an observable reason. Status is WITHIN_LIMIT, OUTSIDE_LIMIT or UNKNOWN. The nested check exposes requested_value, minimum, maximum, within_limit and the existing deviation. Validation rejects contradictory check fields or nonfinite values.

Use the observed mode from the approved safe projection; do not assume NORMAL. If IndustrialState or StateSnapshot is supplied, both projected production_state and operating_mode must match it and its version is preserved. Only these fields/version are read; raw asset health, flags and provenance are not added to the context. The state is never mutated. Missing mode gives UNKNOWN rather than fallback. No operation/mode range gives UNKNOWN. The existing central check performs the numeric calculation; no new normalization is introduced.

Diagnostics use the existing observable-state generator profile, whose mode reflects current IndustrialState. Tests separately supply a live state/snapshot, reject stale NORMAL state for HIGH_OUTPUT observations, and verify version preservation and copy safety. No raw logged state_snapshot is read by the builder.

## Capabilities versus authorization

CapabilityEnvelope fields: source_id, target_id, operation, observation_reference, operational_validity and capability_version=day4b-capabilities-v1. Its export also includes supported_actions, limit/monitor/approval/isolation capability facts, execution_implemented, external_approval_integration and deterministic reasons.

Supported means **logical representation** in these contracts, not available industrial actuation, policy admissibility or permission. All executor integration is explicitly false.

- ALLOW logically represents permission for the original request; it is not granted here.
- MONITOR logically represents permission plus added observation/audit; no persistent monitoring subsystem exists.
- BLOCK logically represents denial of this request; physical safety of denial is unknown.
- REQUEST_APPROVAL logically represents holding/review routing; no human integration or approved safe-deferral envelope exists.
- LIMIT is exposed as RANGE_ONLY when a valid current-mode range/check exists. The range is a prerequisite for later planning, not a safe transformation or executable constraint mechanism. A request of 97 exposes [20,80] and remains 97; no replacement 80 is selected.
- ISOLATE is UNKNOWN and omitted from supported actions because no isolatability/dependency/implementation reference exists. Registry type alone does not grant this capability.

An invalid current request can still have logical ALLOW capability: capability is not an admissible candidate. Future planning must apply constraints, authorization and impact requirements before generating candidates.

AuthorizationStatus defines AUTHORIZED, UNAUTHORIZED and UNKNOWN. Current PolicyContext always reports UNKNOWN, including successful authentication and known authentication failure, because there are no configured identity-operation permissions. P02's unauthenticated-control prose is not a grant/deny authorization table. No auth evaluator or permission rule is invented. AUTHORIZED/UNAUTHORIZED enum values are reserved for future explicit configured semantics.

Capability asks what can be expressed; authorization asks whether the identity/source is permitted; decision selects a proposal; governance validates safety/authority. None substitutes for another.

## Structured policies without invented predicates

PolicyDefinition is frozen: policy_id, name, description and enabled, exactly matching the supported YAML schema. Loading rejects unexpected keys, duplicate IDs and invalid types; immutable PolicyContext retains sorted definitions, observation_reference and policy_version=day4b-prose-v1. The version describes this adapter representation, not a new executable policy release.

Current P01/P02/P03 remain enabled prose. Every enabled definition has applicability UNKNOWN and executable=false; disabled policies report DISABLED. These are unresolved policy references, not claims that every policy applies. authorization_status, approval_requirement and autonomous_isolation_permission remain UNKNOWN. Source/target scoping or numeric thresholds are not inferred from English names/descriptions. A content fingerprint captures the exact policy representation; no YAML changes or scenario-specific rules were added.

## Future stage contracts

All records are frozen, with copy-safe serialization, deterministic content references and no wall-clock or random IDs. No contract is a running agent or an authenticated authorization token.

- **CandidateAction:** action, immutable payload, rationale, safety_effect, operational_impact, reversibility, requires_approval, policy_constraints, evidence_basis, unresolved_prerequisites, capability_reference, planning_policy_version. Impact/reversibility remain required qualitative descriptions because Day 4A defines no validated numeric ranking or universal LOW/HIGH severity categories. Effects are proposed, not observed. No actual candidate objects are generated by the context pipeline.
- **ProposedDecision:** selected_action, selected_candidate_reference, candidate_actions, primary_reason, evidence_summary, trust_basis, risk_basis, uncertainty, policy_basis, alternatives_considered, context_reference, decision_policy_version. A selection must match an exact candidate/reference. No selection requires an empty admissible set and no selected reference. Export includes PROPOSED/NO_ADMISSIBLE_ACTION status and the selected candidate's exact payload. No real proposal is instantiated outside synthetic contract tests.
- **GovernanceDecision:** canonical status APPROVED/VETOED/APPROVAL_REQUIRED/OVERRIDDEN, proposed/authorized action, authorized_payload, policy_checks, violations, reason, context/proposal references, authorization_reference and governance_policy_version. Approvals require nonempty all-PASS checks and no violations. APPROVED preserves the proposed action; OVERRIDDEN differs. Veto/pending must have null action/payload/authorization reference. These checks validate a record; they do not evaluate policy or confer real authority.
- **ExecutionResult:** requested/authorized action, canonical execution status, before/after state references, reason, governance_reference and execution_policy_version. Success or recorded denial requires an authorized action and governance reference; DENIED requires BLOCK. Pending approval cannot claim original action execution. No state mutation or executor exists.

Free-text rationale and payload fields in future-stage fixtures are supplied by trusted callers, not sanitized natural-language inference inputs. Future builders must use approved structured evidence and payload schemas. References are deterministic hashes, not signatures or proofs of safety.

## Observation binding and audit

A context reference hashes safe observation, audit-free assessments, state/reference versions, policy facts and capability data. CapabilityEnvelope and PolicyContext bind to a fingerprint of the exact safe observation. Changing requested value/mode/policy/reference changes the resulting context identity. These hashes bind the newly created artifact; they do not prove how older assessments were produced.

If both trust and risk contain audit records, disagreement is rejected outside inference. Matching changed audit IDs produce identical contexts. A missing audit record does not manufacture a match; no audit is retained in inference output.

Verified: entity/source, target, operation, criticality, trust value/version/coverage agreement; observed state/mode agreement when supplied; envelope request/reference consistency. **Not verifiable with existing contracts:** same-source old assessments for a different requested value when their exposed fields/versions still agree. Neither assessment contains an observation fingerprint. A test explicitly demonstrates that changing requested value can produce a new context around the same assessments; this is a documented caller-owned freshness limitation, not a proof of binding. No existing trust/risk contract was broadened to hide this gap.

## DecisionRecord compatibility

The legacy record's action vocabulary, trust/risk values and explanation/status concepts remain compatible at a descriptive level. Missing structured candidates, full coverage/configuration references, distinct proposal/authorization/execution payloads and immutable typed context prevent direct equivalence. Its mutable context and default random/time IDs conflict with deterministic inference; selected_action cannot express no admissible action. It is not used as a DecisionContext or authorization grant. No migration was made. A later explicit versioned adapter/migration must preserve standalone compatibility and separate audit/evaluation data from inference.

## Actual seed-42 diagnostics

Ten events per observable-state scenario; fresh trust/risk agents. Nine requested contexts were built without candidate generation or action selection. Repeated context builds were identical. Full records are in ignored results/day4b-contexts.json.

All rows have authorization UNKNOWN, risk coverage .45, threat/anomaly unavailable, and P01/P02/P03 enabled with UNKNOWN applicability and no executable predicates. Logical base capabilities B are ALLOW, MONITOR, REQUEST_APPROVAL, BLOCK. B+LIMIT adds only a range reference. Isolation is UNKNOWN everywhere. Identity/device evidence is POSITIVE throughout; HISTORY/CONTEXT direct evidence is INSUFFICIENT throughout.

| Scenario/event | Source → target | Operation/value | Mode | Validity/range | Behavior evidence | Capabilities | Trust | Risk |
|---|---|---|---|---|---|---|---:|---:|
| S1/6 | SERVICE-03 → PUMP-01 | set_speed 63 | NORMAL | UNKNOWN | INSUFFICIENT | B | 0.800950781 | 0.492805122 |
| S2/5 | PLC-07 → MOTOR-02 | set_speed 48 | NORMAL | WITHIN_LIMIT [20,80] | POSITIVE | B+LIMIT | 0.801823096 | 0.514542725 |
| S2/6 | PLC-07 → MOTOR-02 | set_speed 97 | NORMAL | OUTSIDE_LIMIT [20,80] | NEGATIVE | B+LIMIT | 0.798281429 | 0.516510317 |
| S2/7 | PLC-07 → MOTOR-02 | set_speed 97 | NORMAL | OUTSIDE_LIMIT [20,80] | NEGATIVE | B+LIMIT | 0.794688645 | 0.518506308 |
| S2/8 | PLC-07 → MOTOR-02 | set_speed 94 | NORMAL | OUTSIDE_LIMIT [20,80] | NEGATIVE | B+LIMIT | 0.791468016 | 0.520295547 |
| S3/6 | HMI-02 → PLC-03 | write_register 999 | NORMAL | UNKNOWN | INSUFFICIENT | B | 0.801451697 | 0.532526835 |
| S5/5 | PLC-01 → MOTOR-02 | set_speed 53 | NORMAL | WITHIN_LIMIT [20,80] | POSITIVE | B+LIMIT | 0.801823096 | 0.514542725 |
| S5/6 | PLC-01 → MOTOR-02 | set_speed 85 | HIGH_OUTPUT | WITHIN_LIMIT [60,95] | POSITIVE | B+LIMIT | 0.802201697 | 0.514332391 |
| S5/7 | PLC-01 → MOTOR-02 | set_speed 85 | HIGH_OUTPUT | WITHIN_LIMIT [60,95] | POSITIVE | B+LIMIT | 0.802582523 | 0.514120821 |

S1 PUMP-01 has no speed range, so operational validity is UNKNOWN. S2 event 5 is within range; events 6/7 deviation is .283333333333 and event 8 .233333333333 under NORMAL. S3 authentication succeeds but write_register has no permission/range semantics: authorization and validity remain UNKNOWN, behavior evidence insufficient. S5 events 6/7 use [60,95] HIGH_OUTPUT, with zero deviation; stale NORMAL state is rejected. These are observable facts, not action recommendations.

## Verification and limitations

440 tests passed, 0 failed, including all prior 411 tests. New tests cover canonical enum compatibility, immutable contracts/export copies, deterministic contexts/references, logical capabilities, unsupported semantics, current-mode ranges, state preservation, source/target/operation/version consistency, authorization remaining UNKNOWN, prose-policy validation, audit isolation, label-mutation invariance and contradictory future-stage records. Syntax checks cover all five new Python files; whitespace checks cover every added file.

There are no real configured authorization grants to exercise; no affirmative/negative permission is fabricated. No claim is made that ALLOW/BLOCK/deferral is physically safe, that a limit range is a safe command transformation, or that isolation is available. Policy applicability remains unresolved. Future contract fixtures are not security boundaries; immutable objects do not prove the truth of caller-supplied statements.

## Exact prerequisites for Day 4C

A separately authorized PlanningAgent may consume DecisionContext and enumerate conditional CandidateAction records. It must distinguish logical representation from executable/admissible action, honor UNKNOWN authorization and unresolved policies, retain evidence/coverage, use current-mode ranges without automatically clamping, and require a reviewed transform for a concrete LIMIT payload. It must not infer isolation or permission from labels/authentication, resolve prose into invented predicates, or select the final action. Full observation binding, permission/denial/hold envelopes and executor semantics remain explicit future requirements.

No action was selected in the Day-4B pipeline. No Planning/Decision/Governance/Execution Agent, detector, adaptation, LLM or calibration was implemented. Trust/risk code, scenarios, limits, existing configuration and DecisionRecord remain unchanged. Stop after Day 4B.
