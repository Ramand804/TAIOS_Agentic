from copy import deepcopy
from dataclasses import FrozenInstanceError, replace

import pytest

from agents.base_agent import BaseAgent
from agents.decision_agent import DecisionAgent
from agents.execution_agent import EXECUTION_POLICY_VERSION, ExecutionAgent
from agents.governance_agent import GovernanceAgent
from agents.planning_agent import PlanningAgent
from agents.risk_agent import RiskAgent
from agents.trust_agent import TrustAgent
from core.actions import Action
from core.decision_contracts import (
    ExecutionResult, ExecutionStatus, GovernanceDecision, GovernanceStatus,
    ProposedDecision,
)
from core.planning_result import PlanningResult
from core.runtime_inputs import runtime_observation
from core.trust_assessment import AuditCorrelation
from environment.event_generator import EventGenerator
from environment.industrial_environment import IndustrialState, OperatingMode
from evaluation.evaluate_risk import assess_observations
from intelligence.authorization_engine import AuthorizationEngine
from intelligence.autonomous_authority_engine import AutonomousAuthorityEngine
from intelligence.decision_context_builder import build_decision_context


def state_for_event(event):
    state = IndustrialState()
    mode = event.contextual_features.get('operating_mode', 'NORMAL')
    if mode != state.operating_mode.value:
        state.set_operating_mode(mode)
    return state


def pipeline(scenario='S2', index=4, state=None):
    events = EventGenerator(42, observable_state=True).generate(scenario, 10)
    trusts, risks = assess_observations(events, TrustAgent(), RiskAgent())
    event = events[index]
    state = state or state_for_event(event)
    observation = runtime_observation(event)
    auth_engine, authority_engine = AuthorizationEngine(), AutonomousAuthorityEngine()
    authorization = auth_engine.assess(observation)
    base = build_decision_context(
        observation, trusts[index], risks[index], authorization,
        permission_policy=auth_engine.policy, industrial_state=state)
    authority = authority_engine.assess(base)
    context = build_decision_context(
        observation, trusts[index], risks[index], authorization,
        permission_policy=auth_engine.policy,
        autonomous_authority_assessment=authority,
        authority_policy=authority_engine.policy,
        industrial_state=state)
    plan = PlanningAgent().plan(context)
    proposal = DecisionAgent().decide(context, plan)
    governance = GovernanceAgent().review(context, plan, proposal)
    return event, context, plan, proposal, governance, state


def complete_limit_pipeline(replacement_value=80):
    event, context, original_plan, template, _, state = pipeline('S2', 5)
    limit = next(candidate for candidate in original_plan.candidates if candidate.action == Action.LIMIT)
    payload = dict(limit.to_dict()['payload'])
    payload['replacement_value'] = replacement_value
    candidate = replace(
        limit, payload=payload, requires_approval=False,
        unresolved_prerequisites=('Governance and future executor revalidation remain required.',))
    plan = PlanningResult(
        candidates=(candidate,), context_fingerprint=context.reference,
        context_version=context.context_version,
        planning_policy_version=candidate.planning_policy_version,
        unresolved_constraints=('Synthetic complete LIMIT fixture.',),
        exclusions={action.value: 'Synthetic exclusion.' for action in Action if action != Action.LIMIT})
    proposal = ProposedDecision(
        selected_action=Action.LIMIT, selected_candidate_reference=candidate.reference,
        candidate_actions=(candidate,), primary_reason='Synthetic complete LIMIT fixture.',
        evidence_summary=template.evidence_summary, trust_basis=template.trust_basis,
        risk_basis=template.risk_basis, uncertainty=template.uncertainty,
        policy_basis=template.policy_basis, alternatives_considered=(),
        context_reference=context.reference, decision_policy_version=template.decision_policy_version,
        planning_reference=plan.reference, planning_policy_version=plan.planning_policy_version)
    governance = GovernanceAgent().review(context, plan, proposal)
    return event, context, plan, proposal, governance, state


def test_construction_allow_executes_on_clone_and_preserves_unrelated_assets():
    _, context, plan, proposal, governance, state = pipeline()
    agent = ExecutionAgent()
    assert isinstance(agent, BaseAgent)
    before = deepcopy(state.to_dict())
    result = agent.execute(context, plan, proposal, governance, state)
    assert type(result) is ExecutionResult
    assert result.execution_status == ExecutionStatus.SUCCEEDED
    assert result.authorized_action == Action.ALLOW
    assert result.applied_value == context.observation['requested_value'] == 48
    assert result.state_version_before == 0 and result.state_version_after == 1
    assert result.mutation_applied and not result.idempotent_replay
    assert result.resulting_state.asset_states['MOTOR-02'].current_value == 48
    assert result.resulting_state.asset_states['MOTOR-02'].last_operation == 'set_speed'
    for asset_id in state.asset_states:
        if asset_id != 'MOTOR-02':
            assert result.resulting_state.asset_states[asset_id] == state.asset_states[asset_id]
    assert state.to_dict() == before
    assert result.execution_policy_version == EXECUTION_POLICY_VERSION
    with pytest.raises(FrozenInstanceError):
        result.reason = 'changed'


@pytest.mark.parametrize('scenario,index', [('S1', 5), ('S2', 5), ('S2', 6), ('S2', 7), ('S3', 5)])
def test_approval_required_is_safe_gated_non_execution(scenario, index):
    _, context, plan, proposal, governance, state = pipeline(scenario, index)
    before = state.to_dict()
    result = ExecutionAgent().execute(context, plan, proposal, governance, state)
    assert governance.status == GovernanceStatus.APPROVAL_REQUIRED
    assert result.execution_status == ExecutionStatus.PENDING_APPROVAL
    assert not result.mutation_applied
    assert result.state_version_before == result.state_version_after == state.state_version
    assert result.resulting_state.to_dict() == before == state.to_dict()


def test_vetoed_is_rejected_without_mutation():
    _, context, plan, proposal, governance, state = pipeline()
    veto = replace(governance, status='VETOED', authorized_action=None,
                   authorized_payload=None, authorization_reference=None)
    result = ExecutionAgent().execute(context, plan, proposal, veto, state)
    assert result.execution_status == ExecutionStatus.REJECTED
    assert not result.mutation_applied
    assert result.resulting_state.to_dict() == state.to_dict()


def test_complete_approved_limit_executes_exact_value():
    _, context, plan, proposal, governance, state = complete_limit_pipeline(80)
    assert governance.status == GovernanceStatus.APPROVED
    result = ExecutionAgent().execute(context, plan, proposal, governance, state)
    assert result.execution_status == ExecutionStatus.SUCCEEDED
    assert result.authorized_action == Action.LIMIT
    assert result.requested_value == 97 and result.applied_value == 80
    assert result.resulting_state.asset_states['MOTOR-02'].current_value == 80
    assert result.state_version_before == 0 and result.state_version_after == 1


def test_s5_high_output_allow_executes_against_current_mode():
    _, context, plan, proposal, governance, state = pipeline('S5', 5)
    result = ExecutionAgent().execute(context, plan, proposal, governance, state)
    check = context.capabilities.operational_validity.check
    assert state.operating_mode == OperatingMode.HIGH_OUTPUT
    assert (check.minimum, check.maximum) == (60, 95)
    assert result.execution_status == ExecutionStatus.SUCCEEDED
    assert result.applied_value == 85


def test_monitor_is_logical_only_and_never_mutates_industrial_state():
    _, context, plan, template, _, state = pipeline()
    monitor = next(candidate for candidate in plan.candidates if candidate.action == Action.MONITOR)
    proposal = replace(
        template, selected_action=Action.MONITOR,
        selected_candidate_reference=monitor.reference,
        primary_reason='Synthetic logical monitoring fixture.')
    governance = GovernanceAgent().review(context, plan, proposal)
    result = ExecutionAgent().execute(context, plan, proposal, governance, state)
    assert governance.status == GovernanceStatus.APPROVED
    assert result.execution_status == ExecutionStatus.UNSUPPORTED
    assert not result.mutation_applied
    assert result.resulting_state.to_dict() == state.to_dict()


@pytest.mark.parametrize('action', [Action.BLOCK, Action.ISOLATE])
def test_unsupported_physical_action_injection_never_mutates(action):
    _, context, plan, proposal, governance, state = pipeline()
    fabricated = replace(
        governance, proposed_action=action, authorized_action=action,
        authorization_reference='fabricated')
    result = ExecutionAgent().execute(context, plan, proposal, fabricated, state)
    assert result.execution_status == ExecutionStatus.REJECTED
    assert not result.mutation_applied
    assert result.resulting_state.to_dict() == state.to_dict()


def test_incomplete_limit_never_invents_replacement():
    _, context, plan, template, _, state = pipeline('S2', 5)
    limit = next(candidate for candidate in plan.candidates if candidate.action == Action.LIMIT)
    proposal = replace(template, selected_action=Action.LIMIT,
                       selected_candidate_reference=limit.reference,
                       primary_reason='Synthetic incomplete LIMIT.',
                       alternatives_considered=('REQUEST_APPROVAL remains available.',))
    governance = GovernanceAgent().review(context, plan, proposal)
    result = ExecutionAgent().execute(context, plan, proposal, governance, state)
    assert governance.status == GovernanceStatus.APPROVAL_REQUIRED
    assert result.execution_status == ExecutionStatus.PENDING_APPROVAL
    assert result.applied_value is None
    assert result.resulting_state.to_dict() == state.to_dict()


@pytest.mark.parametrize('tamper', ['proposal_action', 'proposal_payload', 'target', 'operation',
                                    'authorization_reference', 'plan', 'context'])
def test_tampering_after_governance_fails_closed(tamper):
    _, context, plan, proposal, governance, state = pipeline()
    supplied_context, supplied_plan, supplied_proposal, supplied_governance = context, plan, proposal, governance
    if tamper == 'proposal_action':
        monitor = next(candidate for candidate in plan.candidates if candidate.action == Action.MONITOR)
        supplied_proposal = replace(proposal, selected_action=Action.MONITOR,
                                    selected_candidate_reference=monitor.reference)
    elif tamper in ('proposal_payload', 'target', 'operation'):
        selected = proposal.candidate_actions[0]
        payload = dict(selected.to_dict()['payload'])
        key, value = {'proposal_payload': ('requested_value', 49),
                      'target': ('target_id', 'PUMP-01'),
                      'operation': ('operation', 'write_register')}[tamper]
        payload[key] = value
        changed = replace(selected, payload=payload)
        supplied_proposal = replace(proposal, candidate_actions=(changed, proposal.candidate_actions[1]),
                                    selected_candidate_reference=changed.reference)
    elif tamper == 'authorization_reference':
        supplied_governance = replace(governance, authorization_reference='fabricated')
    elif tamper == 'plan':
        supplied_plan = replace(plan, context_fingerprint='other-context')
    else:
        supplied_context = pipeline('S5', 4)[1]
    result = ExecutionAgent().execute(
        supplied_context, supplied_plan, supplied_proposal, supplied_governance, state)
    assert result.execution_status == ExecutionStatus.REJECTED
    assert not result.mutation_applied
    assert result.resulting_state.to_dict() == state.to_dict()


def test_fabricated_approved_governance_is_rejected():
    _, context, plan, proposal, governance, state = pipeline('S1', 5)
    candidate = plan.candidates[0]
    fabricated = GovernanceDecision(
        status='APPROVED', proposed_action=candidate.action,
        authorized_action=candidate.action, authorized_payload=candidate.payload,
        policy_checks={key: 'PASS' for key in governance.policy_checks},
        check_reasons={key: 'Fabricated pass.' for key in governance.policy_checks},
        violations=(), reason='Fabricated approval.', context_reference=context.reference,
        proposal_reference=proposal.reference, authorization_reference='fabricated',
        governance_policy_version=governance.governance_policy_version)
    result = ExecutionAgent().execute(context, plan, proposal, fabricated, state)
    assert result.execution_status == ExecutionStatus.REJECTED
    assert not result.mutation_applied


def test_stale_state_version_and_mode_fail_closed():
    _, context, plan, proposal, governance, state = pipeline()
    stale = replace(state)
    stale.set_maintenance_mode(True)
    result = ExecutionAgent().execute(context, plan, proposal, governance, stale)
    assert result.execution_status == ExecutionStatus.STALE_STATE
    assert result.state_version_before == result.state_version_after == 1
    assert result.resulting_state.to_dict() == stale.to_dict()
    changed_mode = replace(state)
    changed_mode.set_operating_mode(OperatingMode.HIGH_OUTPUT)
    result = ExecutionAgent().execute(context, plan, proposal, governance, changed_mode)
    assert result.execution_status == ExecutionStatus.STALE_STATE
    assert not result.mutation_applied


def test_idempotent_replay_does_not_mutate_twice():
    _, context, plan, proposal, governance, state = pipeline()
    agent = ExecutionAgent()
    first = agent.execute(context, plan, proposal, governance, state)
    second = agent.execute(context, plan, proposal, governance, first.resulting_state)
    assert first.execution_status == ExecutionStatus.SUCCEEDED
    assert second.execution_status == ExecutionStatus.ALREADY_EXECUTED
    assert first.execution_id == second.execution_id
    assert not second.mutation_applied and second.idempotent_replay
    assert second.state_version_before == second.state_version_after == 1
    assert second.resulting_state.to_dict() == first.resulting_state.to_dict()


def test_distinct_authorizations_are_not_duplicate():
    agent = ExecutionAgent()
    first_args = pipeline('S2', 4)
    second_args = pipeline('S5', 4)
    first = agent.execute(*first_args[1:5], first_args[5])
    second = agent.execute(*second_args[1:5], second_args[5])
    assert first.execution_status == second.execution_status == ExecutionStatus.SUCCEEDED
    assert first.execution_id != second.execution_id


def test_success_without_effective_change_is_distinguished_from_mutation():
    events = EventGenerator(42, observable_state=True).generate('S2', 10)
    value = events[4].requested_value
    state = IndustrialState()
    state.update_asset_state('MOTOR-02', current_value=value, last_operation='set_speed')
    _, context, plan, proposal, governance, state = pipeline('S2', 4, state)
    result = ExecutionAgent().execute(context, plan, proposal, governance, state)
    assert result.execution_status == ExecutionStatus.SUCCEEDED
    assert not result.mutation_applied
    assert result.state_version_before == result.state_version_after == 1


def test_deterministic_fresh_agents_same_result_and_state():
    _, context, plan, proposal, governance, state = pipeline()
    first = ExecutionAgent().execute(context, plan, proposal, governance, state)
    second = ExecutionAgent().execute(context, plan, proposal, governance, state)
    assert first.to_dict() == second.to_dict()
    assert first.reference == second.reference
    assert first.resulting_state.to_dict() == second.resulting_state.to_dict()


def test_upstream_artifacts_remain_structurally_unchanged():
    _, context, plan, proposal, governance, state = pipeline()
    snapshots = tuple(item.to_dict() for item in (context, plan, proposal, governance))
    ExecutionAgent().execute(context, plan, proposal, governance, state)
    assert snapshots == tuple(item.to_dict() for item in (context, plan, proposal, governance))


@pytest.mark.parametrize('scenario', [f'S{i}' for i in range(1, 7)])
def test_leakage_and_audit_isolation(scenario):
    events = EventGenerator(42, observable_state=True).generate(scenario, 10)
    trusts, risks = assess_observations(events, TrustAgent(), RiskAgent())

    def infer(event, trust, risk, audit=None):
        state = state_for_event(event)
        observation = runtime_observation(event)
        auth_engine, authority_engine = AuthorizationEngine(), AutonomousAuthorityEngine()
        authorization = auth_engine.assess(observation)
        if audit is not None:
            trust, risk = replace(trust, audit=audit), replace(risk, audit=audit)
        base = build_decision_context(observation, trust, risk, authorization,
                                      permission_policy=auth_engine.policy, industrial_state=state)
        authority = authority_engine.assess(base)
        context = build_decision_context(
            observation, trust, risk, authorization, permission_policy=auth_engine.policy,
            autonomous_authority_assessment=authority, authority_policy=authority_engine.policy,
            industrial_state=state)
        plan = PlanningAgent().plan(context)
        proposal = DecisionAgent().decide(context, plan)
        governance = GovernanceAgent().review(context, plan, proposal)
        return ExecutionAgent().execute(context, plan, proposal, governance, state).to_dict()

    before = [infer(event, trust, risk) for event, trust, risk in zip(events, trusts, risks)]
    for event in events:
        event.ground_truth = 'SUSPICIOUS'
        event.expected_safe_action = 'ISOLATE'
        event.scenario_id = 'OTHER'
        event.provenance = replace(event.provenance, phase='OTHER', transition_type='OTHER', causal_tags=('OTHER',))
        event.contextual_features.update(anomaly_score=999, simulated_attack_probability=-999,
                                         transition=999, compromise_phase=True, causal_tags=['OTHER'])
    changed_trusts, changed_risks = assess_observations(events, TrustAgent(), RiskAgent())
    audit = AuditCorrelation('changed-audit', 999)
    after = [infer(event, trust, risk, audit) for event, trust, risk in zip(events, changed_trusts, changed_risks)]
    assert before == after
