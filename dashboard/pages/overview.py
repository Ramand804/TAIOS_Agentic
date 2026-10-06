from dashboard.components.cards import status_card
from dashboard.components.formatters import friendly
from dashboard.components.pipeline import render_pipeline

def render_overview(st, snapshot, presentation=False):
    st.title("TAIOS")
    st.subheader("Trust-Aware Agentic Industrial Operating System")
    st.caption("Software-Defined Industrial Decision Intelligence Testbed")
    st.info("TAIOS separates intelligent reasoning from execution authority. Agentic recommendations cannot directly modify industrial process state.")
    columns = st.columns(4)
    values = [("Operating Mode", friendly(snapshot.operating_mode)), ("Process Status", "Simulated"),
              ("Current Risk", "Not available"), ("Trust Level", "Not available"),
              ("Drift Status", "Not available"), ("Decision", friendly(snapshot.decision.get("disposition"))),
              ("Governance", friendly(snapshot.governance.get("status"))), ("Execution", snapshot.execution["status"])]
    for index, (label, value) in enumerate(values):
        with columns[index % 4]: status_card(st, label, value)
    st.subheader("Decision journey")
    render_pipeline(st, "Governance" if snapshot.governance else "Industrial Event")
    if not presentation:
        with st.expander("Technical details"):
            st.write({"operating_mode": snapshot.operating_mode, "state_version": snapshot.process["state_version"]})
