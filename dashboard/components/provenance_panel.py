def render(st, provenance, trace, result, graph):
    st.subheader("Memory, feedback, and provenance")
    retrieval = (graph or {}).get("memory_retrieval", ())
    st.write("**Retrieved memory count:**", len(retrieval))
    if retrieval:
        st.json([getattr(entry, "__dict__", str(entry)) for entry in retrieval])
    st.write("**Feedback reference:**", getattr(result, "feedback_reference", "N/A"))
    adaptation = getattr(result, "adaptation_decision", None)
    st.write("**Adaptation status:**", getattr(adaptation, "status", "N/A") if adaptation else "N/A")
    st.json(provenance or {"agentic_reasoning": "not used"})
    with st.expander("Detailed sanitized decision trace"):
        st.json(trace)
