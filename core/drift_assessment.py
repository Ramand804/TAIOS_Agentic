"""Immutable contracts for observable regime and behavioral-change evidence."""
from dataclasses import dataclass
from enum import Enum

from core.decision_contracts import Record, freeze, texts
from core.risk_input import text_value
from core.trust_evidence import unit_value


class DriftStatus(str, Enum):
    INSUFFICIENT_HISTORY = 'INSUFFICIENT_HISTORY'
    INSUFFICIENT_SEMANTIC_SCOPE = 'INSUFFICIENT_SEMANTIC_SCOPE'
    NO_CHANGE = 'NO_CHANGE'
    TRANSIENT_DEVIATION = 'TRANSIENT_DEVIATION'
    KNOWN_REGIME_CHANGE = 'KNOWN_REGIME_CHANGE'
    UNEXPLAINED_PERSISTENT_DRIFT = 'UNEXPLAINED_PERSISTENT_DRIFT'


@dataclass(frozen=True, kw_only=True)
class DriftEvidence(Record):
    category: str
    scope: str
    feature: str
    reference_summary: object
    recent_summary: object
    observed_change: float
    context_reference: str
    semantic_reference: str
    reason: str

    def __post_init__(self):
        for name in ('category', 'scope', 'feature', 'context_reference',
                     'semantic_reference', 'reason'):
            text_value(getattr(self, name), name)
        unit_value(self.observed_change, 'observed_change')
        object.__setattr__(self, 'reference_summary', freeze(self.reference_summary))
        object.__setattr__(self, 'recent_summary', freeze(self.recent_summary))


@dataclass(frozen=True, kw_only=True)
class DriftAssessment(Record):
    event_reference: str
    scope: str
    status: DriftStatus
    evidence: tuple[DriftEvidence, ...]
    history_count: int
    reference_window_size: int
    recent_window_size: int
    change_score: float
    persistence_count: int
    context_explanation: str | None
    unresolved_requirements: tuple[str, ...]
    model_version: str
    configuration_fingerprint: str

    def __post_init__(self):
        for name in ('event_reference', 'scope', 'model_version', 'configuration_fingerprint'):
            text_value(getattr(self, name), name)
        object.__setattr__(self, 'status', DriftStatus(self.status))
        evidence = tuple(self.evidence)
        if any(type(item) is not DriftEvidence for item in evidence):
            raise ValueError('Expected DriftEvidence records')
        object.__setattr__(self, 'evidence', evidence)
        for name in ('history_count', 'reference_window_size', 'recent_window_size',
                     'persistence_count'):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f'{name} must be a nonnegative integer')
        unit_value(self.change_score, 'change_score')
        if self.context_explanation is not None:
            text_value(self.context_explanation, 'context_explanation')
        object.__setattr__(self, 'unresolved_requirements', texts(self.unresolved_requirements))
        if self.status == DriftStatus.KNOWN_REGIME_CHANGE and self.context_explanation is None:
            raise ValueError('Known regime change requires an observable context explanation')
        if self.status == DriftStatus.UNEXPLAINED_PERSISTENT_DRIFT and self.persistence_count < 2:
            raise ValueError('Persistent drift requires multiple supporting observations')

    def to_dict(self):
        result = super().to_dict()
        result['score_semantics'] = (
            'Deterministic normalized change magnitude; not probability of drift, regime, or attack.')
        return result
