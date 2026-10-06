from dashboard.components.formatters import friendly

def render_decision_intelligence(st, snapshot, presentation=False):
    st.title("Decision Intelligence")
    st.caption("Deterministic evidence is shown separately from agentic advisory reasoning.")
    st.subheader("Event context")
    st.write(snapshot.event or "No runtime event is currently selected.")
    for title, text in [("Trust assessment", "Not available in the current isolated industrial snapshot."),
                        ("Risk assessment", "Not available. Risk is not presented as attack probability."),
                        ("Drift assessment", "Not available in the current snapshot."),
                        ("Adaptation status", "Not available in the current snapshot."),
                        ("Decision assurance", "Industrial runtime uses its separate deterministic governance boundary.")]:
        st.subheader(title); st.write(text)
    st.subheader("Final deterministic decision")
    st.success(friendly(snapshot.decision.get("disposition")))
