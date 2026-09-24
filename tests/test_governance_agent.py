from copy import deepcopy
from dataclasses import FrozenInstanceError, replace

import pytest

from agents.base_agent import BaseAgent
from agents.decision_agent import DecisionAgent
from agents.governance_agent import GOVERNANCE_POLICY_VERSION, GovernanceAgent
from agents.planning_agent import PlanningAgent
from agents.risk_agent import RiskAgent
from agents.trust_agent import TrustAgent
from core.actions import Action
from core.decision_contracts import GovernanceDecision, GovernanceStatus, ProposedDecision
from core.planning_result import PlanningResult
from core.risk_input import COMPONENTS, RiskConfig
from core.runtime_inputs import runtime_observation
from core.trust_assessment import AuditCorrelation
from environment.event_generator import EventGenerator
from evaluation.evaluate_decision_agent import inference_rows
from evaluation.evaluate_governance_agent import evaluate
from evaluation.evaluate_risk import assess_observations
from intelligence.authorization_engine import AuthorizationEngine
from intelligence.autonomous_authority_engine import AutonomousAuthorityEngine
from intelligence.decision_context_builder import build_decision_context
from intelligence.risk_input_builder import build_risk_input
from intelligence.risk_model import RiskModel


def pipeline(scenario='S2', index=4):
    return inference_rows(scenario)[index][1:]


def govern(scenario='S2', index=4):
    context, plan, proposal = pipeline(scenario, index)
    return context, plan, proposal, GovernanceAgent().review(context, plan, proposal)


def single_plan(context, candidate):
    return PlanningResult(
        candidates=(candidate,), context_fingerprint=context.reference,
        context_version=context.context_version,
        planning_policy_version=candidate.planning_policy_version,
        unresolved_constraints=('Synthetic governance test.',),
        exclusions={action.value: 'Synthetic exclusion.' for action in Action if action != candidate.action},
    )


def proposal_for(template, context, plan, candidate):
    return ProposedDecision(
        selected_action=candidate.action, selected_candidate_reference=candidate.reference,
        candidate_actions=(candidate,), primary_reason='Synthetic governance test.',
        evidence_summary=template.evidence_summary, trust_basis=template.trust_basis,
        risk_basis=template.risk_basis, uncertainty=template.uncertainty,
        policy_basis=template.policy_basis, alternatives_considered=(),
        context_reference=context.reference, decision_policy_version=template.decision_policy_version,
        planning_reference=plan.reference, planning_policy_version=plan.planning_policy_version,
    )


def synthetic_action(scenario, index, action, source_candidate=None):
    context, original_plan, template = pipeline(scenario, index)
    candidate = source_candidate or original_plan.candidates[0]
    candidate = replace(candidate, action=action, rationale=f'Synthetic {action.value} proposal.',
                        capability_reference=context.capabilities.reference)
    plan = single_plan(context, candidate)
    proposal = proposal_for(template, context, plan, candidate)
    return context, plan, proposal


def test_construction_allow_approval_determinism_and_immutability():
    context, plan, proposal, result = govern()
    agent = GovernanceAgent()
    assert isinstance(agent, BaseAgent)
    assert type(result) is GovernanceDecision
    assert result.status == GovernanceStatus.APPROVED
    assert result.authorized_action == result.proposed_action == Action.ALLOW
    assert result.authorized_payload == plan.candidates[0].payload
    assert result.authorization_reference
    assert result.governance_policy_version == GOVERNANCE_POLICY_VERSION
    assert set(result.policy_checks) == set(result.check_reasons)
    assert set(result.policy_checks.values()) == {'PASS'}
    assert result == agent.review(context, plan, proposal)
    assert result.reference == agent.review(context, plan, proposal).reference
    before = (deepcopy(context.to_dict()), deepcopy(plan.to_dict()), deepcopy(proposal.to_dict()))
    agent.review(context, plan, proposal)
    assert before == (context.to_dict(), plan.to_dict(), proposal.to_dict())
    with pytest.raises(FrozenInstanceError):
        result.reason = 'changed'
    with pytest.raises(TypeError):
        result.policy_checks['PROPOSAL_BOUND'] = 'FAIL'


@pytest.mark.parametrize('scenario,index', [('S1', 5), ('S2', 5), ('S2', 6), ('S2', 7), ('S3', 5)])
def test_request_approval_is_never_execution_approval(scenario, index):
    _, _, proposal, result = govern(scenario, index)
    assert proposal.selected_action == Action.REQUEST_APPROVAL
    assert result.status == GovernanceStatus.APPROVAL_REQUIRED
    assert result.authorized_action is None
    assert result.authorized_payload is None
    assert result.authorization_reference is None
    assert result.policy_checks['REVIEW_REQUIREMENT'] == 'UNKNOWN'


@pytest.mark.parametrize('index,mode,maximum', [(4, 'NORMAL', 80), (5, 'HIGH_OUTPUT', 95), (6, 'HIGH_OUTPUT', 95)])
def test_s5_allow_uses_bound_current_mode(index, mode, maximum):
    context, _, _, result = govern('S5', index)
    assert context.capabilities.operational_validity.operating_mode == mode
    assert context.capabilities.operational_validity.check.maximum == maximum
    assert result.status == GovernanceStatus.APPROVED
    assert result.authorized_action == Action.ALLOW


@pytest.mark.parametrize('field,value', [
    ('context_reference', 'tampered-context'),
    ('planning_reference', 'tampered-plan'),
    ('planning_policy_version', 'tampered-version'),
])
def test_binding_tampering_is_vetoed(field, value):
    context, plan, proposal = pipeline()
    result = GovernanceAgent().review(context, plan, replace(proposal, **{field: value}))
    assert result.status == GovernanceStatus.VETOED
    assert result.policy_checks['PROPOSAL_BOUND'] == 'FAIL'
    assert result.authorized_action is None


def test_plan_context_binding_tampering_is_vetoed():
    context, plan, proposal = pipeline()
    tampered = replace(plan, context_fingerprint='tampered')
    result = GovernanceAgent().review(context, tampered, proposal)
    assert result.status == GovernanceStatus.VETOED
    assert result.policy_checks['PROPOSAL_BOUND'] == 'FAIL'


def test_proposal_candidate_set_not_in_plan_is_vetoed():
    context, plan, proposal = pipeline()
    allow = next(candidate for candidate in proposal.candidate_actions if candidate.action == Action.ALLOW)
    tampered = replace(proposal, candidate_actions=(allow,), alternatives_considered=())
    result = GovernanceAgent().review(context, plan, tampered)
    assert result.status == GovernanceStatus.VETOED
    assert result.policy_checks['PROPOSAL_BOUND'] == 'FAIL'


def test_candidate_capability_binding_mismatch_is_vetoed():
    context, original_plan, template = pipeline()
    candidate = replace(original_plan.candidates[0], capability_reference='tampered-capability')
    plan = single_plan(context, candidate)
    proposal = proposal_for(template, context, plan, candidate)
    result = GovernanceAgent().review(context, plan, proposal)
    assert result.status == GovernanceStatus.VETOED
    assert result.policy_checks['PLANNER_CANDIDATE'] == 'FAIL'


def test_unknown_authorization_allow_is_not_approved():
    context, plan, proposal = synthetic_action('S3', 5, Action.ALLOW)
    result = GovernanceAgent().review(context, plan, proposal)
    assert context.authorization_status == 'UNKNOWN'
    assert result.status == GovernanceStatus.VETOED
    assert result.policy_checks['AUTHORIZATION_VALID'] == 'UNKNOWN'
    assert result.policy_checks['AUTHORITY_VALID'] == 'FAIL'


def test_outside_limit_allow_is_not_approved():
    outside_context, _, template = pipeline('S2', 5)
    routine_candidate = pipeline('S2', 4)[1].candidates[0]
    payload = dict(routine_candidate.to_dict()['payload'])
    payload.update(
        source_id=outside_context.source_id,
        target_id=outside_context.target_id,
        operation=outside_context.observation['operation'],
        requested_value=outside_context.observation['requested_value'],
        operating_mode=outside_context.capabilities.operational_validity.operating_mode,
    )
    candidate = replace(routine_candidate, payload=payload,
                        capability_reference=outside_context.capabilities.reference)
    plan = single_plan(outside_context, candidate)
    proposal = proposal_for(template, outside_context, plan, candidate)
    result = GovernanceAgent().review(outside_context, plan, proposal)
    assert result.status == GovernanceStatus.VETOED
    assert result.policy_checks['OPERATIONAL_VALIDITY'] == 'FAIL'
    assert result.policy_checks['AUTHORITY_VALID'] == 'FAIL'


def test_null_limit_transformation_requires_approval():
    context, plan, template = pipeline('S2', 5)
    limit = next(candidate for candidate in plan.candidates if candidate.action == Action.LIMIT)
    proposal = ProposedDecision(
        selected_action=Action.LIMIT, selected_candidate_reference=limit.reference,
        candidate_actions=plan.candidates, primary_reason='Synthetic LIMIT proposal.',
        evidence_summary=template.evidence_summary, trust_basis=template.trust_basis,
        risk_basis=template.risk_basis, uncertainty=template.uncertainty,
        policy_basis=template.policy_basis,
        alternatives_considered=('REQUEST_APPROVAL remains available.',),
        context_reference=context.reference, decision_policy_version=template.decision_policy_version,
        planning_reference=plan.reference, planning_policy_version=plan.planning_policy_version,
    )
    result = GovernanceAgent().review(context, plan, proposal)
    assert limit.payload['replacement_value'] is None and limit.requires_approval
    assert result.status == GovernanceStatus.APPROVAL_REQUIRED
    assert result.policy_checks['ACTION_PAYLOAD_COMPLETE'] == 'UNKNOWN'
    assert result.authorized_action is None


def test_future_complete_limit_can_be_approved_without_value_invention():
    context, original_plan, template = pipeline('S2', 5)
    limit = next(candidate for candidate in original_plan.candidates if candidate.action == Action.LIMIT)
    payload = dict(limit.to_dict()['payload'])
    payload['replacement_value'] = 80
    candidate = replace(
        limit, payload=payload, requires_approval=False,
        unresolved_prerequisites=('Governance and future executor revalidation remain required.',),
    )
    plan = single_plan(context, candidate)
    proposal = proposal_for(template, context, plan, candidate)
    result = GovernanceAgent().review(context, plan, proposal)
    assert result.status == GovernanceStatus.APPROVED
    assert result.authorized_action == Action.LIMIT
    assert result.authorized_payload['replacement_value'] == 80


def test_monitor_logical_candidate_can_be_approved_without_claiming_execution():
    context, plan, template = pipeline('S2', 4)
    monitor = next(candidate for candidate in plan.candidates if candidate.action == Action.MONITOR)
    proposal = replace(template, selected_action=Action.MONITOR,
                       selected_candidate_reference=monitor.reference,
                       primary_reason='Synthetic MONITOR proposal.',
                       alternatives_considered=('ALLOW remains available.',))
    result = GovernanceAgent().review(context, plan, proposal)
    assert result.status == GovernanceStatus.APPROVED
    assert result.authorized_action == Action.MONITOR
    assert result.authorized_payload['monitoring_mode'] == 'LOGICAL_ONLY'
    assert 'executor capability' in result.check_reasons['EXECUTION_PREREQUISITES']


@pytest.mark.parametrize('action', [Action.BLOCK, Action.ISOLATE])
def test_unsupported_actions_are_vetoed(action):
    context, plan, proposal = synthetic_action('S2', 4, action)
    result = GovernanceAgent().review(context, plan, proposal)
    assert result.status == GovernanceStatus.VETOED
    assert result.authorized_action is None
    assert result.policy_checks['AUTHORITY_VALID'] == 'FAIL'
    assert result.policy_checks['POLICY_CONFLICT'] == 'FAIL'


def test_empty_no_decision_is_fail_closed_veto():
    context, _, template = pipeline()
    plan = PlanningResult(
        candidates=(), context_fingerprint=context.reference,
        context_version=context.context_version, planning_policy_version='day4c-planning-v1',
        unresolved_constraints=('No candidates.',),
        exclusions={action.value: 'Unavailable.' for action in Action},
    )
    proposal = replace(
        template, selected_action=None, selected_candidate_reference=None,
        candidate_actions=(), alternatives_considered=(), planning_reference=plan.reference,
        planning_policy_version=plan.planning_policy_version,
    )
    result = GovernanceAgent().review(context, plan, proposal)
    assert result.status == GovernanceStatus.VETOED
    assert result.proposed_action is None and result.authorized_action is None


def test_no_override_is_emitted():
    for scenario in (f'S{i}' for i in range(1, 7)):
        for _, context, plan, proposal in inference_rows(scenario):
            result = GovernanceAgent().review(context, plan, proposal)
            assert result.status != GovernanceStatus.OVERRIDDEN
            assert result.authorized_action in (None, proposal.selected_action)


def _context_with_scores(trust_score, risk_weights):
    events = EventGenerator(42, observable_state=True).generate('S2', 10)
    trusts, _ = assess_observations(events, TrustAgent(), RiskAgent())
    event, trust = events[4], trusts[4]
    observation = runtime_observation(event)
    trust = replace(trust, composite_trust=trust_score,
                    trust_delta=trust_score - trust.previous_composite_trust)
    config = RiskConfig(dict(zip(COMPONENTS, risk_weights)))
    risk = RiskModel().evaluate(build_risk_input(observation, trust, config=config))
    auth_engine, authority_engine = AuthorizationEngine(), AutonomousAuthorityEngine()
    authorization = auth_engine.assess(observation)
    base = build_decision_context(observation, trust, risk, authorization,
                                  permission_policy=auth_engine.policy)
    authority = authority_engine.assess(base)
    context = build_decision_context(
        observation, trust, risk, authorization, permission_policy=auth_engine.policy,
        autonomous_authority_assessment=authority, authority_policy=authority_engine.policy)
    plan = PlanningAgent().plan(context)
    proposal = DecisionAgent().decide(context, plan)
    return context, plan, proposal


@pytest.mark.parametrize('trust_score,risk_weights', [
    (0.0, (0, 1, 0, 0)), (1.0, (0, 0, 1, 0)), (.25, (1, 0, 0, 0)),
])
def test_score_independence(trust_score, risk_weights):
    context, plan, proposal = _context_with_scores(trust_score, risk_weights)
    result = GovernanceAgent().review(context, plan, proposal)
    assert proposal.selected_action == Action.ALLOW
    assert result.status == GovernanceStatus.APPROVED
    assert 'no score threshold applied' in result.reason


@pytest.mark.parametrize('scenario', [f'S{i}' for i in range(1, 7)])
def test_leakage_and_audit_isolation(scenario):
    events = EventGenerator(42, observable_state=True).generate(scenario, 10)
    trusts, risks = assess_observations(events, TrustAgent(), RiskAgent())

    def infer(event, trust, risk, audit=None):
        observation = runtime_observation(event)
        auth_engine, authority_engine = AuthorizationEngine(), AutonomousAuthorityEngine()
        authorization = auth_engine.assess(observation)
        if audit is not None:
            trust, risk = replace(trust, audit=audit), replace(risk, audit=audit)
        base = build_decision_context(observation, trust, risk, authorization,
                                      permission_policy=auth_engine.policy)
        authority = authority_engine.assess(base)
        context = build_decision_context(
            observation, trust, risk, authorization, permission_policy=auth_engine.policy,
            autonomous_authority_assessment=authority, authority_policy=authority_engine.policy)
        plan = PlanningAgent().plan(context)
        proposal = DecisionAgent().decide(context, plan)
        return GovernanceAgent().review(context, plan, proposal).to_dict()

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


def test_fingerprint_changes_on_tampering_and_contract_reasons_bind():
    context, plan, proposal, result = govern()
    tampered = GovernanceAgent().review(context, plan, replace(proposal, context_reference='tampered'))
    assert result.reference != tampered.reference
    assert set(result.check_reasons) == set(result.policy_checks)
    with pytest.raises(ValueError):
        replace(result, check_reasons={'OTHER': 'wrong keys'})


def test_evaluation_structural_metrics_are_repeatable():
    first = evaluate()
    assert first == evaluate()
    assert first['total_reviews'] == 300
    assert sum(first['governance_distribution'].values()) == 300
    metrics = first['structural_metrics']
    assert metrics['binding_failure_prevention']['prevented'] == 2
    assert metrics['unsupported_action_prevention']['prevented'] == 2
