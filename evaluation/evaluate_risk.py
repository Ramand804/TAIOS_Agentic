"""Offline risk evaluation: inference completes before joining experimental labels."""
import argparse
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from agents.trust_agent import TrustAgent
from agents.risk_agent import RiskAgent
from core.runtime_inputs import runtime_observation
from core.risk_input import RiskConfig
from core.event_manager import EventManager
from core.experiment import fingerprint
from environment.event_generator import EventGenerator
from environment.scenarios import get_scenario_manifest
from intelligence.trust_model import TrustModelConfig
from intelligence.trust_evidence_extractor import EvidenceConfig
from intelligence.risk_model import MODEL_VERSION
from evaluation.evaluate_trust import DEFAULT_SEEDS, DEFAULT_SCENARIOS, stable_json
from evaluation.risk_metrics import risk_metrics, aggregate_runs, with_risk_deltas, TOLERANCE

VERSION = 'day3e-v1'
LIMITATIONS = ['UNCALIBRATED: risk_score is NOT attack probability.',
    'THREAT SIGNAL UNAVAILABLE; independent anomaly unavailable.',
    'Different target criticalities and coverage masks can change absolute risk.',
    'Threshold sensitivity deferred until Decision/Governance evaluation; no attack classification.',
    'Ablations and predictive validation are deferred.']


def assess_observations(events, trust_agent, risk_agent):
    counts = defaultdict(int)
    trusts, risks = [], []
    for event in events:
        observation = runtime_observation(event)
        source = observation['source_id']; counts[source] += 1
        trust = trust_agent.assess(observation, delivery_token=f'local-{counts[source]}', observation_number=counts[source])
        risk = risk_agent.assess(observation, trust, expected_trust_state_version=trust.trust_state_version)
        trusts.append(trust); risks.append(risk)
    return trusts, risks


def trajectory_records(events, trusts, risks):
    if len(events) != len(trusts) or len(events) != len(risks):
        raise ValueError('Event/assessment counts differ')
    records = []
    for event,trust,risk in zip(events,trusts,risks):
        row = risk.to_inference_dict()
        row.update(experiment_id=event.experiment_id,scenario_id=event.scenario_id,
                   sequence_number=event.sequence_number,phase=event.provenance.phase,
                   ground_truth=event.ground_truth,expected_safe_action=event.expected_safe_action,
                   requested_value=event.requested_value,operating_mode=event.contextual_features.get('operating_mode'),
                   trust_assessment=trust.to_inference_dict())
        records.append(row)
    return with_risk_deltas(records)


def evaluate_run(scenario_id, seed=42, total_events=10):
    generator = EventGenerator(seed,observable_state=True)
    experiment = generator.create_run(scenario_id,total_events)
    events = generator.generate(scenario_id,total_events,experiment)
    tc,ec,rc = TrustModelConfig.load(),EvidenceConfig.load(),RiskConfig.load()
    trusts,risks = assess_observations(events,TrustAgent(model_config=tc,evidence_config=ec),RiskAgent(config=rc))
    # Only after ALL inference is complete may the evaluator inspect metadata.
    manifest = get_scenario_manifest(scenario_id,total_events)
    EventManager().validate(events,manifest,experiment)
    records = trajectory_records(events,trusts,risks)
    configuration = {'trust':asdict(tc),'evidence':asdict(ec),'risk':rc.to_dict(),
                     'risk_configuration_fingerprint':rc.fingerprint,'risk_model_version':MODEL_VERSION,
                     'evaluation_version':VERSION,'tolerance':TOLERANCE}
    limitations = list(LIMITATIONS)
    if any(r['operation']=='write_register' and r['trust_evidence_coverage']['BEHAVIOR']==['INSUFFICIENT'] for r in records):
        limitations.append('BEHAVIORAL SEMANTICS INSUFFICIENT: no approved register/authorization semantics; not credential-compromise detection.')
    return {'evaluation_id':'RISK-EVAL-'+fingerprint({'experiment':experiment.to_dict(),'configuration':configuration})[:20],
        'experiment':experiment.to_dict(),'configuration':configuration,'scenario_manifest':manifest.to_dict(),
        'trajectory':records,'metrics':risk_metrics(records,manifest.transition_sequence),'limitations':limitations}


def evaluate_suite(scenarios=DEFAULT_SCENARIOS,seeds=DEFAULT_SEEDS,total_events=10):
    scenarios,seeds = tuple(scenarios),tuple(seeds)
    runs = [evaluate_run(s,seed,total_events) for s in scenarios for seed in seeds]
    return {'evaluation_version':VERSION,'seeds':list(seeds),'scenarios':list(scenarios),'events_per_run':total_events,
            'runs':runs,'aggregates':aggregate_runs(runs),'limitations':LIMITATIONS.copy()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events',type=int,default=10)
    parser.add_argument('--output',type=Path,default=Path('results/day3e.json'))
    args = parser.parse_args()
    result = evaluate_suite(total_events=args.events)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(stable_json(result),encoding='utf-8')
    print(f'Evaluated {len(result["runs"])} runs; saved {args.output}')


if __name__=='__main__': main()
