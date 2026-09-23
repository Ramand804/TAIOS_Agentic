# Day 4C.5 — authorization and permission foundation

## Purpose and scope

Authentication establishes whether the presented identity authenticated; authorization establishes permission to request a particular operation; trust describes observed reliability. These remain separate. AUTHORIZED here is a simulation permission fact under an explicit policy, not physical safety, execution authority, governance approval, or a guarantee that credentials are uncompromised.

Inspected environment/assets.py, identities.py, event.py, scenarios.py and every EventGenerator branch; config/policies.yaml and system.yaml; core/decision_context.py, intelligence/decision_context_builder.py, agents/planning_agent.py; AUTONOMOUS_DECISION_SPEC.md, DECISION_CONTEXT_IMPLEMENTATION.md and PLANNING_AGENT_IMPLEMENTATION.md. Also inspected the runtime projection and existing immutable serialization conventions. No prior implementation file was changed.

## Complete generator request inventory

This is structural inspection of all possible identity/source/target/operation combinations, not merely a sampled seed. Values, phase labels and intended actions do not establish permission.

| Generator path | Identity | Source | Target | Operation |
|---|---|---|---|---|
| Routine helper (S1 and initial S6) | Any of all five registered identities | Any PLC-01/03/04/07, HMI-02, SERVICE-03 | MOTOR-02 or PUMP-01 | set_speed |
| S2 | operator-12 | PLC-07 | MOTOR-02 | set_speed |
| S3 | operator-01 | HMI-02 | PLC-03 | write_register |
| S4 | engineer-03 | PLC-03 | MOTOR-02 | set_speed |
| S5 | operator-01 | PLC-01 | MOTOR-02 | set_speed |
| Later S6 | user-17 | HMI-02, PLC-04 or SERVICE-03 | PLC-03 | write_register |

Routine generation chooses source, target and identity independently. Its 60 possible ID combinations do not prove topology or delegated service rights. The other speed paths are subsets of those 60; four register-write combinations add to 64 possible ID tuples overall. The registered identity roles are operator (operator-01, operator-12, user-17), engineer (engineer-03), service (service-account-03). PLC is the available controller asset type; actuator is the available controlled-equipment type. Neither registry supplies explicit wiring, tenant scope or register permissions.

## Explicit policy assumptions and rationale

Configuration: config/permissions.yaml, version **day4c5-permissions-v1**. No timestamps or scenario selectors. Two exact-match rules are implemented:

* PERM-PLC-OPERATOR-SPEED: operator + PLC + actuator + set_speed → AUTHORIZED. Assumes registered operators can request process speed changes through controllers in this single simulated environment.
* PERM-PLC-ENGINEER-SPEED: engineer + PLC + actuator + set_speed → AUTHORIZED. Assumes registered engineers share this narrow process-control permission; it does not grant register programming or safety overrides.

These are newly declared simulation permissions supported by the repository's operator/engineer, controller and actuator concepts. They were not pre-existing security facts recovered from the registries. Their deployment validity requires industrial review. No permission is inferred from benign labels, requested values or the scenario's design description. There is deliberately no service, HMI, write_register, wildcard, trust-threshold or risk-threshold grant. Service-to-pump generation does not establish an identity delegation or process-service relationship. Unknown service/HMI permissions remain visible rather than being filled in from routine labels.

Both grants generalize across all four registered PLC IDs and both actuator IDs. The deliberate simulation scope is type-based: no topology is modeled. A real installation must replace or narrow these assumptions with explicit equipment/identity scopes. Tests exercise each grant on different existing IDs; no frozen registry is altered.

## Contracts and API

PermissionRule is frozen: rule_id, subject_role, source_type, target_type, operation, authorization, policy_version, rationale. Selectors are exact conjunctive matches; wildcard syntax is rejected. Authorization is an explicit grant or denial, never UNKNOWN. No optional mode/value constraints are implemented because none are justified by this permission policy.

PermissionPolicy is frozen: rules and policy_version. Rules are sorted by unique rule_id; versions and exact YAML fields are validated. Its deterministic reference hashes the complete configuration, so altered rules/rationales change identity even within a version. Unknown versions are rejected until explicitly supported.

AuthorizationAssessment is frozen: identity_id, source_id, target_id, operation, status, matched_rule_ids, reasons, authorization_policy_version, permission_policy_reference, request_reference. Collections are immutable tuples and export produces independent lists. There are no trust/risk scores, labels, sequence numbers, timestamps or random IDs.

API: `AuthorizationEngine(policy=None).assess(safe_observation)`. Default policy loads module-relative YAML; callers may supply an immutable PermissionPolicy. The engine snapshots authoritative asset/identity registries, accepts only the exact runtime_observation schema, and resolves roles/types from registries. Caller-supplied role fields, raw events and enriched context are rejected. Unknown identity/source/target returns UNKNOWN; inconsistent source type/zone/protocol or target type returns UNKNOWN, never a grant. Existing EventManager retains responsibility for complete event integrity, including target criticality. No permission conclusion uses criticality or the requested value.

The request_reference hashes permission-relevant request facts and resolved registry records. Value/mode changes do not change permission; full payload/context binding is deliberately deferred. This reference is not a cryptographic credential or an execution token. Registry authenticity and presented identity/source binding remain simulation assumptions.

## Resolution and authentication

1. Match exact role, registered source type, registered target type and operation when registry metadata is consistent. Retain all matching IDs and rationales in canonical order.
2. Explicit authentication failure returns UNAUTHORIZED, even if a grant matches or references are unknown. This is a failed prerequisite for exercising permission, consistent with P02's prohibition on directly allowing unauthenticated control. It does not revoke the underlying role grant. The event's explicit authentication boolean is used; the identity registry's default authenticated=True does not override a failed request.
3. With successful authentication, unknown/inconsistent references or no matching rule return UNKNOWN. Success alone never grants permission.
4. Any matching explicit denial overrides grants and returns UNAUTHORIZED, with all matching rules preserved and an EXPLICIT_DENY_PRECEDENCE reason. This conservative simulation rule prevents a general grant from bypassing an explicit prohibition, consistent with the frozen specification's prohibition precedence. There is no silent conflict resolution. Current shipped rules contain no denials; tests supply a denial to exercise conflicts.
5. Otherwise matching grants return AUTHORIZED.

No randomness, current time, action selection, risk computation or operational-limit validation occurs. Modes NORMAL/HIGH_OUTPUT and in-range/out-of-range values are not permission selectors.

## Scenario outcomes

S1/6 SERVICE-03 → PUMP-01 set_speed remains UNKNOWN: independent random generation supplies no service delegation. Other S1 PLC requests by operator/engineer identities can be AUTHORIZED; other role/source combinations remain UNKNOWN.

S2 PLC-07/operator-12 → MOTOR-02 set_speed is AUTHORIZED both before and after compromise. Entire assessments remain identical across its differing values. A compromised entity may retain permission while trust decreases and values violate operational limits.

S3 HMI-02/operator-01 → PLC-03 write_register remains UNKNOWN both before and after credential compromise. Successful authentication and evaluator labels do not fill absent register permissions.

S4 PLC-03/engineer-03 → MOTOR-02 set_speed is AUTHORIZED. This says nothing about validity of 84 or unresolved risk/policy concerns.

S5 PLC-01/operator-01 → MOTOR-02 set_speed remains AUTHORIZED in NORMAL and HIGH_OUTPUT. Process-limit changes remain the responsibility of existing operational validity.

S6 initial routine requests use the same general rules; all later write_register requests remain UNKNOWN. No coordinated-attack information enters the engine.

## Observed coverage

Coverage is semantic policy coverage, not predictive accuracy. Diagnostics use 10 events per run, observable-state generation, S1–S6 and seeds 42, 123, 456, 789, 2026: 30 runs / 300 events. All generated requests authenticate successfully; hence no observed UNAUTHORIZED events with the shipped grant-only rules. Failed-authentication and explicit-denial outcomes are covered by tests.

Five-seed event counts (AUTHORIZED / UNAUTHORIZED / UNKNOWN):

| Scenario | AUTHORIZED | UNAUTHORIZED | UNKNOWN |
|---|---:|---:|---:|
| S1 | 25 (50%) | 0 (0%) | 25 (50%) |
| S2 | 50 (100%) | 0 (0%) | 0 (0%) |
| S3 | 0 (0%) | 0 (0%) | 50 (100%) |
| S4 | 50 (100%) | 0 (0%) | 0 (0%) |
| S5 | 50 (100%) | 0 (0%) | 0 (0%) |
| S6 | 6 (12%) | 0 (0%) | 44 (88%) |

Overall: **181 AUTHORIZED (60.333%), 0 UNAUTHORIZED (0%), 119 UNKNOWN (39.667%)**.

| Source type | Target type | Operation | AUTHORIZED | UNAUTHORIZED | UNKNOWN |
|---|---|---|---:|---:|---:|
| HMI | PLC | write_register | 0 (0.000%) | 0 (0.000%) | 65 (100.000%) |
| HMI | actuator | set_speed | 0 (0.000%) | 0 (0.000%) | 14 (100.000%) |
| PLC | PLC | write_register | 0 (0.000%) | 0 (0.000%) | 10 (100.000%) |
| PLC | actuator | set_speed | 181 (96.791%) | 0 (0.000%) | 6 (3.209%) |
| service | PLC | write_register | 0 (0.000%) | 0 (0.000%) | 10 (100.000%) |
| service | actuator | set_speed | 0 (0.000%) | 0 (0.000%) | 14 (100.000%) |

Seed-42 unique semantic request patterns (IDs and values collapsed by role/type/operation; repeats across scenarios retained):

| Scenario | Identity role | Source type | Target type | Operation | Status | Rule |
|---|---|---|---|---|---|---|
| S1 | engineer | PLC | actuator | set_speed | AUTHORIZED | PERM-PLC-ENGINEER-SPEED |
| S1 | engineer | service | actuator | set_speed | UNKNOWN | NONE |
| S1 | operator | HMI | actuator | set_speed | UNKNOWN | NONE |
| S1 | operator | PLC | actuator | set_speed | AUTHORIZED | PERM-PLC-OPERATOR-SPEED |
| S1 | operator | service | actuator | set_speed | UNKNOWN | NONE |
| S2 | operator | PLC | actuator | set_speed | AUTHORIZED | PERM-PLC-OPERATOR-SPEED |
| S3 | operator | HMI | PLC | write_register | UNKNOWN | NONE |
| S4 | engineer | PLC | actuator | set_speed | AUTHORIZED | PERM-PLC-ENGINEER-SPEED |
| S5 | operator | PLC | actuator | set_speed | AUTHORIZED | PERM-PLC-OPERATOR-SPEED |
| S6 | operator | HMI | PLC | write_register | UNKNOWN | NONE |
| S6 | operator | PLC | PLC | write_register | UNKNOWN | NONE |
| S6 | operator | PLC | actuator | set_speed | AUTHORIZED | PERM-PLC-OPERATOR-SPEED |
| S6 | operator | service | PLC | write_register | UNKNOWN | NONE |
| S6 | operator | service | actuator | set_speed | UNKNOWN | NONE |

Seed-42 unique-pattern AUTHORIZED/UNAUTHORIZED/UNKNOWN counts and proportions: S1 2/0/3 (40%/0%/60%); S2 1/0/0 (100%/0%/0%); S3 0/0/1 (0%/0%/100%); S4 1/0/0 (100%/0%/0%); S5 1/0/0 (100%/0%/0%); S6 1/0/4 (20%/0%/80%). These denominators differ from event-frequency counts. Full per-seed counts are retained in the diagnostic JSON.

## Verification and leakage boundary

478 tests passed, 0 failed (all previous 453 plus 25 new cases). New cases cover immutable contracts/export copies, deterministic assessment, both grants generalized across IDs, unknown operations/identities/assets/types/roles, metadata mismatch, authentication separation, explicit-denial conflicts and input-order invariance, missing rules, S1/S2/S3/S5 semantics, exact schema rejection, version/configuration validation and repeatable coverage.

Across all S1–S6 generated events, mutations to labels, expected action, scenario, provenance, sequence, transitions, causal tags and synthetic scores leave the complete assessment unchanged after safe projection. Direct enriched inputs are rejected. Numeric requested values and current mode are kept outside permission predicates and its reference; their changes remain observable to other stages. The engine does not import trust/risk models or operational limits.

The diagnostic was executed twice using `.venv/bin/python -m evaluation.evaluate_authorization`. Output files results/day4c5-authorization-a.json and results/day4c5-authorization-b.json are byte-identical, verified by cmp. SHA-256 of each: `e6882a55ce1ccd124ed179a6a7bc452b5c54c1c76bc1e68a0e346705b257f4d2`. Results files are ignored generated artifacts; the reusable diagnostic is tracked as source. Syntax checks and whitespace checks cover all added files.

## Limitations and subsequent integration plan

Permission is an explicit assumed simulation policy, not inferred truth about an installation. No wiring, process topology, per-register meaning, role delegation, source impersonation defenses, revocation lifecycle, permission expiry or external credential validation exists. The grant covers requesting a speed operation, not its physical consequences. No service/HMI/write-register permissions were invented. Five short seeds are a bounded coverage sample, not exhaustive frequency estimates. The generator inventory above separately records all structural combinations.

A subsequent reviewed step can add AuthorizationAssessment as a distinct DecisionContext component while preserving the existing prose PolicyContext. The builder should recompute/validate it against the current safe request, expected policy reference and current registry snapshot, reject stale/substituted scope, and bind the complete observation/value/mode into the resulting context reference. DecisionContext.authorization_status can then expose the assessment's status in place of the current hardcoded UNKNOWN. Increment the affected context version and update tests deliberately; do not mutate trust/risk assessments or interpret authentication as a grant. Permission references alone do not bind command values or authorize execution.

No integration is performed now. Existing DecisionContext continues reporting UNKNOWN and PlanningAgent retains exactly its existing behavior. Future planning can resolve the permission prerequisite for operator/engineer PLC speed requests, but authorization alone must not introduce ALLOW/MONITOR: operational validity, policy clearance, reviewed safety envelopes and execution/governance prerequisites remain independently necessary. The service-to-pump and register-write gaps remain unresolved.

Added six files: core/authorization.py, intelligence/authorization_engine.py, config/permissions.yaml, evaluation/evaluate_authorization.py, tests/test_authorization.py and this document. Existing files modified: none. No existing-code bug was discovered or repaired; missing authorization semantics were the scoped architectural gap. No DecisionAgent, GovernanceAgent, ExecutionAgent, detector, adaptation or LLM integration was added. Trust/risk code, scenarios, planner and frozen contracts are unchanged. Stop after Day 4C.5.
