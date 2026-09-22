import ast
from dataclasses import replace
from pathlib import Path

import pytest

from core.event_manager import EventManager
from core.runtime_inputs import runtime_observation
from environment.event_generator import EventGenerator
from environment.provenance import ProvenanceIntegrityError


@pytest.mark.parametrize('scenario', [f'S{i}' for i in range(1, 7)])
def test_runtime_view_excludes_labels_and_synthetic_hints(scenario):
    event = EventGenerator().generate(scenario, 10)[-1]
    before = runtime_observation(event)
    event.ground_truth = 'DIFFERENT'
    event.expected_safe_action = 'DIFFERENT'
    event.provenance = None
    event.scenario_id = 'DIFFERENT'
    event.contextual_features.update({'compromise_phase': True, 'causal_tags': ['attack'],
        'anomaly_score': 999, 'future_label': {'ground_truth': 'MALICIOUS'}})
    assert runtime_observation(event) == before
    assert set(before['contextual_features']) <= {'production_state', 'operating_mode'}
    assert not {'ground_truth', 'expected_safe_action', 'provenance', 'scenario_id',
                'sequence_number', 'experiment_id', 'event_id'} & set(before)


@pytest.mark.parametrize('kind', ['duplicate', 'missing', 'no_provenance', 'timestamp', 'event_id'])
def test_experiment_batch_rejects_corruption(kind):
    generator = EventGenerator()
    run = generator.create_run('S2', 10)
    events = generator.generate('S2', 10, run)
    if kind == 'duplicate': events[-1] = events[0]
    elif kind == 'missing': events.pop()
    elif kind == 'no_provenance':
        events[0] = replace(events[0], experiment_id=None, provenance=None)
    else: setattr(events[0], kind, 'corrupted')
    with pytest.raises(ProvenanceIntegrityError):
        EventManager().validate(events, experiment=run)


def test_mutated_experiment_configuration_rejected():
    generator = EventGenerator()
    run = generator.create_run('S2', 10)
    run.configuration['assets'][0]['criticality'] = 0.1
    with pytest.raises(ValueError, match='configuration changed'):
        generator.generate('S2', 10, run)


def test_all_project_python_files_parse():
    root = Path(__file__).resolve().parents[1]
    for folder in ('core','environment','agents','intelligence','adaptation','memory',
                   'governance','explainability','evaluation','baselines','experiments'):
        for path in (root / folder).glob('*.py'):
            ast.parse(path.read_text(), filename=str(path))
