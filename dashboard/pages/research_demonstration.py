"""Presentation page reusing the established bounded V1/V2 demo components."""
from agentic.adapter import ExecutionMode
from dashboard.components import (
    decision_panel, event_panel, explainability_panel, metrics_panel,
    provenance_panel, research_pipeline_panel,
)
from dashboard.research_demo import DEMO_SCENARIOS, runtime_event_fields, run_demo, sanitize

FAILURE_CATEGORIES = ("AUTHENTICATION_FAILED", "RATE_LIMIT_OR_QUOTA", "TIMEOUT", "CONNECTION_FAILED", "MALFORMED_PROVIDER_RESPONSE")


def _value(value):
    return getattr(value, "value", value)


def _get_attr(obj, *names, default=None):
    if obj is None:
        return default
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def _summary(result, graph):
    planning = _get_attr(result, "planning_result")
    candidates = tuple(_value(_get_attr(item, "action")) for item in _get_attr(planning, "candidates", default=()))
    proposed = _get_attr(result, "proposed_decision")
    final_action = _value(_get_attr(proposed, "selected_action"))
    provenance = (graph or {}).get("llm_provenance")
    advisory = (graph or {}).get("validated_advisory")
    selection = (graph or {}).get("selection_provenance")
    fallback = _get_attr(provenance, "fallback_reason")
    return {
        "baseline": _value(_get_attr(selection, "deterministic_v1_action", default=final_action)),
        "candidates": candidates,
        "recommendation": _value(_get_attr(advisory, "recommended_action")),
        "validation": f"Fallback: {fallback}" if fallback else _value(_get_attr(provenance, "validation_status", default="Not used")),
        "final_action": final_action,
        "authority": "Available in technical trace",
        "assurance": _value(_get_attr(_get_attr(result, "assurance_assessment"), "status", default="N/A")),
        "governance": _value(_get_attr(_get_attr(result, "governance_decision"), "status", default="N/A")),
        "execution": _value(_get_attr(_get_attr(result, "execution_result"), "execution_status", default="N/A")),
    }


def render_research_demonstration(st, snapshot, presentation=False):
    st.title("Research Demonstration")
    st.caption("Frozen V1/V2 runtime demonstration — separate from the industrial simulator")
    st.info("Agentic reasoning is advisory. Governance and the canonical execution/review path remain authoritative.")
    with st.sidebar:
        mode_label = st.selectbox("Research demonstration mode", ("Deterministic V1", "Agentic MockLLM", "Provider Failure Demonstration"))
        scenario_label = st.selectbox("Canonical research scenario", [item.label for item in DEMO_SCENARIOS])
        seed = st.number_input("Deterministic seed", min_value=0, value=42, step=1)
        failure = st.selectbox("Offline provider failure", FAILURE_CATEGORIES, disabled=mode_label != "Provider Failure Demonstration")
    mode = {"Deterministic V1": ExecutionMode.DETERMINISTIC_V1.value, "Agentic MockLLM": ExecutionMode.AGENTIC_MOCK.value, "Provider Failure Demonstration": ExecutionMode.AGENTIC_LLM.value}[mode_label]
    demo = run_demo(mode=mode, scenario_label=scenario_label, provider_failure=failure, seed=int(seed))
    result, graph = demo["result"], demo["graph"]
    summary = _summary(result, graph)
    metrics_panel.render(st, result)
    research_pipeline_panel.render(st, agentic_enabled=graph is not None)
    decision_panel.render(st, summary)
    event_panel.render(st, runtime_event_fields(demo["event"]))
    st.warning("No live provider request is available in this page. MockLLM and provider-failure modes are deterministic demonstrations.")
    provenance = (graph or {}).get("llm_provenance")
    trace = sanitize({"graph": graph or {}, "provenance": getattr(provenance, "__dict__", None)})
    explainability_panel.render(st, trace)
    provenance_panel.render(st, sanitize(getattr(provenance, "__dict__", None)), trace, result, graph)
