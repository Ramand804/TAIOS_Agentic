"""Deterministic permission evaluation over the exact safe runtime projection."""
import math
from types import MappingProxyType

from core.authorization import AuthorizationAssessment, PermissionPolicy, AuthorizationStatus
from core.experiment import fingerprint
from core.runtime_inputs import OBSERVABLE_FIELDS
from environment.assets import ASSET_REGISTRY
from environment.identities import DEFAULT_IDENTITIES
from environment.industrial_environment import OperatingMode, ProductionState


def _validate(observation):
    if type(observation) is not dict or set(observation) != set(OBSERVABLE_FIELDS) | {'contextual_features'}:
        raise ValueError('Expected exact runtime_observation projection')
    for name in OBSERVABLE_FIELDS:
        if name not in {'requested_value', 'authentication_status', 'asset_criticality'}:
            if not isinstance(observation[name], str) or not observation[name].strip():
                raise ValueError(f'{name} must be nonempty text')
    if type(observation['authentication_status']) is not bool:
        raise ValueError('authentication_status must be bool')
    c = observation['asset_criticality']
    if type(c) not in (int, float) or not math.isfinite(c) or not 0 <= c <= 1:
        raise ValueError('Invalid asset_criticality')
    context = observation['contextual_features']
    if type(context) is not dict or not set(context) <= {'production_state', 'operating_mode'}:
        raise ValueError('Expected allowlisted context')
    if 'production_state' in context:
        ProductionState(context['production_state'])
    if 'operating_mode' in context:
        OperatingMode(context['operating_mode'])


class AuthorizationEngine:
    def __init__(self, policy=None):
        self.policy = PermissionPolicy.load() if policy is None else policy
        if type(self.policy) is not PermissionPolicy:
            raise ValueError('Expected PermissionPolicy')
        self.assets = MappingProxyType(dict(ASSET_REGISTRY))
        self.identities = MappingProxyType({i.identity_id: i for i in DEFAULT_IDENTITIES})

    def assess(self, safe_observation):
        _validate(safe_observation)
        o = safe_observation
        identity = self.identities.get(o['identity_id'])
        source = self.assets.get(o['source_id'])
        target = self.assets.get(o['target_id'])
        # Bind only permission-relevant facts. Values/mode belong to process
        # validity, not this policy; full payload binding belongs to integration.
        facts = {k: o[k] for k in ('identity_id', 'source_id', 'source_type',
                 'target_id', 'target_type', 'operation', 'authentication_status',
                 'network_zone', 'protocol')}
        facts['registered_role'] = identity.role if identity else None
        facts['registered_source'] = source.to_dict() if source else None
        facts['registered_target'] = target.to_dict() if target else None
        matched = ()
        reasons = []
        known = identity is not None and source is not None and target is not None
        consistent = known and (o['source_type'], o['network_zone'], o['protocol'], o['target_type']) == (
            source.asset_type, source.network_zone, source.protocol, target.asset_type)
        if consistent:
            matched = tuple(r for r in self.policy.rules if
                (r.subject_role, r.source_type, r.target_type, r.operation) ==
                (identity.role, source.asset_type, target.asset_type, o['operation']))
        if not o['authentication_status']:
            status = AuthorizationStatus.UNAUTHORIZED
            reasons.append('AUTHENTICATION_FAILED: policy prerequisite failed; no request permission (P02).')
        elif not known:
            status = AuthorizationStatus.UNKNOWN
            reasons.append('UNKNOWN_REFERENCE: identity, source or target is not registered.')
        elif not consistent:
            status = AuthorizationStatus.UNKNOWN
            reasons.append('REGISTRY_MISMATCH: supplied asset metadata cannot establish permission.')
        elif not matched:
            status = AuthorizationStatus.UNKNOWN
            reasons.append('NO_MATCHING_RULE: successful authentication does not grant permission.')
        elif any(r.authorization == AuthorizationStatus.UNAUTHORIZED for r in matched):
            status = AuthorizationStatus.UNAUTHORIZED
            reasons.append('EXPLICIT_DENY_PRECEDENCE: matching prohibition overrides any grants.')
        else:
            status = AuthorizationStatus.AUTHORIZED
            reasons.append('EXPLICIT_GRANT: permission to request only; not process validity or execution authority.')
        reasons.extend(f'{r.rule_id}: {r.rationale}' for r in matched)
        return AuthorizationAssessment(
            **{k: o[k] for k in ('identity_id', 'source_id', 'target_id', 'operation')},
            status=status, matched_rule_ids=tuple(r.rule_id for r in matched), reasons=tuple(reasons),
            authorization_policy_version=self.policy.policy_version,
            permission_policy_reference=self.policy.reference, request_reference=fingerprint(facts))
