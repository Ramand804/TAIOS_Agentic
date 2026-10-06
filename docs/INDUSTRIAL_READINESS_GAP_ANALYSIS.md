# Industrial readiness gap analysis

## Scope and boundary

This is an architecture audit of frozen TAIOS V2 (`taios-agentic-v2`,
`41c897bf23987a21cf3c1d8646b2b8aa090bac5e`). It records integration needs; it
makes no claim of industrial deployment, safety certification, or protocol
security. The frozen scientific components remain the source of truth.

## Verified reusable contracts

| Contract | Existing implementation | Status | Integration implication |
|---|---|---|---|
| Canonical event | `environment.event.IndustrialEvent`; validation via `core.event_manager.EventManager` and `environment.validators` | READY | Protocol adapters must construct this model and pass validation. Runtime reasoning is restricted by `core.runtime_inputs.runtime_observation`. |
| Dynamic state | `environment.industrial_environment.IndustrialState` | PARTIAL | Immutable/versioned simulation state exists, but it has no source timestamp, quality, freshness, or external-process binding. |
| Pipeline | `core.taios_pipeline.TAIOSPipeline.process_event` | READY | Existing transaction/rollback, replay behavior, governance and execution contracts must be called rather than reproduced. |
| Result trace | `core.pipeline_result.PipelineResult` / `EpisodeResult` | READY | Carries assessments, planning, proposal, governance, execution, outcome, feedback, adaptation and state references. |
| Decision/governance/execution | `core.decision_contracts`, `agents.governance_agent`, `agents.execution_agent` | READY | Governance and execution bindings are canonical; no adapter may treat an advisory or human choice as execution authority. |
| Agentic boundary | `agentic.runtime`, `agentic.langgraph_workflow`, `agentic.validator`, `agentic.bounded_selector` | READY | Deterministic V1, MockLLM, and typed provider fallback already preserve bounded selection. |
| Human review | `agentic.human_review` | PARTIAL | Typed in-memory lifecycle exists; no durable operator queue or external identity integration exists. |
| Memory/feedback | `memory`, `adaptation`, `intelligence.feedback_interpreter` | PARTIAL | In-memory scientific lifecycle exists; no operational persistence is available. |
| Explainability/provenance | `agentic.decision_trace`, `explainability.decision_trace` | PARTIAL | Structured traces exist; no durable, tamper-evident industrial audit store exists. |
| Deterministic experiments | `core.experiment`, `environment.event_generator`, `core.orchestrator` | READY | Suitable as a research baseline, not an industrial communication gateway. |

## Runtime versus evaluator-only information

`runtime_observation()` explicitly allow-lists source/target/identity, operation,
value, network/protocol, authentication, criticality, and approved production/
operating-mode context. Labels such as `ground_truth`, `expected_safe_action`,
scenario/provenance phases, causal tags, and experimental identities must remain
outside industrial runtime reasoning and AgenticInput.

## Readiness matrix

| Capability | Status | Evidence / industrial gap |
|---|---|---|
| Frozen TAIOS decision intelligence | READY | Canonical deterministic pipeline and V2 bounded agentic workflow are present. |
| Event integrity | READY | Asset and provenance validation exist. |
| Process simulator | MISSING | Existing `IndustrialState` is a research state model, not a manufacturing-cell simulator. |
| OPC UA adapter/server/client | MISSING | No OPC UA dependency or implementation exists. |
| MQTT adapter | MISSING | No MQTT dependency or implementation exists. |
| REST adapter | OUT_OF_SCOPE | No present requirement for a concrete REST actuator integration; provide an interface only if needed. |
| Industrial identity/certificates | MISSING | Static simulated identities exist; no certificate/IAM adapter or trust-list management exists. |
| Protocol authentication/TLS | MISSING | No external protocol sessions are implemented. |
| State freshness and quality | MISSING | `IndustrialState` versions exist but no wall-clock source age/quality contract exists. |
| Industrial execution gateway | MISSING | Existing ExecutionAgent models research execution; a separate authorization-bound process gateway is required. |
| Independent process interlock | MISSING | Existing operational limits inform semantics but are not a physical/process interlock. |
| Operating modes | MISSING | No SIMULATION/SHADOW/SUPERVISED/CONTROLLED_EXECUTION deployment envelope exists. |
| Replay/idempotency | PARTIAL | Pipeline replay logic exists; external command identity and write idempotency do not. |
| Persistence | MISSING | JSONL experiment logging exists; no operational event/decision/review/execution repository exists. |
| Auditability | PARTIAL | Immutable references/traces exist; durable operational audit, correlation IDs and retention controls are absent. |
| Health/metrics | MISSING | No component health, queue, protocol, persistence or gateway health surface exists. |
| Retry/reconnect | MISSING | No OPC UA/MQTT lifecycle exists. |
| Failure-safe integration | PARTIAL | Agentic/provider failure falls back deterministically; protocol, stale-state, persistence, review-timeout and process-write failure behavior is absent. |
| Dashboard | PARTIAL | A separate `taios-demo-ui` branch contains a demonstration dashboard; it is not an industrial backend dashboard and is not merged here. |
| Deployment packaging | MISSING | No industrial service deployment topology, local stack or least-privilege configuration exists. |
| Certification/compliance | OUT_OF_SCOPE | No certification, IEC 62443 compliance, or physical validation evidence exists. |

## Industrial gaps requiring isolated extensions

- **INDUSTRIAL_GAP: external command binding.** Pipeline governance authorizes a
  canonical proposal, but an integration gateway must bind trace ID, target,
  operation, value, expiry, state freshness, and idempotency before a process
  write.
- **INDUSTRIAL_GAP: independent process safety.** Research operational semantics
  cannot substitute for a process interlock. A deterministic testbed interlock
  must reject out-of-range, emergency, invalid-transition and stale-state writes.
- **INDUSTRIAL_GAP: durable operations.** Research memory and logging are not a
  persistent human-review, execution, or audit system.
- **INDUSTRIAL_GAP: protocol security.** OPC UA certificates, security policies,
  MQTT credentials/TLS, and network segmentation are not implemented.
- **INDUSTRIAL_GAP: deployment evidence.** Software simulation cannot establish
  hardware-in-the-loop operation, physical-plant validation, certification, or
  production readiness.

## Proposed extension boundary

New code belongs under `industrial/` and must adapt to `IndustrialEvent`,
`IndustrialState`, `TAIOSPipeline`, `V2Runtime`, and `PipelineResult`. It must
not change scientific policy code. The default operating mode must be
`SIMULATION`; external writes are prohibited unless a later execution gateway,
interlock, and controlled testbed mode jointly permit them.

## Revised Milestone 4 resolution

The frozen experimental `IndustrialEvent` requires evaluator labels and V1 registry references. The isolated `IndustrialRuntimeEvent` and industrial asset registry therefore preserve deployment-time runtime/evaluator separation without modifying those frozen contracts.

## Milestone 4.5 coupling finding

The V1 semantic and authorization components are fused to V1 concrete registries, limits, and capability construction. A safe industrial profile requires a separately designed runtime policy-provider core; substituting testbed values into frozen V1 mechanisms would either alter V1 behavior or misrepresent testbed policy.
