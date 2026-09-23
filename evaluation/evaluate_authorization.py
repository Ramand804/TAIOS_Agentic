"""Semantic coverage only; scenario/seed annotations stay outside inference."""
import json
from collections import Counter, defaultdict

from core.runtime_inputs import runtime_observation
from environment.event_generator import EventGenerator
from intelligence.authorization_engine import AuthorizationEngine

SEEDS = (42, 123, 456, 789, 2026)
SCENARIOS = tuple(f'S{i}' for i in range(1, 7))


def summary(values):
    counts = Counter(values)
    total = sum(counts.values())
    return {s: {'count': counts[s], 'rate': counts[s] / total if total else None}
            for s in ('AUTHORIZED', 'UNAUTHORIZED', 'UNKNOWN')}


def coverage(events_per_run=10):
    engine = AuthorizationEngine()
    all_statuses, by_scenario, by_group = [], defaultdict(list), defaultdict(list)
    patterns = defaultdict(set)
    run_summaries = []
    for seed in SEEDS:
        for scenario in SCENARIOS:
            observations = [runtime_observation(e) for e in
                            EventGenerator(seed, observable_state=True).generate(scenario, events_per_run)]
            assessments = [engine.assess(o) for o in observations]
            statuses = [a.status.value for a in assessments]
            all_statuses.extend(statuses)
            by_scenario[scenario].extend(statuses)
            run_summaries.append({'seed': seed, 'scenario': scenario, 'counts': summary(statuses)})
            for o, a in zip(observations, assessments):
                key = (o['source_type'], o['target_type'], o['operation'])
                by_group[key].append(a.status.value)
                if seed == 42:
                    patterns[scenario].add((engine.identities[o['identity_id']].role,
                        *key, a.status.value, ','.join(a.matched_rule_ids) or 'NONE'))
    return {'permission_policy': engine.policy.to_dict(),
            'permission_policy_reference': engine.policy.reference,
            'seeds': list(SEEDS), 'events_per_run': events_per_run,
            'total_events': len(all_statuses), 'overall': summary(all_statuses),
            'by_scenario': {s: summary(v) for s, v in sorted(by_scenario.items())},
            'by_source_target_operation': [{'source_type': k[0], 'target_type': k[1],
                'operation': k[2], 'coverage': summary(v)} for k, v in sorted(by_group.items())],
            'runs': run_summaries,
            'seed42_unique_patterns': {s: [dict(zip(('identity_role', 'source_type', 'target_type',
                'operation', 'status', 'matched_rule'), p)) for p in sorted(v)]
                for s, v in sorted(patterns.items())},
            'seed42_unique_pattern_coverage': {s: summary([p[4] for p in v]) for s, v in sorted(patterns.items())}}


if __name__ == '__main__':
    print(json.dumps(coverage(), sort_keys=True, indent=2, allow_nan=False))
