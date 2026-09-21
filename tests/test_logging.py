import json
from core.logger import JsonlLogger
from environment.event_generator import EventGenerator

def test_jsonl_logging(tmp_path):
    p = tmp_path / "events.jsonl"
    logger = JsonlLogger(p)
    e = EventGenerator(seed=42).generate("S1", 1)[0]
    logger.write(e)
    row = json.loads(p.read_text().strip())
    assert row["event_id"] == e.event_id
