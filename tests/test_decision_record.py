import pytest
from core.decision_record import DecisionRecord

def test_decision_record():
    d = DecisionRecord(event_id="EVT-1", selected_action="ALLOW")
    assert d.selected_action == "ALLOW"
    assert d.decision_id.startswith("DEC-")

def test_invalid_action():
    with pytest.raises(ValueError):
        DecisionRecord(event_id="EVT-1", selected_action="DESTROY")
