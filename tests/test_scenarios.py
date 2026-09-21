from environment.event_generator import EventGenerator

def test_all_scenarios_generate_requested_count():
    g = EventGenerator(seed=42)
    for sid in ["S1","S2","S3","S4","S5","S6"]:
        events = g.generate(sid, 20)
        assert len(events) == 20
        assert all(e.scenario_id == sid for e in events)

def test_compromise_contains_malicious_events():
    events = EventGenerator(seed=42).generate("S2", 20)
    assert any(e.ground_truth == "MALICIOUS" for e in events)

def test_drift_remains_legitimate():
    events = EventGenerator(seed=42).generate("S5", 20)
    assert all(e.ground_truth == "BENIGN" for e in events)
    assert any(e.contextual_features.get("new_operating_regime") for e in events)
