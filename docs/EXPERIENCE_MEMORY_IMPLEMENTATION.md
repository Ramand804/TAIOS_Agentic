# Milestone 7A: Outcome Observation and Episodic Experience Memory

## Purpose and boundary

Milestone 7A records what the simulator exposed after TAIOS executed or deferred an action. The causal chain is now:

`state/context → inference → decision → governance → execution → observed outcome → experience record → episode memory`

This infrastructure records experience only. Memory does not feed trust, threat, correlation, risk, authorization, authority, semantics, planning, decision, governance, or execution. No experience is assigned correctness, reward, utility, safety, or attack labels.

## Execution, outcome, and ground truth

`ExecutionResult` records what the executor attempted and its technical result. `ObservedOutcome` independently records the post-execution facts visible in `IndustrialState`: execution status, state versions, mutation flag, target value, applied value, operating mode, and production state. Ground truth and expected action remain post-inference evaluator annotations and never enter either record.

The simulation does not expose physical temperature, damage, safety incidents, production loss, energy use, or external human decisions. The observer does not invent them.

## Observable outcome contract

`ObservedOutcome` is immutable and binds the event and execution references. Its factual statuses are:

- `EXECUTED_MUTATION_OBSERVED`
- `EXECUTED_NOOP_OBSERVED`
- `PENDING_EXTERNAL_APPROVAL`
- `EXECUTION_REJECTED`
- `UNSUPPORTED_EXECUTION`
- `STALE_EXECUTION_PREVENTED`
- `DUPLICATE_EXECUTION_PREVENTED`
- `EXECUTION_DENIED`
- `OUTCOME_PARTIALLY_OBSERVED`

The observer verifies the execution scope, request value, state versions, state fingerprints, resulting state, and mutation flag before producing an outcome. Its stable version is `milestone7a-outcome-observer-v1`.

For `PENDING_APPROVAL`, no mutation is observed and `external_approval_decision` plus `future_execution_effect` remain unresolved. No later human response is fabricated.

A successful repeated-value request is `EXECUTED_NOOP_OBSERVED`: execution technically succeeded, the resulting value is observable, and equal before/after state versions establish that no mutation was needed. It is not treated as failure.

## Experience contract

`ExperienceRecord` is an immutable reference chain with version `milestone7a-experience-v1`. It binds:

- Observable event, source, target, operation, and requested value
- Semantic, threat, correlation, trust, risk, authorization, and authority assessments
- Planning result, proposal, governance decision, execution result, and observed outcome
- State-before and state-after references
- Trust before and after
- Risk score and available-weight coverage

Trust and risk references use their inference-only views, so audit correlation metadata cannot alter an experience reference. Correlation is retained for traceability and does not trigger adaptation.

## Episodic memory

`EpisodicMemory` is deterministic, in-process, and scoped to one episode. It offers:

- `append(experience)`
- `get_by_event(event_reference)`
- `get_by_source(source_id)`
- `get_by_target(target_id)`
- `get_by_operation(operation)`
- `recent(limit)`
- Immutable `records`, `count`, and `memory_fingerprint` views

Event references identify observable content and can repeat when separate events have identical observations. `get_by_event` therefore returns an ordered tuple. Record uniqueness uses the full experience reference, which includes the complete causal chain. Memory fingerprinting hashes the ordered experience references and memory version, so order matters without wall-clock data.

The pipeline resets memory at each `run_episode`, preventing transfer between scenarios or seeds. Exact committed-event replay produces a factual `DUPLICATE_EXECUTION_PREVENTED` observation but reuses the canonical experience reference and does not append another record.

## Transaction and rollback

Experience is committed only after execution and outcome observation complete. Before processing, the pipeline checkpoints trust, threat history, correlation history, execution ledger, entity counters, and experience memory. Failure during outcome observation, experience construction, memory append, or later result validation restores these stateful components. The cloned plant transition is not exposed as committed on failure.

## Frozen diagnostic

Across S1–S6, seeds 42, 123, 456, 789, and 2026:

- Experiences: 300
- Observed successful mutations: 88
- Observed successful no-ops: 5
- Pending external approvals: 207
- Ordered 30-run memory fingerprint: `408033836adcdf0a3f5d275e1063659404b49ed830f46733ad6b86069e75323c`
- Retrieval checks: 30/30 runs passed for event, source, target, operation, and recent causal order

### Scenario observations

- **S1:** 50 experiences: 14 mutations, 1 successful no-op, and 35 pending approvals. These are technical outcomes, not judgments of normality.
- **S2:** 50 experiences: 25 mutations followed by 25 pending approvals across five seeds. For seed 42, events 1–5 mutate the MOTOR-02 state; events 6–10 preserve state version 5 and record unresolved external approval.
- **S3:** 50 pending experiences. No review correctness or malicious intent is inferred.
- **S4:** 50 pending experiences. Conflicting evidence is retained through assessment references without outcome interpretation.
- **S5:** 50 experiences: 46 mutations and 4 successful no-ops. Seed-42 events 1–5 remain NORMAL, event 6 observes HIGH_OUTPUT and a mutation, event 7 observes a successful repeated-value no-op, and events 8–10 observe later mutations.
- **S6:** 50 experiences: 3 mutations and 47 pending approvals. Each record binds both local threat and correlation assessments. Signal-zero correlation uncertainty remains uncertainty and is not reinterpreted as an attack.

## Leakage, traceability, and regression

Outcome observation accepts only the runtime observation, execution result, and before/after state. Experience construction accepts only completed inference/action artifacts. Scenario ID, ground truth, expected action, attack phase, provenance causal labels, formal metrics, and simulator-only contextual annotations are absent.

The complete reference chain answers what was requested, what TAIOS knew, what it proposed, what governance decided, what execution did, and what observable software-state effect followed. It does not answer whether the decision was correct.

The unchanged 6C risk diagnostic and 6D correlation diagnostic remain byte-identical. Proposal, governance, execution, trust, risk, and correlation behavior remain unchanged. Formal action metrics remain unchanged.

## Limitations and readiness

Memory is volatile and episode-local. There is no external approval callback, durable store, distributed transaction, semantic search, vector database, reward, policy update, drift detector, baseline, ablation, ML model, LLM, or LangGraph. Physical-process consequences remain unobserved.

The deterministic outcome and experience layer is ready for a separately authorized 7B interpretation milestone. Learning and adaptation remain deferred.
