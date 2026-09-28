"""Deterministic Milestone-8B assurance OFF/ON diagnostic."""
import argparse
import json
from collections import Counter
from pathlib import Path

from core.taios_pipeline import TAIOSPipeline
from environment.event_generator import EventGenerator
from evaluation.formal_evaluator import TAIOSEvaluator
from evaluation.run_formal_evaluation import SCENARIOS, SEEDS


def _run(enabled, events_per_run=10):
    statuses, evidence, effects = Counter(), Counter(), Counter()
    restrictions = plan_changes = action_changes = upstream = 0
    pairs, trajectories = [], {}
    for scenario in SCENARIOS:
        for seed in SEEDS:
            g = EventGenerator(seed, observable_state=True)
            run = g.create_run(scenario, events_per_run)
            events = g.generate(scenario, events_per_run, run)
            on = TAIOSPipeline(assurance_enabled=enabled).run_episode(
                events, scenario_reference=run.experiment_id, seed=seed)
            off = TAIOSPipeline(assurance_enabled=False).run_episode(
                events, scenario_reference=run.experiment_id, seed=seed)
            pairs.append((on, events))
            for a, b in zip(on.pipeline_results, off.pipeline_results):
                assurance = a.assurance_assessment
                statuses[assurance.status.value] += 1
                effects[assurance.causal_effect.value] += 1
                evidence.update(item.category for item in assurance.evidence_items)
                restrictions += bool(assurance.restrictions)
                plan_changes += a.planning_result != b.planning_result
                action_changes += a.proposed_decision.selected_action != b.proposed_decision.selected_action
                upstream += assurance.causal_effect.value == 'ALREADY_RESTRICTED_UPSTREAM'
            if seed == 42 and scenario in ('S2', 'S5'):
                trajectories[scenario] = [{
                    'event': a.sequence_number,
                    'value': a.observable_input['requested_value'],
                    'semantic_status': a.operational_semantic_assessment.semantic_status.value,
                    'trust_before': a.trust_assessment.previous_composite_trust,
                    'trust_after': a.trust_assessment.composite_trust,
                    'trust_delta': a.trust_assessment.trust_delta,
                    'threat_status': a.threat_assessment.status.value,
                    'risk_score': a.risk_assessment.risk_score,
                    'risk_coverage': a.risk_assessment.coverage,
                    'drift_status': a.drift_assessment.status.value,
                    'existing_authority': dict(a.authority_assessment.action_authority),
                    'assurance_status': a.assurance_assessment.status.value,
                    'assured_authority': dict(a.assured_authority_assessment.action_authority),
                    'proposal': a.proposed_decision.selected_action.value,
                    'governance': a.governance_decision.status.value,
                    'execution': a.execution_result.execution_status.value,
                } for a in on.pipeline_results]
    overall = TAIOSEvaluator().evaluate_experiment(pairs).to_dict()['overall_results']
    return {'mode': 'ASSURANCE_ON' if enabled else 'ASSURANCE_OFF',
            'status_distribution': dict(sorted(statuses.items())),
            'evidence_categories': dict(sorted(evidence.items())),
            'causal_effects': dict(sorted(effects.items())),
            'authority_restrictions': restrictions, 'planning_candidate_changes': plan_changes,
            'final_action_changes': action_changes,
            'already_restricted_upstream': upstream,
            'formal_metrics': {k: overall[k] for k in ('exact_action_agreement','unsafe_action_rate','false_intervention_rate','proposal_review_burden','autonomous_execution_rate')},
            'trajectories_seed42': trajectories}


def evaluate(events_per_run=10):
    off, on = _run(False, events_per_run), _run(True, events_per_run)
    return {'evaluation_version': 'milestone8b-decision-assurance-v1',
            'events': 300, 'off': off, 'on': on,
            'invariant': 'Assured autonomous actions are a subset of existing autonomous actions; REQUEST_APPROVAL is deferral only.',
            'limitations': ['Risk is contextual, not a decision threshold.', 'Current scenarios contain no direct-correlation evidence.', 'No future discriminating scenario is included.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('results/milestone8b-decision-assurance.json'))
    args=parser.parse_args(); result=evaluate(); args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(f'Assessed {result["events"]} events in OFF and ON modes; saved {args.output}')


if __name__=='__main__': main()
