def render_agentic_reasoning(st, snapshot, presentation=False):
    st.title("Agentic Reasoning")
    st.warning("Agentic output is advisory and cannot create execution authority.")
    st.subheader("Deterministic evidence")
    st.write("No live provider is connected to this industrial dashboard.")
    st.subheader("Agentic / LLM advisory reasoning")
    st.write("Provider status: Not configured")
    st.write("Candidate actions, recommendation, rationale, memory, and feedback are available only when produced by the frozen V2 runtime evidence path.")
    with st.expander("Why no recommendation is shown"):
        st.write("The dashboard does not invent LLM output or promote it to an authority input.")
