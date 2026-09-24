"""Structural deterministic execution diagnostics; no evaluator-label join."""
import json
from collections import Counter
from dataclasses import replace

from agents.decision_agent import DecisionAgent
from agents.execution_agent import ExecutionAgent
from agents.governance_agent import GovernanceAgent
from agents.planning_agent import PlanningAgent
from agents.risk_agent import RiskAgent
from agents.trust_agent import TrustAgent
from core.actions import Action
from core.decision_contracts import ExecutionStatus
from core.decision_contracts import ProposedDecision
from core.planning_result import PlanningResult
from core.runtime_inputs import runtime_observation
from environment.event_generator import EventGenerator
from environment.industrial_environment import IndustrialState
from evaluation.evaluate_decision_agent import DIAGNOSTICS, SCENARIOS, SEEDS
from evaluation.evaluate_risk import assess_observations
from intelligence.authorization_engine import AuthorizationEngine
from intelligence.autonomous_authority_engine import AutonomousAuthorityEngine
from intelligence.decision_context_builder import build_decision_context


def _state_for(event):
    state = IndustrialState()
    state.set_operating_mode(event.contextual_features.get('operating_mode', 'NORMAL'))
    return state


def inference_rows(scenario, seed=42, n=10):
    events = EventGenerator(seed, observable_state=True).generate(scenario, n)
    trusts, risks = assess_observations(events, TrustAgent(), RiskAgent())
    rows = []
    for event, trust, risk in zip(events, trusts, risks):
        state = _state_for(event)
        observation = runtime_observation(event)
        authorization_engine = AuthorizationEngine()
        authority_engine = AutonomousAuthorityEngine()
        authorization = authorization_engine.assess(observation)
        base = build_decision_context(
            observation, trust, risk, authorization,
            permission_policy=authorization_engine.policy, industrial_state=state)
        authority = authority_engine.assess(base)
        context = build_decision_context(
            observation, trust, risk, authorization,
            permission_policy=authorization_engine.policy,
            autonomous_authority_assessment=authority,
            authority_policy=authority_engine.policy, industrial_state=state)
        plan = PlanningAgent().plan(context)
        proposal = DecisionAgent().decide(context, plan)
        governance = GovernanceAgent().review(context, plan, proposal)
        rows.append((event, context, plan, proposal, governance, state))
    return rows


def _row(event, context, proposal, governance, result):
    validity = context.capabilities.operational_validity.check
    return {
        'scenario': event.scenario_id,
        'sequence': event.sequence_number,
        'proposal': proposal.selected_action.value,
        'governance_status': governance.status.value,
        'authorized_action': (governance.authorized_action.value
                              if governance.authorized_action is not None else None),
        'execution_status': result.execution_status.value,
        'requested_value': result.requested_value,
        'executed_value': result.applied_value,
        'state_before_reference': result.state_before_reference,
        'state_after_reference': result.state_after_reference,
        'state_version_before': result.state_version_before,
        'state_version_after': result.state_version_after,
        'operating_mode': context.observation['contextual_features']['operating_mode'],
        'operational_range': ([validity.minimum, validity.maximum] if validity else None),
        'mutation_applied': result.mutation_applied,
        'reason': result.reason,
        'execution_reference': result.execution_id,
    }


def _complete_limit_probe():
    event, context, original_plan, template, _, state = inference_rows('S2')[5]
    limit = next(candidate for candidate in original_plan.candidates
                 if candidate.action == Action.LIMIT)
    payload = dict(limit.to_dict()['payload'])
    payload['replacement_value'] = payload['allowed_max']
    candidate = replace(
        limit, payload=payload, requires_approval=False,
        unresolved_prerequisites=(
            'Governance and future executor revalidation remain required.',))
    plan = PlanningResult(
        candidates=(candidate,), context_fingerprint=context.reference,
        context_version=context.context_version,
        planning_policy_version=candidate.planning_policy_version,
        unresolved_constraints=('Synthetic complete LIMIT execution probe.',),
        exclusions={action.value: 'Excluded by synthetic execution probe.'
                    for action in Action if action != Action.LIMIT})
    proposal = ProposedDecision(
        selected_action=Action.LIMIT,
        selected_candidate_reference=candidate.reference,
        candidate_actions=(candidate,),
        primary_reason='Synthetic complete LIMIT execution probe.',
        evidence_summary=template.evidence_summary,
        trust_basis=template.trust_basis, risk_basis=template.risk_basis,
        uncertainty=template.uncertainty, policy_basis=template.policy_basis,
        alternatives_considered=(), context_reference=context.reference,
        decision_policy_version=template.decision_policy_version,
        planning_reference=plan.reference,
        planning_policy_version=plan.planning_policy_version)
    governance = GovernanceAgent().review(context, plan, proposal)
    result = ExecutionAgent().execute(context, plan, proposal, governance, state)
    return _row(event, context, proposal, governance, result)


def evaluate(events_per_run=10):
    statuses = Counter()
    approved = successful = mutations = no_mutation = 0
    prevented_unauthorized = 0
    diagnostics = []
    replay_probe = stale_probe = tamper_probe = None
    for seed in SEEDS:
        for scenario in SCENARIOS:
            for event, context, plan, proposal, governance, state in inference_rows(
                    scenario, seed, events_per_run):
                result = ExecutionAgent().execute(context, plan, proposal, governance, state)
                statuses[result.execution_status.value] += 1
                approved += governance.status.value == 'APPROVED'
                successful += result.execution_status == ExecutionStatus.SUCCEEDED
                mutations += result.mutation_applied
                no_mutation += not result.mutation_applied
                prevented_unauthorized += (
                    governance.status.value != 'APPROVED' and not result.mutation_applied)
                if seed == 42 and event.sequence_number in DIAGNOSTICS.get(scenario, ()):
                    diagnostics.append(_row(event, context, proposal, governance, result))
                if seed == 42 and scenario == 'S2' and event.sequence_number == 5:
                    agent = ExecutionAgent()
                    first = agent.execute(context, plan, proposal, governance, state)
                    replay = agent.execute(
                        context, plan, proposal, governance, first.resulting_state)
                    replay_probe = _row(event, context, proposal, governance, replay)
                    stale_state = replace(state)
                    stale_state.set_maintenance_mode(True)
                    stale = ExecutionAgent().execute(
                        context, plan, proposal, governance, stale_state)
                    stale_probe = _row(event, context, proposal, governance, stale)
                    tampered = replace(governance, authorization_reference='fabricated')
                    tamper = ExecutionAgent().execute(
                        context, plan, proposal, tampered, state)
                    tamper_probe = _row(event, context, proposal, tampered, tamper)
    diagnostics.sort(key=lambda row: (row['scenario'], row['sequence']))
    labels = tuple(status.value for status in ExecutionStatus)
    return {
        'seeds': list(SEEDS), 'scenarios': list(SCENARIOS),
        'events_per_run': events_per_run,
        'total_executions': sum(statuses.values()),
        'execution_distribution': {label: statuses[label] for label in labels},
        'state_mutation_metrics': {
            'approved_actions': approved,
            'successful_executions': successful,
            'prevented_unauthorized_executions': prevented_unauthorized,
            'stale_approvals_prevented': int(
                stale_probe['execution_status'] == 'STALE_STATE'),
            'duplicate_executions_prevented': int(
                replay_probe['execution_status'] == 'ALREADY_EXECUTED'),
            'state_mutations': mutations,
            'no_mutation_outcomes': no_mutation,
            'interpretation': 'Structural execution behavior only; not security effectiveness.',
        },
        'diagnostics': diagnostics,
        'stale_approval_probe': stale_probe,
        'duplicate_execution_probe': replay_probe,
        'tampered_authorization_probe': tamper_probe,
        'complete_limit_probe': _complete_limit_probe(),
    }


if __name__ == '__main__':
    print(json.dumps(evaluate(), sort_keys=True, indent=2, allow_nan=False))
