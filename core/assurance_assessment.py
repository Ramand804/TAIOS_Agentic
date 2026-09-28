"""Immutable decision-assurance evidence and assessment contracts."""
from dataclasses import dataclass
from enum import Enum

from core.actions import Action
from core.decision_contracts import Record, freeze, texts
from core.risk_input import text_value
from core.trust_evidence import unit_value


class AssuranceStatus(str, Enum):
    AUTONOMY_CONFIRMED = 'AUTONOMY_CONFIRMED'
    AUTONOMY_RESTRICTED = 'AUTONOMY_RESTRICTED'
    REVIEW_REQUIRED = 'REVIEW_REQUIRED'
    INSUFFICIENT_ASSURANCE = 'INSUFFICIENT_ASSURANCE'
    NOT_APPLICABLE = 'NOT_APPLICABLE'


class AssuranceCausalEffect(str, Enum):
    ASSESSMENT_ONLY = 'ASSESSMENT_ONLY'
    ASSURANCE_RESTRICTED_AUTHORITY = 'ASSURANCE_RESTRICTED_AUTHORITY'
    ALREADY_RESTRICTED_UPSTREAM = 'ALREADY_RESTRICTED_UPSTREAM'
    ASSURANCE_DISABLED = 'ASSURANCE_DISABLED'


@dataclass(frozen=True, kw_only=True)
class AssuranceEvidence(Record):
    category: str
    source_reference: str
    observable_basis: str
    reason: str

    def __post_init__(self):
        for name in ('category', 'source_reference', 'observable_basis', 'reason'):
            text_value(getattr(self, name), name)


@dataclass(frozen=True, kw_only=True)
class AssuranceAssessment(Record):
    event_reference: str
    authority_reference: str
    trust_reference: str
    threat_reference: str
    risk_reference: str
    drift_reference: str
    correlation_reference: str
    status: AssuranceStatus
    causal_effect: AssuranceCausalEffect
    existing_permitted_actions: tuple[str, ...]
    assured_permitted_actions: tuple[str, ...]
    restrictions: tuple[str, ...]
    evidence_items: tuple[AssuranceEvidence, ...]
    coverage: float
    unresolved_requirements: tuple[str, ...]
    policy_version: str
    configuration_fingerprint: str

    def __post_init__(self):
        for name in ('event_reference', 'authority_reference', 'trust_reference',
                     'threat_reference', 'risk_reference', 'drift_reference',
                     'correlation_reference', 'policy_version', 'configuration_fingerprint'):
            text_value(getattr(self, name), name)
        object.__setattr__(self, 'status', AssuranceStatus(self.status))
        object.__setattr__(self, 'causal_effect', AssuranceCausalEffect(self.causal_effect))
        allowed = tuple(action.value for action in Action)
        for name in ('existing_permitted_actions', 'assured_permitted_actions'):
            values = tuple(getattr(self, name))
            if len(values) != len(set(values)) or any(value not in allowed for value in values):
                raise ValueError(f'Invalid {name}')
            object.__setattr__(self, name, tuple(value for value in allowed if value in values))
        existing = set(self.existing_permitted_actions)
        assured_autonomous = set(self.assured_permitted_actions) - {Action.REQUEST_APPROVAL.value}
        if not assured_autonomous <= existing:
            raise ValueError('Assured autonomous authority cannot expand existing authority')
        object.__setattr__(self, 'restrictions', texts(self.restrictions))
        evidence = tuple(self.evidence_items)
        if any(type(item) is not AssuranceEvidence for item in evidence):
            raise ValueError('Expected AssuranceEvidence records')
        object.__setattr__(self, 'evidence_items', evidence)
        unit_value(self.coverage, 'coverage')
        object.__setattr__(self, 'unresolved_requirements', texts(self.unresolved_requirements))
