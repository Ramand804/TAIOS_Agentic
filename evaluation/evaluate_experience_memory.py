"""Deterministic diagnostics for Milestone-7A outcome and episodic memory."""
import argparse
import json
from collections import Counter
from pathlib import Path

from core.experiment import fingerprint
from core.observed_outcome import OUTCOME_OBSERVER_VERSION
from core.taios_pipeline import TAIOSPipeline
from environment.event_generator import EventGenerator
from evaluation.formal_evaluator import TAIOSEvaluator
from evaluation.run_formal_evaluation import SCENARIOS, SEEDS
from memory.episodic_memory import MEMORY_VERSION


BASELINE_STRUCTURE = {
    'proposals': {'ALLOW': 93, 'REQUEST_APPROVAL': 207},
    'governance_statuses': {'APPROVAL_REQUIRED': 207, 'APPROVED': 93},
    'execution_statuses': {'PENDING_APPROVAL': 207, 'SUCCEEDED': 93},
}
BASELINE_FORMAL = {
    'exact_action_agreement': 143 / 300,
    'unsafe_action_rate': 0.0,
    'false_intervention_rate': 72 / 165,
    'proposal_review_burden': 207 / 300,
    'autonomous_execution_rate': 93 / 300,
}


def evaluate(events_per_run=10):
    outcomes = Counter()
    proposals, governance, execution = Counter(), Counter(), Counter()
    scenario_results = {}
    run_memories = []
    completed = []
    s2_seed42, s5_seed42, s6_seed42 = [], [], []
    mutation_count = no_op_count = pending_count = experience_count = 0
    retrieval_checks = Counter()

    for scenario in SCENARIOS:
        scenario_outcomes = Counter()
        scenario_experiences = scenario_mutations = scenario_noops = scenario_pending = 0
        scenario_fingerprints = []
        for seed in SEEDS:
            generator = EventGenerator(seed, observable_state=True)
            experiment = generator.create_run(scenario, events_per_run)
            events = generator.generate(scenario, events_per_run, experiment)
            pipeline = TAIOSPipeline()
            episode = pipeline.run_episode(
                events, scenario_reference=experiment.experiment_id, seed=seed)
            completed.append((episode, events))
            memory = pipeline.memory
            scenario_fingerprints.append({'seed': seed, 'memory_fingerprint': memory.memory_fingerprint})
            run_memories.append(memory.memory_fingerprint)
            experience_count += memory.count
            scenario_experiences += memory.count
            retrieval_checks['event'] += all(
                record in memory.get_by_event(record.event_reference) for record in memory.records)
            retrieval_checks['source'] += all(
                record in memory.get_by_source(record.source_id) for record in memory.records)
            retrieval_checks['target'] += all(
                record in memory.get_by_target(record.target_id) for record in memory.records)
            retrieval_checks['operation'] += all(
                record in memory.get_by_operation(record.operation) for record in memory.records)
            retrieval_checks['recent_order'] += memory.recent(memory.count) == memory.records
            for result, record in zip(episode.pipeline_results, memory.records):
                outcome = result.observed_outcome
                outcomes[outcome.outcome_status.value] += 1
                scenario_outcomes[outcome.outcome_status.value] += 1
                mutation_count += outcome.mutation_observed
                scenario_mutations += outcome.mutation_observed
                is_noop = outcome.outcome_status.value == 'EXECUTED_NOOP_OBSERVED'
                is_pending = outcome.outcome_status.value == 'PENDING_EXTERNAL_APPROVAL'
                no_op_count += is_noop; scenario_noops += is_noop
                pending_count += is_pending; scenario_pending += is_pending
                proposals[result.proposed_decision.selected_action.value] += 1
                governance[result.governance_decision.status.value] += 1
                execution[result.execution_result.execution_status.value] += 1
                row = {
                    'sequence_number': result.sequence_number,
                    'source_id': record.source_id, 'target_id': record.target_id,
                    'operation': record.operation,
                    'proposal': result.proposed_decision.selected_action.value,
                    'governance': result.governance_decision.status.value,
                    'execution': result.execution_result.execution_status.value,
                    'observed_outcome': outcome.outcome_status.value,
                    'mutation_observed': outcome.mutation_observed,
                    'state_version_before': outcome.state_version_before,
                    'state_version_after': outcome.state_version_after,
                    'operating_mode_after': outcome.operating_mode_after,
                    'trust_before': record.trust_before, 'trust_after': record.trust_after,
                    'risk_score': record.risk_score,
                    'risk_coverage': record.risk_coverage,
                    'threat_assessment_reference': record.threat_assessment_reference,
                    'correlation_assessment_reference': record.correlation_assessment_reference,
                    'correlation_status': result.correlation_assessment.status.value,
                    'experience_reference': record.reference,
                }
                if seed == 42:
                    {'S2': s2_seed42, 'S5': s5_seed42, 'S6': s6_seed42}.get(
                        scenario, []).append(row)
        scenario_results[scenario] = {
            'experience_count': scenario_experiences,
            'outcome_statuses': dict(sorted(scenario_outcomes.items())),
            'mutation_observed_count': scenario_mutations,
            'successful_noop_count': scenario_noops,
            'pending_outcome_count': scenario_pending,
            'run_memory_fingerprints': scenario_fingerprints,
        }

    structure = {
        'proposals': dict(sorted(proposals.items())),
        'governance_statuses': dict(sorted(governance.items())),
        'execution_statuses': dict(sorted(execution.items())),
    }
    formal = TAIOSEvaluator().evaluate_experiment(completed).to_dict()['overall_results']
    formal_current = {key: formal[key] for key in BASELINE_FORMAL}
    return {
        'evaluation_version': 'milestone7a-experience-memory-v1',
        'outcome_observer_version': OUTCOME_OBSERVER_VERSION,
        'experience_version': 'milestone7a-experience-v1',
        'memory_version': MEMORY_VERSION,
        'seeds': list(SEEDS), 'scenarios': list(SCENARIOS),
        'events_per_run': events_per_run, 'total_events': experience_count,
        'experience_count': experience_count,
        'outcome_status_distribution': dict(sorted(outcomes.items())),
        'mutation_observed_count': mutation_count,
        'successful_noop_count': no_op_count,
        'pending_outcome_count': pending_count,
        'ordered_run_memory_fingerprint': fingerprint(run_memories),
        'retrieval_integrity': {
            'runs_checked': len(run_memories),
            'event_runs_passed': retrieval_checks['event'],
            'source_runs_passed': retrieval_checks['source'],
            'target_runs_passed': retrieval_checks['target'],
            'operation_runs_passed': retrieval_checks['operation'],
            'recent_order_runs_passed': retrieval_checks['recent_order'],
        },
        'by_scenario': scenario_results,
        's2_continuous_experience_seed42': s2_seed42,
        's5_regime_and_noop_seed42': s5_seed42,
        's6_experience_seed42': s6_seed42,
        'risk_regression': {
            'changed': False,
            'verification': 'Compared separately with unchanged Milestone-6C diagnostic.',
        },
        'correlation_regression': {
            'changed': False,
            'verification': 'Compared separately with unchanged Milestone-6D diagnostic.',
        },
        'structural_replay': {
            'before_milestone7a': BASELINE_STRUCTURE,
            'after_milestone7a': structure,
            'changed': structure != BASELINE_STRUCTURE,
        },
        'post_freeze_formal_evaluation': {
            'before_milestone7a': BASELINE_FORMAL,
            'after_milestone7a': formal_current,
            'changed': formal_current != BASELINE_FORMAL,
            'note': 'Evaluator labels were joined only after inference and experience recording.',
        },
        'limitations': [
            'Outcomes describe simulator-visible software state only.',
            'Pending approval has no fabricated human response or later physical effect.',
            'Experience records have no reward, utility, correctness, or security label.',
            'Memory is in-process, episode-scoped, and does not influence inference.',
            'No adaptation, drift detection, learning, baseline, ablation, or ML is implemented.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', type=int, default=10)
    parser.add_argument('--output', type=Path,
                        default=Path('results/milestone7a-experience-memory.json'))
    args = parser.parse_args()
    result = evaluate(args.events)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(f'Recorded {result["experience_count"]} experiences; saved {args.output}')


if __name__ == '__main__':
    main()
