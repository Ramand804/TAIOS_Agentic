def render(st, result):
    trust = result.trust_assessment.to_inference_dict() if result.trust_assessment else {}
    risk = result.risk_assessment.to_inference_dict() if result.risk_assessment else {}
    drift = result.drift_assessment.to_dict() if result.drift_assessment else {}
    assurance = result.assurance_assessment.to_dict() if result.assurance_assessment else {}
    cols = st.columns(4)
    cols[0].metric("Trust", trust.get("composite_trust", trust.get("trust_score", trust.get("score", "N/A"))))
    cols[1].metric("Risk", risk.get("risk_score", risk.get("score", "N/A")), help="Risk is danger associated with allowing or executing an action, not attack probability.")
    cols[2].metric("Drift", drift.get("status", "N/A"))
    cols[3].metric("Assurance", assurance.get("status", "N/A"))
    st.caption("Threat is an uncalibrated security signal, not attack probability.")
