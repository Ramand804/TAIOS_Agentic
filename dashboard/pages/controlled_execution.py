from dashboard.components.formatters import friendly

def render_controlled_execution(st, snapshot, presentation=False):
    st.title("Controlled Execution")
    st.caption("Governance → Human Review → Capability → State/Mode Validation → Gateway → Interlock → Process")
    st.warning("Authority valid and process action safe are separate checks.")
    st.metric("Capability", snapshot.execution["status"])
    st.metric("Safety interlock", snapshot.execution["interlock"])
    st.write("No raw capability token is displayed or accepted by the dashboard.")
    with st.expander("Technical details"):
        st.write("The dashboard has no execution, capability issuance, or process-write operation.")
