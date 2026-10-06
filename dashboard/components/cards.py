def status_card(st, label, value, detail=None):
    st.metric(label, value)
    if detail:
        st.caption(detail)
