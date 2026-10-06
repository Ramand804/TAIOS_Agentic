def render(st, event_fields):
    st.subheader("Industrial event")
    st.caption("Sanitized runtime fields supplied to the TAIOS pipeline.")
    st.json(event_fields)
