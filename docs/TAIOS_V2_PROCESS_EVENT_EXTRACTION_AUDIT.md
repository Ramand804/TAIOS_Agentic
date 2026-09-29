# `process_event` extraction audit

Audited source: `core/taios_pipeline.py:149-289`.

| Stage / lines | Existing mechanism | Mutable state / checkpoint | Downstream binding / failure |
|---|---|---|---|
| validation 160 | `EventManager.validate` | none | invalid input enters common rollback failure path |
| observation/sync 162-163 | `runtime_observation`, `_synchronize_regime` | cloned `IndustrialState` only | observation drives all later assessments |
| semantics 165-166 | `OperationalSemanticModel.assess` | none | drift, context, assurance |
| drift 167-176 | `DriftDetector.assess` | drift detector checkpoint 156 | assurance and adaptation |
| authorization 178-179 | `AuthorizationEngine.assess` | none | threat/context/assurance |
| threat/correlation 180-185 | evidence models | checkpoints 152-153 | risk, assurance |
| trust 186-192 | `TrustAgent.assess` | trust + entity-count checkpoints 149-150 | risk/context |
| risk/context/authority 193-205 | V1 agents/builders | none | assurance/planning |
| assurance/final context 206-219 | `DecisionAssuranceGate` | none | bounds planning |
| planning/decision/governance 220-225 | V1 agents | none | canonical decision chain |
| execution 226-229 | `ExecutionAgent.execute` | execution checkpoint 151 | outcome/state-after |
| outcome/experience 230-242 | observer/builder/memory | memory checkpoint 154 | feedback |
| feedback/adaptation 243-250 | feedback/adaptation services | checkpoints 155,157 | final result |
| result/commit 251-276 | `PipelineResult`, `_processed_events` | processed-event cache is post-success commit | returns canonical result |

Transactional mutable stores are: TrustAgent, `_entity_observations`, ExecutionAgent idempotency state, threat and correlation models, episodic memory, feedback memory, DriftDetector, BehavioralAdapter/reference store. All are checkpointed before validation. Industrial state is cloned and only returned through execution; the caller owns later episode state propagation. `_processed_events` is post-success mutable. Authorization, semantics, risk, authority, assurance, planning, governance, outcome construction, and result construction are read-only for pipeline-owned scientific state.

On `AttributeError`, `KeyError`, `TypeError`, or `ValueError`, lines 280-289 restore every listed checkpoint, then raise `PipelineProcessingError` with the current stage. A `PipelineProcessingError` is re-raised. Expected governance rejection and pending approval are successful transaction outcomes, not failures. Commit is effective only after result creation and `_processed_events[event_key]` assignment at line 275; prior stores mutate during processing but are rolled back if a handled exception occurs after them.

Retry safety: validation/semantics/authorization/risk/context/authority/assurance/planning/decision/governance are retry-safe only with identical immutable inputs. Drift, threat, correlation, trust, execution, memory, feedback, and adaptation are not retry-safe outside a transaction because they may mutate state. Existing same-event replay is handled by `_processed_events` before checkpoints (lines 110-148); it uses ExecutionAgent idempotency behavior rather than re-running assessments. LangGraph persistent checkpointing must not restore scientific stores; TAIOS checkpoints remain authoritative.

## Pre-extraction characterization matrix

The V2 oracle records, after every event, canonical result fingerprint, checkpoint-equivalent transaction-state fingerprint, drift/assurance status, decision action, and execution status. It covers deterministic S2 and S5 sequences; S2 reaches `UNEXPLAINED_PERSISTENT_DRIFT`, while S5 reaches `KNOWN_REGIME_CHANGE`. Both produce adaptation decisions under existing policy. Autonomous execution and pending approval are committed valid outcomes; replay is `ALREADY_EXECUTED` through the existing execution idempotency mechanism.

Directly tested rollback points are risk (after drift/threat/correlation/trust mutation) and outcome observation (after execution, before experience/feedback/adaptation). Both restore all audited checkpoint state and leave no processed-event record. Governance rejection is not currently reachable from the canonical fixture path without corrupting a binding; it is therefore not manufactured for characterization. Execution is controlled in-memory `IndustrialState` simulation. Its software checkpoint is rollback-protected, but this does not claim physical action reversal in a future deployment.

Field classification: runtime decision input is the allowlisted `runtime_observation` plus synchronized industrial state. `scenario_id`, experiment identity, sequence number, and provenance are integrity/provenance inputs used by event validation, not decision evidence. `ground_truth` and `expected_safe_action` are evaluator-only; changing them leaves both result and checkpoint-state fingerprints unchanged. They must remain absent from future graph/LLM contracts.

## Final pre-extraction oracle

| Outcome | Reachable public path | Transaction success | Experience / feedback | processed-event / replay |
|---|---|---|---|---|
| `SUCCEEDED` | S2 conforming command | yes | recorded | committed; replay is `ALREADY_EXECUTED` |
| `PENDING_APPROVAL` | S2 outside-limit request | yes | recorded | committed; non-actuating result |
| semantic `OUTSIDE_LIMIT` | S2 event six | yes; this is assessment, not schema failure | recorded | committed |
| authorization `UNAUTHORIZED` | not reachable from canonical frozen scenarios; S3 is `UNKNOWN` | n/a | n/a | n/a |
| governance `VETOED` | not naturally reachable from canonical pipeline: planner/decision bindings satisfy governance; unit tests cover malformed/foreign proposals | n/a | n/a | n/a |
| system exception | injected risk/outcome/feedback/adaptation/result construction | no; rollback | none persists | not committed; event can later process normally |

Feedback and adaptation failure injection both restore the complete checkpoint-equivalent state. A direct final-result constructor injection also restores state and proves the observed commit ordering: result construction precedes `_processed_events` mutation. The normal execution implementation is in-memory `IndustrialState` simulation with an idempotency map; rollback restores that software map only and does not establish physical reversal semantics.

## Private helper extraction result

`TAIOSPipeline` now exposes protected, non-public lifecycle boundaries for validation/observation, semantics, drift, authorization, threat, correlation, trust, risk, authority/assurance/context, planning, baseline decision, governance, execution, outcome, experience, feedback, adaptation, result construction, transaction checkpoints, rollback, and processed-event commit. The public `process_event()` still creates checkpoints before validation, owns the V1 try/except boundary and `_failure` construction, and invokes those helpers in its original order. V1 has no imports from V2.

The V2 sequential runner and full MockLLM LangGraph workflow call these same helpers. The graph retains transaction ownership in a non-persistent `TAIOSTransactionContext`; it does not use LangGraph checkpoint restoration. A completed graph stage cannot be applied twice within one transaction. The event replay branch is intentionally delegated to the public V1 replay contract, preventing duplicate trust, drift, correlation, memory, feedback, adaptation, and execution-idempotency mutations.
