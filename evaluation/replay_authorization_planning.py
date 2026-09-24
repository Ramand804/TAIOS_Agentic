"""Before/after replay: legacy UNKNOWN versus explicit permission facts."""
import json
from agents.trust_agent import TrustAgent
from agents.risk_agent import RiskAgent
from agents.planning_agent import PlanningAgent
from core.runtime_inputs import runtime_observation
from environment.event_generator import EventGenerator
from evaluation.evaluate_risk import assess_observations
from intelligence.authorization_engine import AuthorizationEngine
from intelligence.decision_context_builder import build_decision_context


def replay():
    rows = []
    engine, planner = AuthorizationEngine(), PlanningAgent()
    for scenario, sequences in (('S1', (6,)), ('S2', (5, 6, 7, 8)), ('S3', (6,)), ('S5', (5, 6, 7))):
        events = EventGenerator(42, observable_state=True).generate(scenario, 10)
        trusts, risks = assess_observations(events, TrustAgent(), RiskAgent())
        for seq in sequences:
            o = runtime_observation(events[seq-1])
            t, r = trusts[seq-1], risks[seq-1]
            a = engine.assess(o)
            old = build_decision_context(o, t, r)
            new = build_decision_context(o, t, r, a, permission_policy=engine.policy)
            before, after = planner.plan(old), planner.plan(new)
            old_actions = [c.action.value for c in before.candidates]
            new_actions = [c.action.value for c in after.candidates]
            rows.append(dict(scenario=scenario, sequence=seq,
                old_authorization=old.authorization_status.value,
                new_authorization=new.authorization_status.value,
                old_candidates=old_actions, new_candidates=new_actions,
                added_candidates=[a for a in new_actions if a not in old_actions],
                removed_candidates=[a for a in old_actions if a not in new_actions],
                unchanged_candidates=[a for a in old_actions if a in new_actions],
                addition_removal_reasons={},
                explanation='Membership unchanged: current planner still requires policy clearance and an executable permission envelope for permissive actions; range-only LIMIT and logical approval rules are unchanged.',
                operational_validity=new.capabilities.operational_validity.to_dict(),
                trust=t.composite_trust, risk=r.risk_score, risk_coverage=r.coverage,
                authorization_assessment=a.to_dict(),
                old_context_reference=old.reference, new_context_reference=new.reference,
                old_planning=before.to_dict(), new_planning=after.to_dict()))
    return {'seed': 42, 'events_per_run': 10,
            'baseline': 'Legacy UNKNOWN context using unchanged candidate-membership policy; references use the new context schema.',
            'rows': rows}


if __name__ == '__main__':
    print(json.dumps(replay(), sort_keys=True, indent=2, allow_nan=False))
