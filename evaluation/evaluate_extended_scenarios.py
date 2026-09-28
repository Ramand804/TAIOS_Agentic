"""Milestone-8C frozen-policy evaluation of S7--S9 long deterministic streams."""
import argparse
import json
import math
from dataclasses import asdict
from collections import Counter
from pathlib import Path

from core.experiment import event_stream_fingerprint, fingerprint
from core.experimental_configuration import ExperimentalConfiguration
from core.taios_pipeline import TAIOSPipeline
from environment.event_generator import EventGenerator
from environment.scenarios import get_scenario_evaluation_metadata
from evaluation.baseline_framework import CONFIGURATION_SPECS, create_pipeline
from evaluation.formal_evaluator import TAIOSEvaluator

SCENARIOS = ('S7', 'S8', 'S9')
SEEDS = (42, 123, 456, 789, 2026)
METRICS = ('exact_action_agreement', 'unsafe_action_rate', 'false_intervention_rate',
           'proposal_review_burden', 'autonomous_execution_rate')


def _summary(values):
    values = list(values)
    mean = sum(values) / len(values)
    sd = math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1)) if len(values) > 1 else 0.0
    return {'mean': mean, 'sample_sd': sd,
            'exploratory_95_ci': [mean - 1.96 * sd / math.sqrt(len(values)),
                                  mean + 1.96 * sd / math.sqrt(len(values))]}


def _pipeline_fingerprints():
    pipeline = TAIOSPipeline()
    return {
        'trust': fingerprint(asdict(pipeline.trust_agent._model_config)),
        'risk': pipeline.risk_agent._config.fingerprint,
        'threat': pipeline.threat_evidence_model.configuration_fingerprint,
        'correlation': pipeline.correlation_evidence_model.configuration_fingerprint,
        'drift': pipeline.drift_detector.configuration_fingerprint,
        'adaptation': pipeline.behavioral_adapter.configuration_fingerprint,
        'assurance': pipeline.assurance_gate.configuration_fingerprint,
        'rule_baseline': CONFIGURATION_SPECS[ExperimentalConfiguration.RULE_BASED].configuration_fingerprint,
        'no_trust': fingerprint({'version': 'milestone8a-no-trust-v1', 'fixed_value': 0.80}),
    }


def _row(result, event, expected):
    return {
        'event_position': result.sequence_number, 'phase_evaluator_only': event.provenance.phase,
        'requested_value': result.observable_input['requested_value'],
        'authentication': result.observable_input['authentication_status'],
        'authorization': result.authorization_assessment.status.value,
        'semantic_status': result.operational_semantic_assessment.semantic_status.value,
        'operational_validity': result.operational_semantic_assessment.operational_validity,
        'trust_before': result.trust_assessment.previous_composite_trust,
        'trust_after': result.trust_assessment.composite_trust,
        'trust_delta': result.trust_assessment.trust_delta,
        'threat_status': result.threat_assessment.status.value,
        'risk': result.risk_assessment.risk_score, 'risk_coverage': result.risk_assessment.coverage,
        'drift_status': result.drift_assessment.status.value,
        'drift_persistence': result.drift_assessment.persistence_count,
        'existing_authority': dict(result.authority_assessment.action_authority),
        'assurance_status': result.assurance_assessment.status.value,
        'assured_authority': dict(result.assured_authority_assessment.action_authority),
        'planning_candidates': [candidate.action.value for candidate in result.planning_result.candidates],
        'selected_action': result.proposed_decision.selected_action.value,
        'governance': result.governance_decision.status.value,
        'execution': result.execution_result.execution_status.value,
        'expected_action_evaluator_only': expected,
    }


def _metrics(pairs):
    result = TAIOSEvaluator().evaluate_experiment(pairs).to_dict()
    overall = result['overall_results']
    return ({metric: overall[metric] for metric in METRICS}, result)


def evaluate(events_per_run=50):
    streams = {}
    for scenario in SCENARIOS:
        for seed in SEEDS:
            generator = EventGenerator(seed, observable_state=True)
            run = generator.create_run(scenario, events_per_run)
            streams[(scenario, seed)] = (run, generator.generate(scenario, events_per_run, run))

    configurations, episodes = {}, {}
    for configuration in ExperimentalConfiguration:
        pairs, per_seed = [], {}
        for key, (run, events) in streams.items():
            pipeline = create_pipeline(configuration)
            episode = pipeline.run_episode(events, scenario_reference=run.experiment_id, seed=key[1])
            episodes[(configuration.value, *key)] = episode
            pairs.append((episode, events))
        aggregate, details = _metrics(pairs)
        for seed in SEEDS:
            seed_pairs = [(episodes[(configuration.value, scenario, seed)], streams[(scenario, seed)][1]) for scenario in SCENARIOS]
            per_seed[str(seed)] = _metrics(seed_pairs)[0]
        configurations[configuration.value] = {
            'aggregate_metrics': aggregate, 'per_seed_metrics': per_seed,
            'seed_summary': {metric: _summary(per_seed[str(seed)][metric] for seed in SEEDS) for metric in METRICS},
            'specification_fingerprint': CONFIGURATION_SPECS[configuration].configuration_fingerprint,
        }

    # Causal 8B check: the same S7 event instances are delivered to fresh pipelines.
    off_pairs, on_pairs, off_lookup, on_lookup = [], [], {}, {}
    for key, (run, events) in streams.items():
        if key[0] != 'S7':
            continue
        off = TAIOSPipeline(assurance_enabled=False).run_episode(events, scenario_reference=run.experiment_id, seed=key[1])
        on = TAIOSPipeline(assurance_enabled=True).run_episode(events, scenario_reference=run.experiment_id, seed=key[1])
        off_pairs.append((off, events)); on_pairs.append((on, events)); off_lookup[key] = off; on_lookup[key] = on
    causal = Counter()
    for on, off in zip(on_lookup[('S7', 42)].pipeline_results, off_lookup[('S7', 42)].pipeline_results):
        causal['permissive_upstream'] += on.authority_assessment.action_authority['ALLOW'] == 'PERMITTED'
        causal['adverse_observable_evidence'] += on.drift_assessment.status.value == 'UNEXPLAINED_PERSISTENT_DRIFT'
        causal['assurance_restrictions'] += bool(on.assurance_assessment.restrictions)
        causal['planning_changes'] += on.planning_result != off.planning_result
        causal['final_action_changes'] += on.proposed_decision.selected_action != off.proposed_decision.selected_action
        causal['review_introductions'] += (on.proposed_decision.selected_action.value == 'REQUEST_APPROVAL' and
                                           off.proposed_decision.selected_action.value != 'REQUEST_APPROVAL')
    s7_events = streams[('S7', 42)][1]
    s7_on = on_lookup[('S7', 42)]
    causal_table = [_row(row, event, event.expected_safe_action) for row, event in zip(s7_on.pipeline_results, s7_events)]
    on_metrics, _ = _metrics(on_pairs); off_metrics, _ = _metrics(off_pairs)

    return {
        'evaluation_version': 'milestone8c-extended-scenarios-v1',
        'events_per_episode': events_per_run, 'seeds': list(SEEDS),
        'scenario_metadata': {scenario: get_scenario_evaluation_metadata(scenario, events_per_run).to_dict() for scenario in SCENARIOS},
        'scenario_fingerprints': {scenario: fingerprint(get_scenario_evaluation_metadata(scenario, events_per_run).to_dict()) for scenario in SCENARIOS},
        'configuration_fingerprints': _pipeline_fingerprints(),
        'event_stream_fingerprints': {f'{scenario}:{seed}': event_stream_fingerprint(events)
                                      for (scenario, seed), (_, events) in streams.items()},
        'configuration_results': configurations,
        's7_assurance_off_on': {'off_metrics': off_metrics, 'on_metrics': on_metrics,
                                'seed42_causal_counts': dict(causal)},
        's7_seed42_causal_table': causal_table,
        's7_seed42_trajectories': [{key: row[key] for key in ('event_position', 'trust_after', 'risk', 'threat_status', 'drift_status', 'assurance_status')}
                                    for row in causal_table],
        'limitations': ['S7 uses only valid observable behavior; frozen threat evidence has no direct category for it.',
                        'Dynamic trust evidence remains positive for within-limit registered requests.',
                        'Recovery is observational; no recovery rule was added.',
                        'Five seeds are exploratory replication units, not independent events.'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', type=int, default=50)
    parser.add_argument('--output', type=Path, default=Path('results/milestone8c-extended-scenarios.json'))
    args = parser.parse_args()
    result = evaluate(args.events)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(f'Evaluated {len(SCENARIOS) * len(SEEDS)} long streams across four configurations; saved {args.output}')


if __name__ == '__main__':
    main()
