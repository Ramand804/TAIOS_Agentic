"""Immutable contracts for governed contextual behavioral adaptation."""
from dataclasses import dataclass
from enum import Enum

from core.decision_contracts import Record, freeze, texts
from core.risk_input import text_value


class AdaptationMode(str, Enum):
    STATIC = 'STATIC'
    ADAPTIVE = 'ADAPTIVE'


class ProposalStatus(str, Enum):
    NOT_ELIGIBLE = 'NOT_ELIGIBLE'
    ELIGIBLE = 'ELIGIBLE'
    DEFERRED = 'DEFERRED'


class AdaptationStatus(str, Enum):
    NOT_ELIGIBLE = 'NOT_ELIGIBLE'
    DEFERRED = 'DEFERRED'
    REJECTED = 'REJECTED'
    APPLIED = 'APPLIED'


@dataclass(frozen=True, kw_only=True)
class BehavioralReferenceSnapshot(Record):
    scope: str
    sample_count: int
    reference_summary: object
    operating_context: object
    version: int
    provenance_references: tuple[str, ...]
    model_version: str

    def __post_init__(self):
        for name in ('scope', 'model_version'):
            text_value(getattr(self, name), name)
        if type(self.sample_count) is not int or self.sample_count < 1:
            raise ValueError('sample_count must be a positive integer')
        if type(self.version) is not int or self.version < 1:
            raise ValueError('version must be a positive integer')
        object.__setattr__(self, 'reference_summary', freeze(self.reference_summary))
        object.__setattr__(self, 'operating_context', freeze(self.operating_context))
        provenance = texts(self.provenance_references)
        if len(provenance) != self.sample_count:
            raise ValueError('Every reference sample requires provenance')
        object.__setattr__(self, 'provenance_references', provenance)


@dataclass(frozen=True, kw_only=True)
class AdaptationProposal(Record):
    trigger_drift_reference: str
    event_reference: str
    scope: str
    context_key: str
    status: ProposalStatus
    current_reference: str | None
    candidate_reference: str | None
    candidate_summary: object | None
    observable_support: tuple[str, ...]
    semantic_support: str
    feedback_support: str
    unresolved_requirements: tuple[str, ...]
    proposal_version: str
    configuration_fingerprint: str

    def __post_init__(self):
        for name in ('trigger_drift_reference', 'event_reference', 'scope', 'context_key',
                     'semantic_support', 'feedback_support', 'proposal_version',
                     'configuration_fingerprint'):
            text_value(getattr(self, name), name)
        object.__setattr__(self, 'status', ProposalStatus(self.status))
        for name in ('current_reference', 'candidate_reference'):
            if getattr(self, name) is not None:
                text_value(getattr(self, name), name)
        if self.candidate_summary is not None:
            object.__setattr__(self, 'candidate_summary', freeze(self.candidate_summary))
        if (self.candidate_reference is None) != (self.candidate_summary is None):
            raise ValueError('Candidate reference and summary must be supplied together')
        object.__setattr__(self, 'observable_support', texts(self.observable_support))
        object.__setattr__(self, 'unresolved_requirements', texts(self.unresolved_requirements))


@dataclass(frozen=True, kw_only=True)
class AdaptationDecision(Record):
    proposal_reference: str
    status: AdaptationStatus
    reasons: tuple[str, ...]
    authorized_update: bool
    before_reference: str | None
    after_reference: str | None
    policy_version: str
    configuration_fingerprint: str

    def __post_init__(self):
        for name in ('proposal_reference', 'policy_version', 'configuration_fingerprint'):
            text_value(getattr(self, name), name)
        object.__setattr__(self, 'status', AdaptationStatus(self.status))
        object.__setattr__(self, 'reasons', texts(self.reasons))
        if type(self.authorized_update) is not bool:
            raise ValueError('authorized_update must be bool')
        for name in ('before_reference', 'after_reference'):
            if getattr(self, name) is not None:
                text_value(getattr(self, name), name)
        applied = self.status == AdaptationStatus.APPLIED
        if applied != self.authorized_update or applied != (self.after_reference is not None):
            raise ValueError('Only an applied decision may authorize a reference update')
