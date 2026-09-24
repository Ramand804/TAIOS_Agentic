"""Immutable autonomous-authority policy and assessment contracts."""
from collections.abc import Mapping
from dataclasses import dataclass, fields
from enum import Enum
from pathlib import Path

import yaml

from core.actions import Action
from core.decision_contracts import Record, freeze, texts
from core.decision_context import AuthorizationStatus
from core.risk_input import text_value

VERSION = 'day4c7-authority-v1'
CONDITIONS = {
    'ALWAYS', 'ROUTINE_AUTHORIZED_VALID', 'NOT_ROUTINE_AUTHORIZED_VALID',
    'AUTHORIZED_OUTSIDE_LIMIT', 'WITHIN_LIMIT', 'UNRESOLVED_OR_OUTSIDE',
}


class AuthorityStatus(str, Enum):
    PERMITTED = 'PERMITTED'
    NOT_PERMITTED = 'NOT_PERMITTED'
    UNKNOWN = 'UNKNOWN'


@dataclass(frozen=True, kw_only=True)
class AuthorityRule(Record):
    rule_id: str
    action: Action
    condition: str
    status: AuthorityStatus
    rationale: str
    policy_version: str = VERSION

    def __post_init__(self):
        for name in ('rule_id', 'condition', 'rationale', 'policy_version'):
            text_value(getattr(self, name), name)
        object.__setattr__(self, 'action', Action(self.action))
        object.__setattr__(self, 'status', AuthorityStatus(self.status))
        if self.condition not in CONDITIONS:
            raise ValueError('Unsupported authority condition')
        if self.status == AuthorityStatus.UNKNOWN:
            raise ValueError('Rules must resolve to PERMITTED or NOT_PERMITTED')
        if self.policy_version != VERSION:
            raise ValueError('Unsupported authority policy version')


@dataclass(frozen=True, kw_only=True)
class AuthorityPolicy(Record):
    rules: tuple[AuthorityRule, ...]
    policy_version: str = VERSION

    def __post_init__(self):
        rules = tuple(self.rules)
        if self.policy_version != VERSION:
            raise ValueError('Unsupported authority policy version')
        if any(type(rule) is not AuthorityRule or rule.policy_version != self.policy_version for rule in rules):
            raise ValueError('Expected same-version AuthorityRule objects')
        if len({rule.rule_id for rule in rules}) != len(rules):
            raise ValueError('Duplicate authority rule ID')
        object.__setattr__(self, 'rules', tuple(sorted(rules, key=lambda rule: rule.rule_id)))

    @classmethod
    def load(cls, path=None):
        path = Path(path) if path is not None else Path(__file__).resolve().parents[1] / 'config/autonomous_authority.yaml'
        with path.open(encoding='utf-8') as stream:
            data = yaml.safe_load(stream)
        if type(data) is not dict or set(data) != {'policy_version', 'rules'} or type(data['rules']) is not list:
            raise ValueError('Expected versioned autonomous-authority rules')
        expected = {field.name for field in fields(AuthorityRule)} - {'policy_version'}
        rules = []
        for row in data['rules']:
            if type(row) is not dict or set(row) != expected:
                raise ValueError('Invalid autonomous-authority rule schema')
            rules.append(AuthorityRule(**row, policy_version=data['policy_version']))
        return cls(rules=tuple(rules), policy_version=data['policy_version'])


@dataclass(frozen=True, kw_only=True)
class AutonomousAuthorityAssessment(Record):
    source_id: str
    identity_id: str
    target_id: str
    operation: str
    authorization_status: AuthorizationStatus
    operational_validity: str
    action_authority: object
    matched_policy_ids: object
    unresolved_requirements: tuple[str, ...]
    reasons: object
    authority_policy_version: str
    authority_policy_fingerprint: str
    context_input_reference: str

    def __post_init__(self):
        for name in ('source_id', 'identity_id', 'target_id', 'operation',
                     'operational_validity', 'authority_policy_version',
                     'authority_policy_fingerprint', 'context_input_reference'):
            text_value(getattr(self, name), name)
        object.__setattr__(self, 'authorization_status', AuthorizationStatus(self.authorization_status))
        if self.operational_validity not in {'WITHIN_LIMIT', 'OUTSIDE_LIMIT', 'UNKNOWN'}:
            raise ValueError('Invalid operational validity')
        if self.authority_policy_version != VERSION:
            raise ValueError('Unsupported authority policy version')
        if not isinstance(self.action_authority, Mapping) or set(self.action_authority) != {a.value for a in Action}:
            raise ValueError('Every canonical action requires authority status')
        statuses = {Action(key).value: AuthorityStatus(value).value for key, value in self.action_authority.items()}
        for name, value in (('matched_policy_ids', self.matched_policy_ids), ('reasons', self.reasons)):
            if not isinstance(value, Mapping) or set(value) != {a.value for a in Action}:
                raise ValueError(f'Every canonical action requires {name}')
        matched = {a.value: texts(self.matched_policy_ids[a.value]) for a in Action}
        reasons = {a.value: texts(self.reasons[a.value]) for a in Action}
        if any(not reasons[a.value] for a in Action):
            raise ValueError('Every action requires an authority reason')
        object.__setattr__(self, 'action_authority', freeze(statuses))
        object.__setattr__(self, 'matched_policy_ids', freeze(matched))
        object.__setattr__(self, 'reasons', freeze(reasons))
        object.__setattr__(self, 'unresolved_requirements', texts(self.unresolved_requirements))

    def status_for(self, action):
        return AuthorityStatus(self.action_authority[Action(action).value])
