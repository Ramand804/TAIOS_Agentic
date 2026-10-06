# Runtime compatibility analysis

| Stage | Status | File / boundary | Reason |
|---|---|---|---|
| Context extraction | ADAPTER_REQUIRED | `core/runtime_inputs.py:runtime_observation` | Accepts frozen `IndustrialEvent`, although it only emits runtime fields. |
| Operational semantics | DIRECTLY_COMPATIBLE | `intelligence/operational_semantic_model.py` | Consumes the derived observation mapping. |
| Authorization | DIRECTLY_COMPATIBLE | `intelligence/authorization_engine.py` | Consumes runtime observation mapping. |
| Threat/correlation | DIRECTLY_COMPATIBLE | `intelligence/*evidence*` | Consume runtime observation mapping. |
| Trust | DIRECTLY_COMPATIBLE | `agents/trust_agent.py` | Consumes runtime observation mapping. |
| Risk | DIRECTLY_COMPATIBLE | `agents/risk_agent.py` | Consumes observation plus trust/threat. |
| Drift/adaptation | DIRECTLY_COMPATIBLE | `intelligence/drift_detector.py`, `adaptation/behavioral_adapter.py` | Consume runtime observation but are stateful. |
| Decision context / authority / assurance | ADAPTER_REQUIRED | `intelligence/decision_context_builder.py` | Need a runtime observation and industrial state adapter. |
| Planner / agentic reasoning | ADAPTER_REQUIRED | `agents/planning_agent.py`, `agentic/*` | Require canonical decision context. |
| Governance / execution | BLOCKED_BY_EXPERIMENT_CONTRACT | `agents/governance_agent.py`, `agents/execution_agent.py` | Must wait for governed runtime execution binding. |
| Pipeline | BLOCKED_BY_EXPERIMENT_CONTRACT | `core/taios_pipeline.py:process_event` | Immediately calls `EventManager.validate` on frozen `IndustrialEvent`. |

## Recommended runtime entry boundary

A future `RuntimeContextAdapter` immediately before `runtime_observation`/the internal `_event_observation` boundary is the narrowest safe entry point. It must create the allowlisted runtime observation directly from `IndustrialRuntimeEvent`, without constructing an experimental event. It needs a separately governed runtime transaction path because `TAIOSPipeline.process_event` owns validation, replay, checkpoints, and stateful commits.
