from pathlib import Path
import json
from environment.event_generator import EventGenerator
from core.logger import JsonlLogger
from core.event_manager import EventManager
from core.experiment import DEFAULT_SIMULATION_START, event_stream_fingerprint


class Orchestrator:
    def __init__(self, seed=42, log_dir="logs",
                 simulation_start_time=DEFAULT_SIMULATION_START, event_interval_seconds=1.0):
        self.event_manager = EventManager()
        self.generator = EventGenerator(seed=seed)
        self.log_dir = Path(log_dir)
        self.simulation_start_time = simulation_start_time
        self.event_interval_seconds = event_interval_seconds
        self.experiment = None
        self.fingerprint = None
        self.event_logger = None

    def run_scenario(self, scenario_id, n=100):
        experiment = self.generator.create_run(
            scenario_id, n, self.simulation_start_time, self.event_interval_seconds)
        events = self.event_manager.validate(self.generator.generate(scenario_id, n, experiment))
        stream_fingerprint = event_stream_fingerprint(events)
        run_dir = self.log_dir / experiment.experiment_id
        logger = JsonlLogger(run_dir / "events.jsonl")
        logger.write_all(events)
        metadata = experiment.to_dict()
        metadata["event_stream_fingerprint"] = stream_fingerprint
        (run_dir / "experiment.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.experiment, self.fingerprint = experiment, stream_fingerprint
        self.event_logger = logger
        return events
