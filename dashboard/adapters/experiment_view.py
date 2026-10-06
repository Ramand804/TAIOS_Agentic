"""Read-only loaders for frozen publication artifacts."""
from pathlib import Path
import json

ROOT = Path(__file__).parents[2]
PUBLICATION = ROOT / "publication"

FIGURES = (
    ("TAIOS architecture", PUBLICATION / "figures" / "fig01_architecture.png", PUBLICATION / "captions" / "fig01_architecture.md"),
    ("Safety and autonomy", PUBLICATION / "figures" / "fig02_s7_safety_autonomy.png", PUBLICATION / "captions" / "fig02_s7_safety_autonomy.md"),
    ("Unsafe-action ablation", PUBLICATION / "figures" / "fig03_s7_unsafe_ablation.png", PUBLICATION / "captions" / "fig03_s7_unsafe_ablation.md"),
    ("Trust endpoints", PUBLICATION / "figures" / "fig04_s7_trust_endpoints.png", PUBLICATION / "captions" / "fig04_s7_trust_endpoints.md"),
    ("Component attribution", PUBLICATION / "figures" / "fig05_component_attribution.png", PUBLICATION / "captions" / "fig05_component_attribution.md"),
    ("Causal mechanism", PUBLICATION / "figures" / "fig06_s7_causal_mechanism.png", PUBLICATION / "captions" / "fig06_s7_causal_mechanism.md"),
)

TABLES = (
    ("Experimental configurations", PUBLICATION / "tables" / "table01_configurations.json"),
    ("Overall seed records", PUBLICATION / "tables" / "table02_overall_seed_records.json"),
    ("Scenario summaries", PUBLICATION / "tables" / "table03_scenario_summaries.json"),
    ("S7 causal ablation", PUBLICATION / "tables" / "table04_s7_causal_ablation.json"),
    ("S7 paired results", PUBLICATION / "tables" / "table05_s7_paired.json"),
)


def load_json(path):
    with path.open() as stream:
        return json.load(stream)
