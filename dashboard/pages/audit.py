def render_audit(st, snapshot, presentation=False):
    st.title("Audit & Explainability")
    st.caption("Chronological evidence. Agentic rationale is not deterministic causal proof.")
    if not snapshot.audit:
        st.info("No audit entries are loaded for this view.")
        return
    for entry in snapshot.audit:
        with st.expander(f"{entry.get('sequence', '?')} · {entry.get('category', 'event')}"):
            st.write(entry)
