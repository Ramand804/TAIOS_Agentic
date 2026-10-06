def render_about(st, snapshot, presentation=False):
    st.title("About TAIOS")
    st.write("TAIOS is an experimental agentic decision operating layer for trust-aware, adaptive, explainable autonomous decision intelligence in Industrial IoT.")
    st.subheader("Current validation level")
    st.success("Software-Defined Industrial Testbed")
    st.subheader("Implemented")
    st.write("Software-defined process, OPC UA/MQTT boundary adapters, bounded agentic reasoning, deterministic governance, authoritative human review, capability-protected execution, independent interlock, audit, and observability.")
    st.subheader("Not validated")
    st.write("Physical plant, PLC/HIL deployment, production deployment, SIL or safety certification, IEC 62443 compliance, and hard real-time control.")
