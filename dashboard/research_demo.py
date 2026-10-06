"""Canonical-event demo adapters. This module never alters scientific policies."""
from dataclasses import dataclass
from agentic.adapter import ExecutionMode
from agentic.provider import ProviderFailure
from agentic.runtime import V2Runtime
from agentic.mock_llm import MockLLM
from core.taios_pipeline import TAIOSPipeline
from environment.event_generator import EventGenerator
from environment.industrial_environment import IndustrialState

EVALUATOR_ONLY_FIELDS = frozenset({
    "ground_truth", "expected_safe_action", "scenario_id", "experiment_id",
    "scenario_version", "phase", "phase_label", "causal_annotation",
    "causal_annotations", "provenance", "compromise_marker", "test_oracle",
})

@dataclass(frozen=True)
class DemoScenario:
    label: str
    scenario_id: str
    event_index: int
    description: str

DEMO_SCENARIOS = (
    DemoScenario("Normal authorized operation", "S1", 0, "Canonical S1 runtime event."),
    DemoScenario("Invalid/adverse command", "S3", 9, "Canonical S3 runtime event."),
    DemoScenario("Suspicious behavioral change", "S2", 9, "Canonical S2 runtime event."),
    DemoScenario("Legitimate operating-regime change", "S8", 9, "Canonical S8 runtime event."),
    DemoScenario("Human-review-required case", "S4", 0, "Canonical S4 runtime event."),
)

class DemoFailureProvider:
    """Offline typed provider-failure source; it never contacts a provider."""
    def __init__(self, category: str):
        self.category = category
    def reason(self, request):
        raise ProviderFailure(self.category)

def sanitize(value):
    """Remove evaluator-only information before any UI presentation."""
    if isinstance(value, dict):
        return {str(k): sanitize(v) for k, v in value.items() if str(k) not in EVALUATOR_ONLY_FIELDS}
    if isinstance(value, (tuple, list)):
        return [sanitize(item) for item in value]
    if hasattr(value, "value"):
        return value.value
    return value

def runtime_event_fields(event):
    """Explicit allow-list of runtime fields, never event.to_dict()."""
    names = ("event_id", "sequence_number", "source_id", "source_type", "target_id", "target_type",
             "identity_id", "event_type", "operation", "requested_value", "network_zone", "protocol",
             "authentication_status", "asset_criticality", "timestamp", "contextual_features")
    return sanitize({name: getattr(event, name, None) for name in names})

def _event_for(spec: DemoScenario, *, seed=42):
    generator = EventGenerator(seed=seed, observable_state=True)
    run = generator.create_run(spec.scenario_id, 10)
    events = generator.generate(spec.scenario_id, 10, run)
    return events[min(spec.event_index, len(events) - 1)]

def run_demo(*, mode: str, scenario_label: str, provider_failure: str = "TIMEOUT", seed: int = 42):
    """Run one isolated canonical pipeline invocation for UI presentation."""
    spec = next(item for item in DEMO_SCENARIOS if item.label == scenario_label)
    event = _event_for(spec, seed=seed)
    pipeline = TAIOSPipeline()
    execution_mode = ExecutionMode(mode)
    if execution_mode is ExecutionMode.DETERMINISTIC_V1:
        runtime = V2Runtime(pipeline, mode=execution_mode)
    elif execution_mode is ExecutionMode.AGENTIC_MOCK:
        runtime = V2Runtime(pipeline, mode=execution_mode, reasoner=MockLLM())
    else:
        runtime = V2Runtime(pipeline, mode=ExecutionMode.AGENTIC_LLM,
                            reasoner=DemoFailureProvider(provider_failure))
    result = runtime.process_event(event, IndustrialState())
    return {"spec": spec, "event": event, "result": result,
            "graph": getattr(runtime, "last_graph_output", None), "mode": execution_mode.value}
