"""Authority coverage and before/after planning replay; labels stay outside inference."""
import json
from collections import Counter

from agents.planning_agent import PlanningAgent
from agents.risk_agent import RiskAgent
from agents.trust_agent import TrustAgent
from core.actions import Action
from core.runtime_inputs import runtime_observation
from environment.event_generator import EventGenerator
from evaluation.evaluate_risk import assess_observations
from intelligence.authorization_engine import AuthorizationEngine
from intelligence.autonomous_authority_engine import AutonomousAuthorityEngine
from intelligence.decision_context_builder import build_decision_context

SEEDS = (42, 123, 456, 789, 2026)
SCENARIOS = tuple(f'S{i}' for i in range(1, 7))
DIAGNOSTICS = {'S1': (6,), 'S2': (5, 6, 7, 8), 'S3': (6,), 'S5': (5, 6, 7)}


def _counts(values):
    counts = Counter(values)
    total = sum(counts.values())
    return {status: {'count': counts[status], 'rate': counts[status] / total if total else None}
            for status in ('PERMITTED', 'NOT_PERMITTED', 'UNKNOWN')}


def _pipeline(scenario, seed=42, n=10):
    events = EventGenerator(seed, observable_state=True).generate(scenario, n)
    trusts, risks = assess_observations(events, TrustAgent(), RiskAgent())
    authorization_engine = AuthorizationEngine()
    authority_engine = AutonomousAuthorityEngine()
    planner = PlanningAgent()
    rows = []
    for event, trust, risk in zip(events, trusts, risks):
        observation = runtime_observation(event)
        authorization = authorization_engine.assess(observation)
        base = build_decision_context(observation, trust, risk, authorization,
                                      permission_policy=authorization_engine.policy)
        old_plan = planner.plan(base)
        authority = authority_engine.assess(base)
        context = build_decision_context(
            observation, trust, risk, authorization,
            permission_policy=authorization_engine.policy,
            autonomous_authority_assessment=authority,
            authority_policy=authority_engine.policy,
        )
        rows.append((event, context, authority, old_plan, planner.plan(context)))
    return rows, authority_engine


def evaluate(events_per_run=10):
    coverage = {action.value: [] for action in Action}
    by_scenario = {scenario: {action.value: [] for action in Action} for scenario in SCENARIOS}
    diagnostics = []
    policy = None
    for seed in SEEDS:
        for scenario in SCENARIOS:
            rows, engine = _pipeline(scenario, seed, events_per_run)
            policy = engine.policy
            for event, context, authority, old_plan, new_plan in rows:
                for action in Action:
                    status = authority.status_for(action).value
                    coverage[action.value].append(status)
                    by_scenario[scenario][action.value].append(status)
                if seed == 42 and event.sequence_number in DIAGNOSTICS.get(scenario, ()):
                    old_actions = [candidate.action.value for candidate in old_plan.candidates]
                    new_actions = [candidate.action.value for candidate in new_plan.candidates]
                    diagnostics.append({
                        'scenario': scenario, 'sequence': event.sequence_number,
                        'authorization': context.authorization_status.value,
                        'operational_validity': context.capabilities.operational_validity.to_dict(),
                        'trust': context.trust_assessment.composite_trust,
                        'risk': context.risk_assessment.risk_score,
                        'risk_coverage': context.risk_assessment.coverage,
                        'capabilities': [action.value for action in context.capabilities.supported_actions],
                        'action_authority': authority.to_dict()['action_authority'],
                        'old_candidates': old_actions, 'new_candidates': new_actions,
                        'added': [action for action in new_actions if action not in old_actions],
                        'removed': [action for action in old_actions if action not in new_actions],
                        'unchanged': [action for action in old_actions if action in new_actions],
                        'reason': ('Candidate differences follow only explicit per-action authority; '
                                   'capability, operational validity and existing candidate payload rules remain in force.'),
                        'authority_assessment': authority.to_dict(),
                        'context_reference': context.reference,
                        'planning_result': new_plan.to_dict(),
                    })
    diagnostics.sort(key=lambda row: (row['scenario'], row['sequence']))
    return {
        'seeds': list(SEEDS), 'scenarios': list(SCENARIOS),
        'events_per_run': events_per_run, 'total_events': len(SEEDS) * len(SCENARIOS) * events_per_run,
        'authority_policy': policy.to_dict(), 'authority_policy_fingerprint': policy.reference,
        'per_action_coverage': {action: _counts(values) for action, values in coverage.items()},
        'per_scenario_action_coverage': {
            scenario: {action: _counts(values) for action, values in actions.items()}
            for scenario, actions in by_scenario.items()
        },
        'diagnostics': diagnostics,
    }


if __name__ == '__main__':
    print(json.dumps(evaluate(), sort_keys=True, indent=2, allow_nan=False))
