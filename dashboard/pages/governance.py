from dashboard.components.formatters import friendly

def render_governance(st, snapshot, presentation=False):
    st.title("Governance & Human Review")
    st.caption("Recommendation → Governance → Human Review when required → Execution Authority")
    governance = snapshot.governance
    if not governance:
        st.info("No authoritative governance decision is selected.")
        return
    st.metric("Governance decision", friendly(governance.get("status")))
    st.write("Transaction ID:", governance.get("transaction_id"))
    st.write("Expires:", governance.get("expires_at"))
    st.write("Human review required:", governance.get("requires_human_review"))
    st.warning("This dashboard is read-only. Approval and rejection are not available here.")
