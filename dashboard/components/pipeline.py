def render_pipeline(st, active_stage=None):
    stages = ["Industrial Event", "Context", "Trust / Risk / Drift", "Decision Assurance", "Agentic Advisory", "Governance", "Human Review", "Execution Capability", "Safety Interlock", "Industrial Process"]
    st.markdown(" → ".join(f"**{stage}**" if stage == active_stage else stage for stage in stages))
