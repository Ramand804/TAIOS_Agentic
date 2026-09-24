from copy import deepcopy
from dataclasses import FrozenInstanceError, replace

import pytest

from agents.base_agent import BaseAgent
from agents.decision_agent import DECISION_POLICY_VERSION, DecisionAgent
from agents.planning_agent import PlanningAgent
from agents.risk_agent import RiskAgent
from agents.trust_agent import TrustAgent
from core.actions import Action
from core.decision_contracts import ProposedDecision
from core.planning_result import PlanningResult
from core.risk_input import COMPONENTS, RiskConfig
from core.runtime_inputs import runtime_observation
from core.trust_assessment import AuditCorrelation
from environment.event_generator import EventGenerator
from evaluation.evaluate_decision_agent import evaluate, inference_rows
from evaluation.evaluate_risk import assess_observations
from intelligence.authorization_engine import AuthorizationEngine
from intelligence.autonomous_authority_engine import AutonomousAuthorityEngine
from intelligence.decision_context_builder import build_decision_context
from intelligence.risk_input_builder import build_risk_input
from intelligence.risk_model import RiskModel


def pipeline(scenario='S2', index=4):
    return inference_rows(scenario)[index][1:]


def empty_plan(context):
    return PlanningResult(
        candidates=(), context_fingerprint=context.reference,
        context_version=context.context_version, planning_policy_version='day4c-planning-v1',
        unresolved_constraints=('No candidate satisfies current prerequisites.',),
        exclusions={action.value: 'Unavailable in test fixture.' for action in Action},
    )


def test_construction_binding_determinism_and_immutability():
    context, plan, expected = pipeline()
    agent = DecisionAgent()
    assert isinstance(agent, BaseAgent)
    before_context, before_plan = deepcopy(context.to_dict()), deepcopy(plan.to_dict())
    result = agent.decide(context, plan)
    assert type(result) is ProposedDecision
    assert result == expected == DecisionAgent().decide(context, plan)
    assert result.decision_policy_version == DECISION_POLICY_VERSION
    assert result.context_reference == context.reference
    assert result.planning_reference == plan.reference
    assert result.planning_policy_version == plan.planning_policy_version
    assert result.reference == DecisionAgent().decide(context, plan).reference
    assert context.to_dict() == before_context and plan.to_dict() == before_plan
    with pytest.raises(FrozenInstanceError):
        result.primary_reason = 'changed'


def test_fingerprint_changes_with_context_candidates_or_proposal():
    _, plan, decision = pipeline()
    monitor = next(candidate for candidate in plan.candidates if candidate.action == Action.MONITOR)
    changed_action = replace(
        decision, selected_action=Action.MONITOR,
        selected_candidate_reference=monitor.reference,
        primary_reason='Test-only alternate proposal.',
    )
    allow = next(candidate for candidate in plan.candidates if candidate.action == Action.ALLOW)
    changed_candidates = replace(
        decision, candidate_actions=(allow,), alternatives_considered=(),
    )
    changed_context = replace(decision, context_reference='different-context')
    assert len({decision.reference, changed_action.reference,
                changed_candidates.reference, changed_context.reference}) == 4
    with pytest.raises(ValueError):
        replace(decision, planning_reference=None)


def test_single_candidate_and_unknown_authorization():
    for scenario in ('S1', 'S3'):
        context, plan, decision = pipeline(scenario, 5)
        assert context.authorization_status == 'UNKNOWN'
        assert tuple(candidate.action for candidate in plan.candidates) == (Action.REQUEST_APPROVAL,)
        assert decision.selected_action == Action.REQUEST_APPROVAL
        assert decision.alternatives_considered == ()
        assert 'only admissible candidate' in decision.primary_reason


def test_routine_allow_monitor_selects_allow_and_retains_alternative():
    context, plan, decision = pipeline('S2', 4)
    assert tuple(candidate.action for candidate in plan.candidates) == (Action.ALLOW, Action.MONITOR)
    assert decision.selected_action == Action.ALLOW
    assert decision.selected_candidate_reference == plan.candidates[0].reference
    assert len(decision.alternatives_considered) == 1
    assert decision.alternatives_considered[0].startswith('MONITOR:')
    assert 'routine request' in decision.primary_reason


@pytest.mark.parametrize('index', [5, 6, 7])
def test_limit_review_set_selects_review_without_clamping(index):
    context, plan, decision = pipeline('S2', index)
    assert tuple(candidate.action for candidate in plan.candidates) == (Action.LIMIT, Action.REQUEST_APPROVAL)
    assert decision.selected_action == Action.REQUEST_APPROVAL
    assert any(alternative.startswith('LIMIT:') for alternative in decision.alternatives_considered)
    limit = plan.candidates[0]
    assert limit.requires_approval
    assert limit.payload['replacement_value'] is None
    assert (limit.payload['allowed_min'], limit.payload['allowed_max']) == (20, 80)
    assert decision.to_dict()['selected_payload']['purpose'] == 'DEFER_FOR_REVIEW'
    assert 'no replacement value is inferred' in decision.primary_reason


def test_empty_plan_returns_explicit_no_decision():
    context, _, _ = pipeline()
    plan = empty_plan(context)
    decision = DecisionAgent().decide(context, plan)
    assert decision.status == 'NO_ADMISSIBLE_ACTION'
    assert decision.selected_action is None
    assert decision.selected_candidate_reference is None
    assert decision.candidate_actions == ()
    assert decision.alternatives_considered == ()
    assert decision.to_dict()['selected_payload'] is None


def test_selected_action_always_belongs_and_no_block_or_isolate_manufactured():
    for scenario in (f'S{i}' for i in range(1, 7)):
        for context, plan, decision in (row[1:] for row in inference_rows(scenario)):
            if decision.selected_action is not None:
                assert any(candidate.action == decision.selected_action and
                           candidate.reference == decision.selected_candidate_reference
                           for candidate in plan.candidates)
            assert decision.selected_action not in (Action.BLOCK, Action.ISOLATE)


def test_context_and_plan_mismatch_rejected():
    context, plan, _ = pipeline('S2', 4)
    other_context, other_plan, _ = pipeline('S5', 5)
    with pytest.raises(ValueError, match='belong'):
        DecisionAgent().decide(context, other_plan)
    with pytest.raises(ValueError):
        DecisionAgent().decide(context.to_dict(), plan)
    with pytest.raises(ValueError):
        DecisionAgent().decide(context, plan.to_dict())
    with pytest.raises(ValueError, match='version'):
        DecisionAgent().decide(context, replace(plan, context_version='other'))


def test_candidate_permutation_does_not_create_hidden_preference():
    context, plan, decision = pipeline('S2', 4)
    selected, reason = DecisionAgent._select(tuple(reversed(plan.candidates)), context)
    assert selected.action == decision.selected_action == Action.ALLOW
    assert reason == decision.primary_reason
    context, plan, decision = pipeline('S2', 5)
    selected, reason = DecisionAgent._select(tuple(reversed(plan.candidates)), context)
    assert selected.action == decision.selected_action == Action.REQUEST_APPROVAL
    assert reason == decision.primary_reason


def _context_with_scores(trust_score, risk_weights):
    event = EventGenerator(42, observable_state=True).generate('S2', 10)[4]
    observation = runtime_observation(event)
    trusts, _ = assess_observations([event], TrustAgent(), RiskAgent())
    trust = trusts[0]
    trust = replace(trust, composite_trust=trust_score,
                    trust_delta=trust_score - trust.previous_composite_trust)
    config = RiskConfig(dict(zip(COMPONENTS, risk_weights)))
    risk = RiskModel().evaluate(build_risk_input(observation, trust, config=config))
    auth_engine, authority_engine = AuthorizationEngine(), AutonomousAuthorityEngine()
    authorization = auth_engine.assess(observation)
    base = build_decision_context(observation, trust, risk, authorization,
                                  permission_policy=auth_engine.policy)
    authority = authority_engine.assess(base)
    return build_decision_context(
        observation, trust, risk, authorization, permission_policy=auth_engine.policy,
        autonomous_authority_assessment=authority, authority_policy=authority_engine.policy)


@pytest.mark.parametrize('trust_score,risk_weights', [
    (0.0, (0, 1, 0, 0)), (1.0, (0, 0, 1, 0)), (.25, (1, 0, 0, 0)),
])
def test_numeric_score_independence(trust_score, risk_weights):
    context = _context_with_scores(trust_score, risk_weights)
    plan = PlanningAgent().plan(context)
    decision = DecisionAgent().decide(context, plan)
    assert tuple(candidate.action for candidate in plan.candidates) == (Action.ALLOW, Action.MONITOR)
    assert decision.selected_action == Action.ALLOW
    assert 'no numeric trust category' in decision.trust_basis
    assert 'no numeric risk category' in decision.risk_basis


def test_s5_uses_current_high_output_semantics():
    for index, mode, maximum in ((4, 'NORMAL', 80), (5, 'HIGH_OUTPUT', 95), (6, 'HIGH_OUTPUT', 95)):
        context, plan, decision = pipeline('S5', index)
        assert context.capabilities.operational_validity.operating_mode == mode
        assert context.capabilities.operational_validity.check.maximum == maximum
        assert decision.selected_action == Action.ALLOW
        assert tuple(candidate.action for candidate in plan.candidates) == (Action.ALLOW, Action.MONITOR)


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
        return DecisionAgent().decide(context, plan).to_dict()

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


def test_decider_does_not_rerun_upstream_or_mutate(monkeypatch):
    context, plan, _ = pipeline()
    before_context, before_plan = context.to_dict(), plan.to_dict()
    monkeypatch.setattr(AuthorizationEngine, 'assess', lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(AutonomousAuthorityEngine, 'assess', lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()))
    assert DecisionAgent().decide(context, plan).selected_action == Action.ALLOW
    assert context.to_dict() == before_context and plan.to_dict() == before_plan


def test_multi_seed_evaluation_is_complete_and_repeatable():
    first = evaluate()
    assert first == evaluate()
    assert first['total_proposals'] == 300
    assert sum(first['proposal_distribution'].values()) == 300
