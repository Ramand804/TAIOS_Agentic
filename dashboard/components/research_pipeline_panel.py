STAGES = ("Industrial Event", "Context", "Trust", "Risk", "Drift", "Decision Assurance", "Deterministic Planner", "Agentic Reasoning", "Bounded Selection", "Governance", "Execution / Human Review", "Feedback / Memory")
def render(st, *, agentic_enabled):
    st.subheader("Decision pipeline")
    labels = [f"**{stage}**" if (stage != "Agentic Reasoning" or agentic_enabled) else stage for stage in STAGES]
    st.markdown("  →  ".join(labels))
