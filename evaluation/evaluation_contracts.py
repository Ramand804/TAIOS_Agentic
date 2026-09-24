"""Immutable post-inference evaluation records."""
from dataclasses import dataclass

from core.decision_contracts import Record, freeze, export
from core.experiment import fingerprint


@dataclass(frozen=True, kw_only=True)
class EventEvaluation(Record):
    source_pipeline_fingerprint: str
    scenario_id: str
    seed: int
    sequence_number: int
    ground_truth: str
    expected_action: str
    proposed_action: str
    governance_status: str
    authorized_action: str | None
    execution_status: str
    exact_agreement: bool
    unsafe_action: bool
    false_intervention: bool
    evaluator_details: object

    def __post_init__(self):
        object.__setattr__(self, 'evaluator_details', freeze(self.evaluator_details))


@dataclass(frozen=True, kw_only=True)
class ScenarioEvaluation(Record):
    scenario_id: str
    seed: int
    source_episode_fingerprint: str
    events: tuple[EventEvaluation, ...]
    metrics: object
    temporal_analysis: object

    def __post_init__(self):
        object.__setattr__(self, 'events', tuple(self.events))
        object.__setattr__(self, 'metrics', freeze(self.metrics))
        object.__setattr__(self, 'temporal_analysis', freeze(self.temporal_analysis))


@dataclass(frozen=True, kw_only=True)
class ExperimentEvaluation(Record):
    evaluation_version: str
    configuration_fingerprint: str
    metric_definitions: object
    source_episode_fingerprints: tuple[str, ...]
    scenario_runs: tuple[ScenarioEvaluation, ...]
    overall_results: object
    per_seed_results: object
    per_scenario_results: object
    ground_truth_stratification: object
    action_confusion_matrix: object
    governance_confusion_matrix: object
    temporal_analyses: object
    utility_framework: object
    limitations: tuple[str, ...]

    def __post_init__(self):
        object.__setattr__(self, 'source_episode_fingerprints',
                           tuple(self.source_episode_fingerprints))
        object.__setattr__(self, 'scenario_runs', tuple(self.scenario_runs))
        for name in ('metric_definitions', 'overall_results', 'per_seed_results',
                     'per_scenario_results', 'ground_truth_stratification',
                     'action_confusion_matrix', 'governance_confusion_matrix',
                     'temporal_analyses', 'utility_framework'):
            object.__setattr__(self, name, freeze(getattr(self, name)))
        object.__setattr__(self, 'limitations', tuple(self.limitations))

    @property
    def evaluation_fingerprint(self):
        return fingerprint({
            'evaluation_version': self.evaluation_version,
            'configuration_fingerprint': self.configuration_fingerprint,
            'source_episode_fingerprints': self.source_episode_fingerprints,
            'overall_results': export(self.overall_results),
            'per_seed_results': export(self.per_seed_results),
            'per_scenario_results': export(self.per_scenario_results),
            'ground_truth_stratification': export(self.ground_truth_stratification),
            'action_confusion_matrix': export(self.action_confusion_matrix),
        })

    def to_dict(self):
        result = super().to_dict()
        result['evaluation_fingerprint'] = self.evaluation_fingerprint
        return result
