"""Presentation-only formatting. These functions never alter runtime objects."""

LABELS = {
    "SIMULATION": "Simulation", "SHADOW": "Shadow", "SUPERVISED": "Supervised",
    "CONTROLLED_EXECUTION": "Controlled Execution", "REQUEST_APPROVAL": "Human Approval Required",
    "OPERATING_MODE_MISMATCH": "Execution Blocked — Operating Mode Changed",
    "STATE_VERSION_MISMATCH": "Execution Blocked — Process State Changed",
    "LEGACY_DIRECT_EXECUTION_DISABLED": "Direct Execution Blocked",
    "REVIEW_REQUIRED": "Human Review Required", "APPROVED": "Approved", "REJECTED": "Rejected",
    "UNKNOWN": "Unknown", "NOT_CONFIGURED": "Not Configured", "UNAVAILABLE": "Unavailable",
}


def friendly(value):
    if value is None:
        return "Not available"
    raw = getattr(value, "value", value)
    return LABELS.get(str(raw), str(raw).replace("_", " ").title())


def safe_capability_metadata(capability):
    """Expose identifier/status fields only; capability tokens are intentionally omitted."""
    if capability is None:
        return {"status": "Not issued"}
    return {"capability_id": getattr(capability, "authorization_id", "Unknown"), "status": "Issued"}
