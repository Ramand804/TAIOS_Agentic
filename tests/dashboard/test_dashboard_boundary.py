from pathlib import Path

from dashboard.components.formatters import friendly, safe_capability_metadata
from industrial.capabilities import ExecutionCapability

ROOT = Path(__file__).parents[2]
DASHBOARD = ROOT / "dashboard"


def source():
    return "\n".join(path.read_text() for path in DASHBOARD.rglob("*.py"))


def test_dashboard_has_no_process_mutation_or_authority_registration():
    text = source()
    assert ".apply(" not in text
    assert ".register(" not in text
    assert "._issue(" not in text
    assert "._claim(" not in text


def test_dashboard_never_renders_raw_capability_token():
    cap = ExecutionCapability("cap-id", "private-token-must-not-render")
    model = safe_capability_metadata(cap)
    assert model == {"capability_id": "cap-id", "status": "Issued"}
    assert "private-token-must-not-render" not in repr(model)


def test_presentation_formatting_preserves_runtime_values():
    value = "CONTROLLED_EXECUTION"
    assert friendly(value) == "Controlled Execution"
    assert value == "CONTROLLED_EXECUTION"


def test_experiment_page_is_read_only_and_dashboard_uses_no_execution_api():
    text = source()
    assert "def execute(" not in text
    assert "def issue(" not in text
    assert "def decide(" not in text


def test_dashboard_snapshot_is_simulation_only_and_cannot_mutate_process():
    app = (DASHBOARD / "app.py").read_text()
    assert "OperatingMode.SIMULATION" in app
    assert ".apply(" not in app
    assert "set_mode(" not in app


def test_experiment_view_reads_frozen_artifacts_without_writing_results():
    text = (DASHBOARD / "adapters" / "experiment_view.py").read_text()
    assert "open()" in text and "write" not in text
    assert "results/" not in text
