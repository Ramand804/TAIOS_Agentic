# TAIOS V2 title capability matrix

| Title term | Required capability | V2 implementation | Test | Status | Limitation |
|---|---|---|---|---|---|
| Agentic AI | bounded recommendation selection | `agentic/bounded_selector.py` | `test_v2_bounded_selector.py` | IMPLEMENTED | Mock-only until a separately approved provider integration |
| Agentic Decision Operating Layer | typed orchestration and services | `agentic/langgraph_workflow.py` | `test_v2_full_lifecycle_graph.py` | IMPLEMENTED | no persistent graph checkpointing |
| Trust-Aware | deterministic trust consumed | V1 context plus sanitized input | V1/V2 tests | IMPLEMENTED | no V2 effectiveness evaluation |
| Adaptive | governed behavioral adaptation | source-derived V1 graph node | graph sequence parity tests | IMPLEMENTED | V1 adaptation science remains authoritative |
| Explainable | selection provenance and decision trace | `agentic/decision_trace.py` | full graph trace test | IMPLEMENTED | advisory rationale remains non-authoritative |
| Autonomous Decision Intelligence | governed action selection | selector + V1 governance/execution | full graph safety tests | IMPLEMENTED | no effectiveness claim |
| Industrial IoT | typed events/assets/context | V1 environment/core | V1 tests | IMPLEMENTED | controlled software environment |

## Real-provider phase evidence

| Title term | V2 evidence | Status | Limitation |
|---|---|---|---|
| Agentic AI | OpenAI structured-output adapter, strict validator, bounded selector | INTEGRATION_TESTED | Live test skipped: no credential |
| Operating System / Agentic Decision Operating Layer | Transactional LangGraph lifecycle, replay guard, observability trace | INTEGRATION_TESTED | No persistent checkpointing by design |
| Trust-Aware | Sanitized trust summary included in agentic input; V2 harness records trust trajectory | INTEGRATION_TESTED | No claim that trust improves quality |
| Adaptive | V1 governed adaptation remains in graph sequence | INTEGRATION_TESTED | No online model learning |
| Explainable | Structured trace separates facts, assessments, baseline, advice, validation, selection, governance, execution, feedback, memory | INTEGRATION_TESTED | LLM rationale is advisory only |
| Autonomous Decision Intelligence | Assurance/authority-bounded recommendation, governance-exclusive execution, explicit review records | INTEGRATION_TESTED | No real-world deployment claim |
| Industrial IoT | Existing typed assets/events/state retained; provider receives sanitized industrial evidence only | INTEGRATION_TESTED | Controlled software environment |

Live OpenAI validation status: `NOT_RUN_NO_CREDENTIAL`. The structural provider test uses an injected local client and verifies strict JSON-schema request construction, non-secret metadata capture, and validator/bounded-selection enforcement. The generated V2 harness artifact is `analysis/v2/v2_agentic_validation.json`; its `AGENTIC_LLM` rows record the intentional `MODEL_UNAVAILABLE` fallback rather than fabricated live results.
