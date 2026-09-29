# Methodology source notes

| Subsection | Frozen sources | Verified constants / notes |
|---|---|---|
| 3.2 | `environment/event.py`, `core/runtime_inputs.py` | Runtime allowlist excludes evaluator fields. |
| 3.4 | `intelligence/operational_semantic_model.py`, `intelligence/authorization_engine.py` | Four semantic statuses. |
| 3.5 | `intelligence/trust_model.py`, `config/trust.yaml`, `config/trust_model.yaml` | weights 0.20/0.25/0.25/0.15/0.15; prior 0.80; rates 0.01/0.10/0.005. |
| 3.6 | `intelligence/threat_evidence_model.py`, `core/risk_input.py`, `config/risk.yaml` | risk weights 0.40/0.25/0.20/0.15. |
| 3.7 | `intelligence/drift_detector.py`, `adaptation/behavioral_adapter.py` | history 3; reference 3; threshold 0.30; persistence 2. |
| 3.8 | `intelligence/decision_assurance.py` | Authority restriction only; pre-planning location. |
| 3.9 | `agents/planning_agent.py`, `agents/decision_agent.py`, `agents/governance_agent.py`, `agents/execution_agent.py` | Six actions; execution requires governance artifact. |
| 3.10–3.11 | `core/taios_pipeline.py`, memory/feedback/outcome modules | Pipeline ordering verified from frozen V1. |
