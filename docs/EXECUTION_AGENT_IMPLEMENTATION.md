# Day 4F — deterministic ExecutionAgent

## Responsibility and API

`ExecutionAgent.execute(decision_context, planning_result, proposed_decision,
governance_decision, industrial_state)` is the sole Day-4 component that can
apply an authorized action to simulated plant state. Planning generates
candidates, Decision selects one, Governance authorizes the exact proposal,
and Execution checks that authorization and applies only its exact payload.

The executor does not select or substitute actions, rerun upstream inference,
use trust/risk thresholds, read evaluation labels, invent LIMIT values, or
simulate a human approval. Its stable policy version is
`day4f-execution-v1`.

## Result contract and statuses

The backwards-compatible `ExecutionResult` now optionally records a
deterministic `execution_id`, target, operation, requested/applied values,
before/after state versions, mutation and replay flags, governance
authorization reference, and a resulting `IndustrialState` snapshot.

The existing status vocabulary remains available. Day 4F uses:

* `SUCCEEDED` for an exact supported transition, including an authorized
  transition whose requested value already equals current state.
* `PENDING_APPROVAL` for `APPROVAL_REQUIRED`; it never mutates state.
* `REJECTED` for a veto, invalid binding, incomplete payload, or invalid
  authorization.
* `STALE_STATE` when current state/version no longer matches approval context.
* `ALREADY_EXECUTED` for a successful authorization replay.
* `UNSUPPORTED` when an otherwise valid authorization has no implemented
  industrial transition semantics.

## Hard gate and artifact binding

Execution requires an APPROVED GovernanceDecision, a non-null exact action and
payload, all governance checks PASS, no violations, and the supported
governance policy version. The executor verifies the context-to-plan,
plan-to-proposal, and proposal-to-governance references; the exact planner
candidate set; selected candidate reference; authorized action and payload;
and the deterministic governance authorization reference. Validation occurs
before any transition.

The authorization reference is a deterministic SHA-256 fingerprint over the
context, plan, proposal, action, exact payload, governance checks, and
governance policy version. The execution reference additionally binds the
governance artifact and execution policy. Neither uses wall-clock time or a
random identifier.

## State validation, transactionality, and idempotency

Execution compares `DecisionContext.state_version` with the current
`IndustrialState.state_version`, then compares the approved production state
and operating mode with current state. A changed mode, version, or production
state returns `STALE_STATE` and leaves state unchanged. Action-specific
preconditions are then checked against the exact bound payload and operational
range.

Transitions use the existing `IndustrialState.update_asset_state` API. The
executor validates first, clones the supplied state, and applies the transition
to that clone. It never mutates the caller's state or any upstream artifact.
Before/after fingerprints and versions make a no-op distinguishable from a
version-changing mutation.

A process-local ledger stores only successful deterministic execution IDs.
Replaying the same authorization returns `ALREADY_EXECUTED` with the first
resulting state and performs no second transition. Persistence and distributed
coordination of this ledger belong to the next integration milestone.

## Action semantics

**ALLOW.** Only the bound `set_speed` operation currently has a state
transition. The exact original requested value is applied through
`update_asset_state`. The executor rechecks target, operation, state version,
production state, and current operating mode. S5 HIGH_OUTPUT therefore uses
the approved `[60,95]` context rather than reconstructing NORMAL `[20,80]`.

**REQUEST_APPROVAL.** Governance returns APPROVAL_REQUIRED and execution
returns PENDING_APPROVAL. No human response or state change is inferred.

**LIMIT.** Current real LIMIT candidates contain a null replacement and remain
approval-required, so they cannot execute. A fully specified, governance-
approved synthetic LIMIT can apply exactly its explicit replacement when it is
inside the exact approved range. Execution never clamps or chooses a value.

**MONITOR.** Logical monitoring has no external monitoring executor or plant
mutation. An approved MONITOR therefore returns UNSUPPORTED without mutation.

**BLOCK and ISOLATE.** No physical denial or isolation semantics exist.
Injected or invalid approvals fail binding; no plant behavior is fabricated.

Unknown operations also return a non-mutating unsupported or rejected outcome,
depending on whether the artifact itself is valid.

## Deterministic replay behavior

The seed-42 diagnostic expects S1/6, S2/6-8, and S3/6 to remain
PENDING_APPROVAL without mutation. S2/5 executes set_speed 48 under NORMAL.
S5/5 executes 53 under NORMAL, while S5/6-7 execute 85 under HIGH_OUTPUT.

`evaluation/evaluate_execution_agent.py` reports those rows, all S1-S6 events
for seeds 42/123/456/789/2026, execution distributions, mutation counts, and
separate tampered-authorization, stale-approval, duplicate-execution, and
complete-LIMIT probes. These are structural behavior measurements, not claims
of attack-detection or security effectiveness.

Tests cover construction, exact ALLOW/LIMIT execution, request and veto gates,
MONITOR/BLOCK/ISOLATE boundaries, payload/action/target/operation/reference
tampering, stale version and changed-mode TOCTOU, idempotency, deterministic
fresh-state replay, upstream immutability, S5 HIGH_OUTPUT behavior, label
leakage invariance, and audit isolation across S1-S6.

## Limitations and next integration milestone

The executor models state only; it does not command real devices. State
versioning is process-local, and the ledger is in memory. There is no external
approval workflow, monitoring platform, durable transaction store, distributed
lock, BLOCK safety envelope, or ISOLATE implementation. Only `set_speed` has a
defined transition.

The next end-to-end integration milestone should make the Orchestrator carry a
single IndustrialState through context construction, governance, and execution;
persist the complete artifact chain and ExecutionResult; restore a durable
single-use authorization ledger; atomically compare-and-apply state versions;
and expose explicit approval, monitoring, and device-adapter interfaces before
adding corresponding action semantics. Upstream trust, risk, authorization,
authority, planning, decision, governance, scenarios, and policy behavior are
unchanged by Day 4F.
