"""Run frozen TAIOS inference, then evaluate it across the hard label boundary."""
import argparse
import json
from pathlib import Path

from core.taios_pipeline import TAIOSPipeline
from environment.event_generator import EventGenerator
from evaluation.formal_evaluator import TAIOSEvaluator

SEEDS = (42, 123, 456, 789, 2026)
SCENARIOS = tuple(f'S{i}' for i in range(1, 7))


def run_evaluation(events_per_run=10):
    completed = []
    for scenario in SCENARIOS:
        for seed in SEEDS:
            generator = EventGenerator(seed, observable_state=True)
            experiment = generator.create_run(scenario, events_per_run)
            events = generator.generate(scenario, events_per_run, experiment)
            # Inference completes before labels are joined by TAIOSEvaluator.
            episode = TAIOSPipeline().run_episode(
                events, scenario_reference=experiment.experiment_id, seed=seed)
            completed.append((episode, events))
    return TAIOSEvaluator().evaluate_experiment(completed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', type=int, default=10)
    parser.add_argument('--output', type=Path,
                        default=Path('results/day5b-formal-evaluation.json'))
    args = parser.parse_args()
    result = run_evaluation(args.events).to_dict()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n',
        encoding='utf-8')
    print(f'Evaluated {result["overall_results"]["event_count"]} events; saved {args.output}')


if __name__ == '__main__':
    main()
