"""Proposal-only DecisionAgent diagnostics; evaluator labels never enter inference."""
import json
from collections import Counter

from agents.decision_agent import DecisionAgent
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


def inference_rows(scenario, seed=42, n=10):
    events = EventGenerator(seed, observable_state=True).generate(scenario, n)
    trusts, risks = assess_observations(events, TrustAgent(), RiskAgent())
    authorization_engine = AuthorizationEngine()
    authority_engine = AutonomousAuthorityEngine()
    planner, decider = PlanningAgent(), DecisionAgent()
    rows = []
    for event, trust, risk in zip(events, trusts, risks):
        observation = runtime_observation(event)
        authorization = authorization_engine.assess(observation)
        base = build_decision_context(observation, trust, risk, authorization,
                                      permission_policy=authorization_engine.policy)
        authority = authority_engine.assess(base)
        context = build_decision_context(
            observation, trust, risk, authorization,
            permission_policy=authorization_engine.policy,
            autonomous_authority_assessment=authority,
            authority_policy=authority_engine.policy,
        )
        plan = planner.plan(context)
        decision = decider.decide(context, plan)
        rows.append((event, context, plan, decision))
    return rows


def evaluate(events_per_run=10):
    distribution = Counter()
    by_scenario = {scenario: Counter() for scenario in SCENARIOS}
    diagnostics = []
    for seed in SEEDS:
        for scenario in SCENARIOS:
            for event, context, plan, decision in inference_rows(scenario, seed, events_per_run):
                proposal = decision.selected_action.value if decision.selected_action is not None else 'NO_DECISION'
                distribution[proposal] += 1
                by_scenario[scenario][proposal] += 1
                if seed == 42 and event.sequence_number in DIAGNOSTICS.get(scenario, ()):
                    authority = context.autonomous_authority_assessment
                    diagnostics.append({
                        'scenario': scenario, 'sequence': event.sequence_number,
                        'candidates': [candidate.action.value for candidate in plan.candidates],
                        'proposed_action': proposal,
                        'alternatives': list(decision.alternatives_considered),
                        'primary_reason': decision.primary_reason,
                        'authorization': context.authorization_status.value,
                        'operational_validity': context.capabilities.operational_validity.to_dict(),
                        'authority_basis': authority.to_dict(),
                        'trust': context.trust_assessment.composite_trust,
                        'risk': context.risk_assessment.risk_score,
                        'risk_coverage': context.risk_assessment.coverage,
                        'unresolved_constraints': list(decision.uncertainty),
                        'decision_policy_version': decision.decision_policy_version,
                        'decision_fingerprint': decision.reference,
                        'planning_reference': plan.reference,
                        'context_reference': context.reference,
                        'decision': decision.to_dict(),
                    })
    labels = [action.value for action in Action] + ['NO_DECISION']
    diagnostics.sort(key=lambda row: (row['scenario'], row['sequence']))
    return {
        'seeds': list(SEEDS), 'scenarios': list(SCENARIOS),
        'events_per_run': events_per_run,
        'total_proposals': sum(distribution.values()),
        'proposal_distribution': {label: distribution[label] for label in labels},
        'per_scenario_distribution': {
            scenario: {label: counts[label] for label in labels}
            for scenario, counts in by_scenario.items()
        },
        'diagnostics': diagnostics,
    }


if __name__ == '__main__':
    print(json.dumps(evaluate(), sort_keys=True, indent=2, allow_nan=False))
