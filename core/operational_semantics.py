"""Immutable operational semantic assessment contracts."""
from dataclasses import dataclass
from enum import Enum

from core.decision_contracts import Record, freeze
from core.risk_input import text_value


class SemanticStatus(str, Enum):
    SUPPORTED_VALID = 'SUPPORTED_VALID'
    SUPPORTED_INVALID = 'SUPPORTED_INVALID'
    UNDERSPECIFIED = 'UNDERSPECIFIED'
    UNSUPPORTED = 'UNSUPPORTED'


@dataclass(frozen=True, kw_only=True)
class OperationalSemanticAssessment(Record):
    source_id: str
    target_id: str
    target_type: str
    operation: str
    semantic_status: SemanticStatus
    value_semantics_status: str
    operational_validity: str
    known_constraints: object
    observed_value: object
    applicable_semantic_rule_ids: tuple[str, ...]
    unresolved_semantic_requirements: tuple[str, ...]
    reasons: tuple[str, ...]
    semantic_policy_version: str
    semantic_policy_fingerprint: str

    def __post_init__(self):
        object.__setattr__(self, 'semantic_status', SemanticStatus(self.semantic_status))
        for name in ('source_id', 'target_id', 'target_type', 'operation',
                     'value_semantics_status', 'operational_validity',
                     'semantic_policy_version', 'semantic_policy_fingerprint'):
            text_value(getattr(self, name), name)
        object.__setattr__(self, 'known_constraints', freeze(self.known_constraints))
        for name in ('applicable_semantic_rule_ids',
                     'unresolved_semantic_requirements', 'reasons'):
            values = tuple(getattr(self, name))
            if any(not isinstance(value, str) or not value.strip() for value in values):
                raise ValueError(f'{name} must contain nonempty text')
            object.__setattr__(self, name, values)

    @property
    def fully_established(self):
        return self.semantic_status in (
            SemanticStatus.SUPPORTED_VALID, SemanticStatus.SUPPORTED_INVALID)
