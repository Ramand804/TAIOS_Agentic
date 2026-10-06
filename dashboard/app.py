"""TAIOS research and observability dashboard. It is deliberately read-only."""
import streamlit as st

from dashboard.adapters.runtime_view import from_runtime
from dashboard.demo_scenarios import SCENARIOS
from dashboard.pages import (
    render_about, render_agentic_reasoning, render_audit, render_controlled_execution,
    render_decision_intelligence, render_experiments, render_governance, render_health,
    render_industrial_process, render_overview,
)
from industrial.audit import AppendOnlyAuditLog
from industrial.runtime.governance import IndustrialGovernance, OperatingMode
from industrial.trusted_runtime import build_trusted_runtime
from datetime import datetime, timezone

PAGES = {
    "Overview": render_overview,
    "Research Demonstration": None,
    "Industrial Process": render_industrial_process,
    "Decision Intelligence": render_decision_intelligence,
    "Agentic Reasoning": render_agentic_reasoning,
    "Governance & Human Review": render_governance,
    "Controlled Execution": render_controlled_execution,
    "Audit & Explainability": render_audit,
    "Experiments & Results": render_experiments,
    "System Health": render_health,
    "About TAIOS": render_about,
}


def _snapshot():
    """Construct a SIMULATION-only display snapshot without evaluating a command."""
    now = lambda: datetime.now(timezone.utc)
    runtime = build_trusted_runtime(IndustrialGovernance(OperatingMode.SIMULATION, now), now)
    return from_runtime(runtime, audit_entries=AppendOnlyAuditLog().entries())


def main():
    st.set_page_config(page_title="TAIOS Industrial Testbed", page_icon="⚙️", layout="wide")
    st.sidebar.title("TAIOS")
    st.sidebar.caption("Research & observability interface")
    page = st.sidebar.radio("Navigate", list(PAGES))
    st.sidebar.selectbox("Demonstration scenario", SCENARIOS, disabled=True, help="Scenario selection is intentionally disabled in this read-only release.")
    presentation = st.sidebar.toggle("Presentation View", value=False)
    if page == "Research Demonstration":
        try:
            from dashboard.pages.research_demonstration import render_research_demonstration
            render_research_demonstration(st, _snapshot(), presentation)
        except ModuleNotFoundError as error:
            st.error(f"Research demonstration dependency is unavailable: {error.name}")
            st.code(".venv-dashboard/bin/pip install -r requirements-dashboard.txt")
    else:
        PAGES[page](st, _snapshot(), presentation)


if __name__ == "__main__":
    main()
