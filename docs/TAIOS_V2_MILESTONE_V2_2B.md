# V2-2B: LangGraph orchestration with a deterministic mock

The V2-only environment is `/home/sac/Downloads/TAIOS_Day1B/.venv-v2` (Python 3.14.4) and contains LangGraph 1.2.12. No provider SDK, API key, or external model is used. The V1 environment and pipeline do not import LangGraph.

The source-derived V1 order remains: EventManager validation, runtime observation/state synchronization, operational semantics, drift, authorization, threat, correlation, trust, risk, decision context, authority, decision assurance, planning, decision, governance, execution, outcome, feedback, then behavioural adaptation. V2-2B does not reorder or replace it.

The compiled mock advisory graph is `START → agentic_advisory → END`. It is entered only after deterministic code creates sanitized input, planner candidates, and the assurance envelope. The advisory node can write only the validated proposal or exact deterministic fallback, validation/fallback state, mock provenance, workflow metadata, and visited nodes. Deterministic assessments, authority, assurance, governance, execution, feedback, and memory are read-only graph snapshots. Evaluator-only fields are rejected before the node runs.

A valid MockLLM output produces a validated advisory. Malformed, invalid, empty, timeout, and provider-error mock output retain the exact deterministic proposal with an auditable fallback reason. `REQUEST_APPROVAL` is never converted to approval. An AgenticProposal is never governance or execution authorization; V1 continues to require its canonical governance artifact.

The trace separates sanitized observable evidence, deterministic assessments, planner candidates, advisory rationale, validation, assurance, governance, and execution snapshots. Provenance records workflow version, mode, visited nodes, validation status, fallback reason, and mock provider/model/prompt/schema versions plus a deterministic response-metadata hash. It contains no secrets.

This is mock-only orchestration, not a real-LLM adapter or a claim of experimental superiority. A full component-level V2 graph must first wrap V1 stages in their source-derived order without changing V1 science. Real-provider work must not start until that integration and its representative scenario coverage are complete.
