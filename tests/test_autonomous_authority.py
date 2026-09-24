from copy import deepcopy
from dataclasses import FrozenInstanceError, replace

import pytest

from agents.planning_agent import PlanningAgent
from agents.risk_agent import RiskAgent
from agents.trust_agent import TrustAgent
from core.actions import Action
from core.autonomous_authority import (
    AutonomousAuthorityAssessment, AuthorityPolicy, AuthorityRule, AuthorityStatus, VERSION,
)
from core.runtime_inputs import runtime_observation
from core.trust_assessment import AuditCorrelation
from environment.event_generator import EventGenerator
from evaluation.evaluate_autonomous_authority import evaluate
from evaluation.evaluate_risk import assess_observations
from intelligence.authorization_engine import AuthorizationEngine
from intelligence.autonomous_authority_engine import AutonomousAuthorityEngine
from intelligence.decision_context_builder import build_decision_context


def pipeline(scenario='S2', index=4, *, authority_policy=None):
    events = EventGenerator(42, observable_state=True).generate(scenario, 10)
    trusts, risks = assess_observations(events, TrustAgent(), RiskAgent())
    observation = runtime_observation(events[index])
    authorization_engine = AuthorizationEngine()
    authorization = authorization_engine.assess(observation)
    base = build_decision_context(observation, trusts[index], risks[index], authorization,
                                  permission_policy=authorization_engine.policy)
    engine = AutonomousAuthorityEngine(authority_policy)
    authority = engine.assess(base)
    context = build_decision_context(
        observation, trusts[index], risks[index], authorization,
        permission_policy=authorization_engine.policy,
        autonomous_authority_assessment=authority,
        authority_policy=engine.policy,
    )
    return events[index], observation, base, authority, context, engine


def actions(result):
    return tuple(candidate.action for candidate in result.candidates)


def test_contract_is_immutable_complete_and_unranked():
    _, _, _, assessment, _, _ = pipeline()
    assert type(assessment) is AutonomousAuthorityAssessment
    assert set(assessment.action_authority) == {action.value for action in Action}
    assert assessment.authority_policy_version == VERSION
    for name in ('selected_action', 'recommended_action', 'ranking', 'best_action'):
        assert not hasattr(assessment, name) and name not in assessment.to_dict()
    with pytest.raises(FrozenInstanceError):
        assessment.operation = 'other'
    with pytest.raises(TypeError):
        assessment.action_authority['ALLOW'] = 'UNKNOWN'
    exported = assessment.to_dict()
    exported['reasons']['ALLOW'].clear()
    assert assessment.reasons['ALLOW']


def test_policy_version_fingerprint_and_determinism():
    policy = AuthorityPolicy.load()
    assert policy.policy_version == VERSION
    assert policy.reference == AuthorityPolicy.load().reference
    _, _, base, first, context, _ = pipeline()
    assert first == AutonomousAuthorityEngine().assess(base)
    assert context.reference == pipeline()[4].reference
    changed_rule = replace(policy.rules[0], rationale='Changed simulation policy')
    changed = AuthorityPolicy(rules=(changed_rule,) + policy.rules[1:])
    assert changed.reference != policy.reference
    with pytest.raises(ValueError):
        AuthorityPolicy(rules=(policy.rules[0], policy.rules[0]))
    with pytest.raises(ValueError):
        replace(policy.rules[0], policy_version='future')


def test_routine_valid_authority_despite_incomplete_optional_evidence():
    _, _, _, authority, context, _ = pipeline('S2', 4)
    assert context.risk_assessment.coverage == .45
    assert context.trust_assessment.evidence_coverage['HISTORY'] == ['INSUFFICIENT']
    assert authority.status_for(Action.ALLOW) == AuthorityStatus.PERMITTED
    assert authority.status_for(Action.MONITOR) == AuthorityStatus.PERMITTED
    assert authority.status_for(Action.REQUEST_APPROVAL) == AuthorityStatus.NOT_PERMITTED
    assert actions(PlanningAgent().plan(context)) == (Action.ALLOW, Action.MONITOR)


@pytest.mark.parametrize('index', [5, 6, 7])
def test_authorized_outside_limit_authority(index):
    _, _, _, authority, context, _ = pipeline('S2', index)
    assert context.authorization_status == 'AUTHORIZED'
    assert authority.operational_validity == 'OUTSIDE_LIMIT'
    assert authority.status_for(Action.ALLOW) == AuthorityStatus.NOT_PERMITTED
    assert authority.status_for(Action.MONITOR) == AuthorityStatus.NOT_PERMITTED
    assert authority.status_for(Action.LIMIT) == AuthorityStatus.PERMITTED
    assert authority.status_for(Action.REQUEST_APPROVAL) == AuthorityStatus.PERMITTED
    assert actions(PlanningAgent().plan(context)) == (Action.LIMIT, Action.REQUEST_APPROVAL)


@pytest.mark.parametrize('scenario', ['S1', 'S3'])
def test_unknown_authorization_or_operation_routes_only_to_review(scenario):
    _, _, _, authority, context, _ = pipeline(scenario, 5)
    assert authority.authorization_status == 'UNKNOWN'
    assert authority.status_for(Action.ALLOW) == AuthorityStatus.NOT_PERMITTED
    assert authority.status_for(Action.REQUEST_APPROVAL) == AuthorityStatus.PERMITTED
    assert authority.status_for(Action.ISOLATE) == AuthorityStatus.NOT_PERMITTED
    assert actions(PlanningAgent().plan(context)) == (Action.REQUEST_APPROVAL,)


@pytest.mark.parametrize('index,mode,maximum', [(4, 'NORMAL', 80), (5, 'HIGH_OUTPUT', 95), (6, 'HIGH_OUTPUT', 95)])
def test_s5_current_mode_routine_authority(index, mode, maximum):
    _, _, _, authority, context, _ = pipeline('S5', index)
    check = context.capabilities.operational_validity.check
    assert authority.status_for(Action.ALLOW) == AuthorityStatus.PERMITTED
    assert authority.status_for(Action.MONITOR) == AuthorityStatus.PERMITTED
    assert context.capabilities.operational_validity.operating_mode == mode
    assert check.maximum == maximum
    assert actions(PlanningAgent().plan(context)) == (Action.ALLOW, Action.MONITOR)


def test_block_isolation_and_capability_are_conservative():
    for scenario, index in (('S2', 4), ('S2', 5), ('S3', 5)):
        _, _, _, authority, context, _ = pipeline(scenario, index)
        assert authority.status_for(Action.BLOCK) == AuthorityStatus.NOT_PERMITTED
        assert authority.status_for(Action.ISOLATE) == AuthorityStatus.NOT_PERMITTED
        assert Action.ISOLATE not in context.capabilities.supported_actions
        assert Action.BLOCK not in actions(PlanningAgent().plan(context))
        assert Action.ISOLATE not in actions(PlanningAgent().plan(context))


def test_restrictive_conflict_precedence_and_input_order():
    policy = AuthorityPolicy.load()
    deny = next(rule for rule in policy.rules if rule.rule_id == 'AUTH-BLOCK-SAFETY-RESTRICTION')
    permit = AuthorityRule(rule_id='TEST-BLOCK-PERMIT', action='BLOCK', condition='ALWAYS',
                           status='PERMITTED', rationale='Test-only conflict')
    first = AuthorityPolicy(rules=(permit, deny))
    second = AuthorityPolicy(rules=(deny, permit))
    assert first.reference == second.reference
    for configured in (first, second):
        authority = pipeline(authority_policy=configured)[3]
        assert authority.status_for(Action.BLOCK) == AuthorityStatus.NOT_PERMITTED
        assert 'RESTRICTIVE_PRECEDENCE' in authority.reasons['BLOCK'][0]


@pytest.mark.parametrize('field,value', [
    ('source_id', 'PLC-01'), ('identity_id', 'operator-01'), ('target_id', 'PUMP-01'),
    ('operation', 'write_register'), ('authorization_status', 'UNKNOWN'),
    ('operational_validity', 'OUTSIDE_LIMIT'), ('authority_policy_fingerprint', 'wrong'),
    ('context_input_reference', 'wrong'),
])
def test_context_rejects_mismatched_authority(field, value):
    _, observation, base, authority, _, engine = pipeline()
    with pytest.raises(ValueError, match='Authority'):
        build_decision_context(
            observation, base.trust_assessment, base.risk_assessment, base.authorization_assessment,
            permission_policy=base.permission_policy,
            autonomous_authority_assessment=replace(authority, **{field: value}),
            authority_policy=engine.policy,
        )


def test_planner_differential_and_canonical_order():
    expected = {
        ('S1', 5): ((Action.REQUEST_APPROVAL,), (Action.REQUEST_APPROVAL,)),
        ('S2', 4): ((Action.REQUEST_APPROVAL,), (Action.ALLOW, Action.MONITOR)),
        ('S2', 5): ((Action.LIMIT, Action.REQUEST_APPROVAL), (Action.LIMIT, Action.REQUEST_APPROVAL)),
        ('S3', 5): ((Action.REQUEST_APPROVAL,), (Action.REQUEST_APPROVAL,)),
        ('S5', 5): ((Action.REQUEST_APPROVAL,), (Action.ALLOW, Action.MONITOR)),
    }
    for key, (before, after) in expected.items():
        _, _, base, _, context, _ = pipeline(*key)
        assert actions(PlanningAgent().plan(base)) == before
        result = PlanningAgent().plan(context)
        assert actions(result) == after
        assert actions(result) == tuple(action for action in Action if action in actions(result))


@pytest.mark.parametrize('scenario', [f'S{i}' for i in range(1, 7)])
def test_full_pipeline_leakage_and_audit_isolation(scenario):
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
        return authority.to_dict(), context.to_dict(), PlanningAgent().plan(context).to_dict()

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


def test_engine_does_not_mutate_or_recompute_upstream(monkeypatch):
    _, _, base, _, _, _ = pipeline()
    before = deepcopy(base.to_dict())
    from intelligence.authorization_engine import AuthorizationEngine as Upstream
    monkeypatch.setattr(Upstream, 'assess', lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()))
    assert AutonomousAuthorityEngine().assess(base) == AutonomousAuthorityEngine().assess(base)
    assert base.to_dict() == before


def test_five_seed_coverage_is_complete_and_repeatable():
    first = evaluate()
    assert first == evaluate()
    assert first['total_events'] == 300
    for action in Action:
        coverage = first['per_action_coverage'][action.value]
        assert sum(row['count'] for row in coverage.values()) == 300
