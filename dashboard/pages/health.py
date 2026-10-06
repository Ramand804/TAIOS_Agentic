from dashboard.components.formatters import friendly

def render_health(st, snapshot, presentation=False):
    st.title("System Health")
    for name, status in snapshot.health.items():
        st.write(f"**{name.replace('_', ' ').title()}**: {friendly(status)}")
