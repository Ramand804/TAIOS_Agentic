"""Deterministic offline harness. Evaluation labels are joined AFTER inference."""
import argparse
from collections import defaultdict
from dataclasses import asdict
import json
from pathlib import Path

from agents.trust_agent import TrustAgent
from core.runtime_inputs import runtime_observation
from core.event_manager import EventManager
from core.experiment import fingerprint
from environment.event_generator import EventGenerator
from environment.scenarios import get_scenario_manifest
from evaluation.trust_metrics import trust_metrics, aggregate_runs
from intelligence.trust_model import TrustModelConfig
from intelligence.trust_evidence_extractor import EvidenceConfig


DEFAULT_SEEDS = (42,123,456,789,2026)
DEFAULT_SCENARIOS = ('S1','S2','S3','S5')


def assess_observations(events, agent):
    """Complete inference before reading ANY evaluation labels or manifest data."""
    counters = defaultdict(int)
    assessments = []
    for event in events:
        observation = runtime_observation(event)
        entity = 'asset:' + observation['source_id']
        counters[entity] += 1
        ordinal = counters[entity]
        assessments.append(agent.assess(observation,delivery_token=f'delivery-{ordinal}',observation_number=ordinal))
    return assessments


def trajectory_records(events, assessments):
    if len(events) != len(assessments): raise ValueError('Event/assessment counts differ')
    records = []
    for event, assessment in zip(events, assessments):
        record = assessment.to_inference_dict()
        record.update(experiment_id=event.experiment_id, scenario_id=event.scenario_id,
                      sequence_number=event.sequence_number, phase=event.provenance.phase,
                      ground_truth=event.ground_truth, expected_safe_action=event.expected_safe_action,
                      operation=event.operation, requested_value=event.requested_value,
                      operating_mode=event.contextual_features.get('operating_mode'))
        records.append(record)
    return records


def evaluate_run(scenario_id, seed=42, total_events=10):
    if type(total_events) is not int or total_events < 0: raise ValueError('total_events must be nonnegative')
    generator = EventGenerator(seed,observable_state=True)
    experiment = generator.create_run(scenario_id,total_events)
    events = generator.generate(scenario_id,total_events,experiment)
    model_config, evidence_config = TrustModelConfig.load(), EvidenceConfig.load()
    assessments = assess_observations(events,TrustAgent(model_config=model_config,evidence_config=evidence_config))
    # Metadata is consumed only after all trust inference has completed.
    manifest = get_scenario_manifest(scenario_id,total_events)
    EventManager().validate(events,manifest,experiment)
    records = trajectory_records(events,assessments)
    by_entity = defaultdict(list)
    for record in records: by_entity[record['entity_id']].append(record)
    config = {'model':asdict(model_config),'evidence':asdict(evidence_config),'evaluation_version':'day2e-v1'}
    identity = 'TRUST-EVAL-' + fingerprint({'experiment':experiment.to_dict(),'configuration':config})[:20]
    limitations = ['UNCALIBRATED: scores are not probabilities.', 'Recovery not measurable with current scenarios.']
    if any('MISSING_LIMIT' in reason and r['operation']=='write_register' for r in records for reason in r['reasons']):
        limitations.append('BEHAVIORAL SEMANTICS INSUFFICIENT: write_register lacks operational range/authorization policy.')
    return {'evaluation_id':identity,'experiment':experiment.to_dict(),'configuration':config,
            'scenario_manifest':manifest.to_dict(),'trajectory':records,
            'metrics':trust_metrics(records,manifest.transition_sequence),
            'entity_metrics':{entity:trust_metrics(rows,manifest.transition_sequence) for entity,rows in sorted(by_entity.items())},
            'limitations':limitations}


def evaluate_suite(scenarios=DEFAULT_SCENARIOS,seeds=DEFAULT_SEEDS,total_events=10):
    runs = [evaluate_run(scenario,seed,total_events) for scenario in scenarios for seed in seeds]
    return {'evaluation_version':'day2e-v1','events_per_run':total_events,'runs':runs,'aggregates':aggregate_runs(runs)}


def stable_json(result):
    return json.dumps(result,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events',type=int,default=10)
    parser.add_argument('--seeds',type=int,nargs='+',default=list(DEFAULT_SEEDS))
    parser.add_argument('--scenarios',nargs='+',choices=[f'S{i}' for i in range(1,7)],default=list(DEFAULT_SCENARIOS))
    parser.add_argument('--output',type=Path,default=Path('results/trust_evaluation.json'))
    args=parser.parse_args()
    result=evaluate_suite(args.scenarios,args.seeds,args.events)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(stable_json(result),encoding='utf-8')
    print(f'Evaluated {len(result["runs"])} runs; saved {args.output}')


if __name__=='__main__': main()
