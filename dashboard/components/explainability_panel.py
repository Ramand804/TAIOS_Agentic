def render(st, trace):
    st.subheader("Explainability")
    tabs = st.tabs(["Deterministic evidence", "Agentic rationale", "Assurance", "Governance", "Execution outcome"])
    tabs[0].json(trace.get("deterministic_assessments", {}))
    tabs[1].json(trace.get("agentic_reasoning") or {"status": "No advisory used"})
    tabs[2].json(trace.get("deterministic_assessments", {}).get("assurance", {}))
    tabs[3].json(trace.get("governance", {}))
    tabs[4].json({"execution": trace.get("execution", {}), "outcome": trace.get("outcome", {})})
