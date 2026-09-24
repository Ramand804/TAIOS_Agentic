"""Immutable contracts for causal cross-entity security-correlation evidence."""
from dataclasses import dataclass
from enum import Enum

from core.decision_contracts import Record
from core.risk_input import text_value
from core.trust_evidence import unit_value


class CorrelationEvidenceClass(str, Enum):
    DIRECT = 'DIRECT'
    UNCERTAINTY = 'UNCERTAINTY'


class CorrelationAssessmentStatus(str, Enum):
    DIRECT_EVIDENCE = 'DIRECT_EVIDENCE'
    UNCERTAINTY_ONLY = 'UNCERTAINTY_ONLY'
    NO_CORRELATION_EVIDENCE = 'NO_CORRELATION_EVIDENCE'


def _texts(values, name):
    if isinstance(values, str):
        raise ValueError(f'{name} must be a sequence')
    result = tuple(values)
    if any(not isinstance(value, str) or not value.strip() for value in result):
        raise ValueError(f'{name} must contain nonempty strings')
    return result


@dataclass(frozen=True, kw_only=True)
class CorrelationEvidence(Record):
    category: str
    evidence_class: CorrelationEvidenceClass
    current_source: str
    related_sources: tuple[str, ...]
    current_target: str
    related_targets: tuple[str, ...]
    relationship_type: str
    supporting_prior_event_references: tuple[str, ...]
    strength: float
    confidence: float
    observable_basis: str
    reason: str
    model_version: str

    def __post_init__(self):
        object.__setattr__(self, 'evidence_class', CorrelationEvidenceClass(self.evidence_class))
        for name in ('category', 'current_source', 'current_target', 'relationship_type',
                     'observable_basis', 'reason', 'model_version'):
            text_value(getattr(self, name), name)
        for name in ('related_sources', 'related_targets', 'supporting_prior_event_references'):
            values = _texts(getattr(self, name), name)
            if not values or len(values) != len(set(values)):
                raise ValueError(f'{name} must be nonempty and unique')
            object.__setattr__(self, name, values)
        if self.current_source in self.related_sources:
            raise ValueError('Cross-entity evidence requires distinct related sources')
        unit_value(self.strength, 'strength')
        unit_value(self.confidence, 'confidence')

    @property
    def effective_strength(self):
        return self.strength * self.confidence


@dataclass(frozen=True, kw_only=True)
class CorrelationAssessment(Record):
    current_event_reference: str
    source_id: str
    target_id: str
    identity_id: str
    evidence: tuple[CorrelationEvidence, ...]
    coordination_signal_score: float
    evidence_coverage: float
    status: CorrelationAssessmentStatus
    participating_entities: tuple[str, ...]
    supporting_event_references: tuple[str, ...]
    history_version: int
    configuration_fingerprint: str
    unresolved_requirements: tuple[str, ...]
    reasons: tuple[str, ...]
    model_version: str

    def __post_init__(self):
        for name in ('current_event_reference', 'source_id', 'target_id', 'identity_id',
                     'configuration_fingerprint', 'model_version'):
            text_value(getattr(self, name), name)
        evidence = tuple(self.evidence)
        if any(type(item) is not CorrelationEvidence for item in evidence):
            raise ValueError('Expected CorrelationEvidence records')
        object.__setattr__(self, 'evidence', evidence)
        object.__setattr__(self, 'status', CorrelationAssessmentStatus(self.status))
        unit_value(self.coordination_signal_score, 'coordination_signal_score')
        unit_value(self.evidence_coverage, 'evidence_coverage')
        if type(self.history_version) is not int or self.history_version < 0:
            raise ValueError('history_version must be a nonnegative integer')
        for name in ('participating_entities', 'supporting_event_references',
                     'unresolved_requirements', 'reasons'):
            values = _texts(getattr(self, name), name)
            if name in ('participating_entities', 'supporting_event_references') and len(values) != len(set(values)):
                raise ValueError(f'{name} must be unique')
            object.__setattr__(self, name, values)
        direct = [item.effective_strength for item in evidence
                  if item.evidence_class == CorrelationEvidenceClass.DIRECT]
        uncertain = any(item.evidence_class == CorrelationEvidenceClass.UNCERTAINTY
                        for item in evidence)
        expected_status = (CorrelationAssessmentStatus.DIRECT_EVIDENCE if direct else
                           CorrelationAssessmentStatus.UNCERTAINTY_ONLY if uncertain else
                           CorrelationAssessmentStatus.NO_CORRELATION_EVIDENCE)
        if self.status != expected_status:
            raise ValueError('Correlation status disagrees with evidence')
        if self.coordination_signal_score != max(direct, default=0.0):
            raise ValueError('Coordination signal must equal maximum direct evidence strength')
        if bool(evidence) != bool(self.supporting_event_references):
            raise ValueError('Evidence and supporting references must agree')
        if direct and len(self.participating_entities) < 2:
            raise ValueError('Direct cross-entity evidence requires multiple entities')

    @property
    def evidence_count(self):
        return len(self.evidence)

    def to_dict(self):
        result = super().to_dict()
        result.update(
            evidence_count=self.evidence_count,
            score_semantics=('Uncalibrated cross-entity evidence severity; not probability of '
                             'coordination, compromise, or attack.'))
        return result
