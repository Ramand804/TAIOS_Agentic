from copy import deepcopy
from dataclasses import FrozenInstanceError, replace

import pytest

from core.authorization import (PermissionRule, PermissionPolicy, AuthorizationAssessment,
                                AuthorizationStatus, VERSION)
from core.runtime_inputs import runtime_observation
from environment.assets import get_asset
from environment.event_generator import EventGenerator
from intelligence.authorization_engine import AuthorizationEngine
from evaluation.evaluate_authorization import coverage


def observation(scenario='S2', index=0):
    return runtime_observation(EventGenerator(42, observable_state=True).generate(scenario, 10)[index])


def test_immutable_contracts_and_copy_exports():
    policy = PermissionPolicy.load()
    a = AuthorizationEngine(policy).assess(observation())
    for obj, name, value in ((policy, 'rules', ()), (policy.rules[0], 'rationale', 'x'),
                             (a, 'status', AuthorizationStatus.UNKNOWN)):
        with pytest.raises(FrozenInstanceError):
            setattr(obj, name, value)
    export = a.to_dict()
    export['matched_rule_ids'].clear()
    assert a.matched_rule_ids
    assert isinstance(a, AuthorizationAssessment)


def test_determinism_and_input_preservation():
    o = observation()
    before = deepcopy(o)
    assert AuthorizationEngine().assess(o).to_dict() == AuthorizationEngine().assess(o).to_dict()
    assert o == before


@pytest.mark.parametrize('role_identity', ['operator-01', 'engineer-03'])
def test_each_grant_generalizes_across_registered_ids(role_identity):
    o = observation()
    o['identity_id'] = role_identity
    for source_id in ('PLC-01', 'PLC-03', 'PLC-04', 'PLC-07'):
        for target_id in ('MOTOR-02', 'PUMP-01'):
            source, target = get_asset(source_id), get_asset(target_id)
            o.update(source_id=source_id, source_type=source.asset_type,
                     network_zone=source.network_zone, protocol=source.protocol,
                     target_id=target_id, target_type=target.asset_type, asset_criticality=target.criticality)
            assert AuthorizationEngine().assess(o).status == 'AUTHORIZED'


@pytest.mark.parametrize('patch', [
    {'operation': 'unknown_operation'}, {'identity_id': 'unknown_identity'},
    {'source_id': 'unknown_source'}, {'target_id': 'unknown_target'},
    {'target_id': 'PLC-03', 'target_type': 'PLC', 'asset_criticality': .95},
    {'identity_id': 'service-account-03'}, {'source_type': 'service'},
])
def test_missing_or_unsupported_semantics_unknown(patch):
    o = observation()
    o.update(patch)
    assert AuthorizationEngine().assess(o).status == 'UNKNOWN'


def test_authentication_separation():
    engine = AuthorizationEngine()
    o = observation('S3')
    assert o['authentication_status'] is True
    assert engine.assess(o).status == 'UNKNOWN'
    o['authentication_status'] = False
    assert engine.assess(o).status == 'UNAUTHORIZED'
    o = observation()
    o['authentication_status'] = False
    a = engine.assess(o)
    assert a.status == 'UNAUTHORIZED' and a.matched_rule_ids
    assert 'AUTHENTICATION_FAILED' in a.reasons[0]


def test_conflict_deny_precedence_and_order_independence():
    grant = next(r for r in PermissionPolicy.load().rules if r.subject_role == 'operator')
    deny = replace(grant, rule_id='DENY', authorization='UNAUTHORIZED', rationale='Test prohibition')
    for rules in ((deny, grant), (grant, deny), (deny,)):
        a = AuthorizationEngine(PermissionPolicy(rules=rules)).assess(observation())
        assert a.status == 'UNAUTHORIZED'
        assert 'EXPLICIT_DENY_PRECEDENCE' in a.reasons[0]
    assert PermissionPolicy(rules=(deny, grant)).reference == PermissionPolicy(rules=(grant, deny)).reference
    assert AuthorizationEngine(PermissionPolicy(rules=())).assess(observation()).status == 'UNKNOWN'


def test_s1_service_relationship_is_not_inferred_from_generator():
    o = observation('S1', 5)
    assert (o['source_id'], o['target_id']) == ('SERVICE-03', 'PUMP-01')
    assert AuthorizationEngine().assess(o).status == 'UNKNOWN'


@pytest.mark.parametrize('scenario,status', [('S2', 'AUTHORIZED'), ('S3', 'UNKNOWN'), ('S5', 'AUTHORIZED')])
def test_pre_post_permission_is_identical(scenario, status):
    engine = AuthorizationEngine()
    results = [engine.assess(observation(scenario, i)) for i in range(10)]
    assert all(a.status == status for a in results)
    assert all(a.to_dict() == results[0].to_dict() for a in results)


@pytest.mark.parametrize('scenario', [f'S{i}' for i in range(1, 7)])
def test_leakage_boundary(scenario):
    engine = AuthorizationEngine()
    for e in EventGenerator(42, observable_state=True).generate(scenario, 10):
        baseline = engine.assess(runtime_observation(e)).to_dict()
        e.ground_truth = 'SUSPICIOUS'
        e.expected_safe_action = 'ISOLATE'
        e.scenario_id = 'not-inference'
        e.event_id = 'changed'
        e.sequence_number = 999
        e.provenance = None
        e.contextual_features.update(provenance='fake', transition=999, causal_tags=['fake'],
            compromise_phase=True, anomaly_score=999, simulated_attack_probability=-999,
            prior_device_trust=0, event_sequence=-1)
        assert engine.assess(runtime_observation(e)).to_dict() == baseline
    o = observation(scenario)
    o['scenario_id'] = scenario
    with pytest.raises(ValueError):
        engine.assess(o)
    o = observation(scenario)
    o['contextual_features']['anomaly_score'] = .9
    with pytest.raises(ValueError):
        engine.assess(o)


def test_configuration_versioning_and_validation(tmp_path):
    policy = PermissionPolicy.load()
    r = policy.rules[0]
    for patch in ({'policy_version': 'future'}, {'operation': '*'}, {'authorization': 'UNKNOWN'}):
        with pytest.raises(ValueError):
            replace(r, **patch)
    with pytest.raises(ValueError):
        PermissionPolicy(rules=(r, r))
    with pytest.raises(ValueError):
        PermissionPolicy(rules=(), policy_version='future')
    changed = PermissionPolicy(rules=(replace(r, rationale='Changed explicit policy'),))
    assert changed.reference != policy.reference
    p = tmp_path / 'bad.yaml'
    p.write_text('policy_version: day4c5-permissions-v1\nrules:\n - scenario_id: S2\n')
    with pytest.raises(ValueError):
        PermissionPolicy.load(p)
    assert policy.policy_version == VERSION


def test_coverage_repeatable():
    a, b = coverage(), coverage()
    assert a == b
    assert a['total_events'] == 300
    assert sum(v['count'] for v in a['overall'].values()) == 300
