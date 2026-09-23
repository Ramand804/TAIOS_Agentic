"""Immutable, versioned simulation permission facts; no execution authority."""
from dataclasses import dataclass, fields
from pathlib import Path

import yaml

from core.decision_context import AuthorizationStatus
from core.decision_contracts import Record, texts
from core.risk_input import text_value

VERSION = 'day4c5-permissions-v1'


@dataclass(frozen=True, kw_only=True)
class PermissionRule(Record):
    rule_id: str
    subject_role: str
    source_type: str
    target_type: str
    operation: str
    authorization: AuthorizationStatus
    policy_version: str
    rationale: str

    def __post_init__(self):
        for field in fields(self):
            text_value(getattr(self, field.name), field.name)
        if any('*' in getattr(self, name) for name in
               ('subject_role', 'source_type', 'target_type', 'operation')):
            raise ValueError('Permission selectors must be exact, never wildcards')
        object.__setattr__(self, 'authorization', AuthorizationStatus(self.authorization))
        if self.authorization == AuthorizationStatus.UNKNOWN:
            raise ValueError('Rules must explicitly grant or deny; absence means UNKNOWN')
        if self.policy_version != VERSION:
            raise ValueError('Unsupported permission version')


@dataclass(frozen=True, kw_only=True)
class PermissionPolicy(Record):
    rules: tuple[PermissionRule, ...]
    policy_version: str = VERSION

    def __post_init__(self):
        rules = tuple(self.rules)
        if self.policy_version != VERSION:
            raise ValueError('Unsupported permission version')
        if any(type(r) is not PermissionRule or r.policy_version != self.policy_version for r in rules):
            raise ValueError('Expected same-version PermissionRule objects')
        if len({r.rule_id for r in rules}) != len(rules):
            raise ValueError('Duplicate permission rule ID')
        object.__setattr__(self, 'rules', tuple(sorted(rules, key=lambda r: r.rule_id)))

    @classmethod
    def load(cls, path=None):
        path = Path(path) if path is not None else Path(__file__).resolve().parents[1] / 'config/permissions.yaml'
        with path.open(encoding='utf-8') as stream:
            data = yaml.safe_load(stream)
        if type(data) is not dict or set(data) != {'policy_version', 'rules'} or type(data['rules']) is not list:
            raise ValueError('Expected versioned permission rules')
        required = {f.name for f in fields(PermissionRule)} - {'policy_version'}
        rules = []
        for row in data['rules']:
            if type(row) is not dict or set(row) != required:
                raise ValueError('Invalid permission rule schema')
            rules.append(PermissionRule(**row, policy_version=data['policy_version']))
        return cls(rules=tuple(rules), policy_version=data['policy_version'])


@dataclass(frozen=True, kw_only=True)
class AuthorizationAssessment(Record):
    identity_id: str
    source_id: str
    target_id: str
    operation: str
    status: AuthorizationStatus
    matched_rule_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    authorization_policy_version: str
    permission_policy_reference: str
    request_reference: str

    def __post_init__(self):
        for name in ('identity_id', 'source_id', 'target_id', 'operation',
                     'permission_policy_reference', 'request_reference'):
            text_value(getattr(self, name), name)
        if self.authorization_policy_version != VERSION:
            raise ValueError('Unsupported authorization version')
        object.__setattr__(self, 'status', AuthorizationStatus(self.status))
        ids = texts(self.matched_rule_ids)
        if len(set(ids)) != len(ids):
            raise ValueError('Duplicate matched rule ID')
        object.__setattr__(self, 'matched_rule_ids', tuple(sorted(ids)))
        object.__setattr__(self, 'reasons', texts(self.reasons))
        if not self.reasons:
            raise ValueError('Assessment requires reasons')
        if self.status == AuthorizationStatus.AUTHORIZED and not ids:
            raise ValueError('Authorization requires an explicit grant')
