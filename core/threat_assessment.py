"""Immutable, uncalibrated security-evidence contracts."""
from dataclasses import dataclass
from enum import Enum

from core.decision_contracts import Record
from core.risk_input import text_value
from core.trust_evidence import unit_value


class ThreatEvidenceClass(str, Enum):
    DIRECT = 'DIRECT'
    UNCERTAINTY = 'UNCERTAINTY'


class ThreatAssessmentStatus(str, Enum):
    DIRECT_EVIDENCE = 'DIRECT_EVIDENCE'
    UNCERTAINTY_ONLY = 'UNCERTAINTY_ONLY'
    NO_SECURITY_EVIDENCE = 'NO_SECURITY_EVIDENCE'


@dataclass(frozen=True, kw_only=True)
class ThreatEvidence(Record):
    evidence_type: str
    evidence_class: ThreatEvidenceClass
    source_id: str
    target_id: str
    strength: float
    confidence: float
    observable_basis: str
    semantic_rule_reference: str | None
    reason: str
    model_version: str

    def __post_init__(self):
        object.__setattr__(self, 'evidence_class', ThreatEvidenceClass(self.evidence_class))
        unit_value(self.strength, 'strength')
        unit_value(self.confidence, 'confidence')
        for name in ('evidence_type', 'source_id', 'target_id', 'observable_basis',
                     'reason', 'model_version'):
            text_value(getattr(self, name), name)
        if self.semantic_rule_reference is not None:
            text_value(self.semantic_rule_reference, 'semantic_rule_reference')

    @property
    def effective_strength(self):
        return self.strength * self.confidence


@dataclass(frozen=True, kw_only=True)
class ThreatAssessment(Record):
    source_id: str
    target_id: str
    identity_id: str
    evidence: tuple[ThreatEvidence, ...]
    security_signal_score: float
    evidence_coverage: float
    status: ThreatAssessmentStatus
    observable_reasons: tuple[str, ...]
    unresolved_requirements: tuple[str, ...]
    source_history_version: int
    prior_operational_violation_count: int
    threat_model_version: str
    configuration_fingerprint: str

    def __post_init__(self):
        for name in ('source_id', 'target_id', 'identity_id', 'threat_model_version',
                     'configuration_fingerprint'):
            text_value(getattr(self, name), name)
        evidence = tuple(self.evidence)
        if any(type(item) is not ThreatEvidence for item in evidence):
            raise ValueError('Expected ThreatEvidence records')
        object.__setattr__(self, 'evidence', evidence)
        object.__setattr__(self, 'status', ThreatAssessmentStatus(self.status))
        unit_value(self.security_signal_score, 'security_signal_score')
        unit_value(self.evidence_coverage, 'evidence_coverage')
        for name in ('source_history_version', 'prior_operational_violation_count'):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f'{name} must be a nonnegative integer')
        for name in ('observable_reasons', 'unresolved_requirements'):
            values = tuple(getattr(self, name))
            if any(not isinstance(value, str) or not value.strip() for value in values):
                raise ValueError(f'{name} must contain nonempty text')
            object.__setattr__(self, name, values)
        direct = [item.effective_strength for item in evidence
                  if item.evidence_class == ThreatEvidenceClass.DIRECT]
        expected_score = max(direct, default=0.0)
        if self.security_signal_score != expected_score:
            raise ValueError('Security signal must equal maximum effective direct strength')
        expected_status = (ThreatAssessmentStatus.DIRECT_EVIDENCE if direct else
                           ThreatAssessmentStatus.UNCERTAINTY_ONLY if evidence else
                           ThreatAssessmentStatus.NO_SECURITY_EVIDENCE)
        if self.status != expected_status:
            raise ValueError('Threat assessment status disagrees with evidence')

    @property
    def evidence_count(self):
        return len(self.evidence)

    @property
    def direct_evidence_count(self):
        return sum(item.evidence_class == ThreatEvidenceClass.DIRECT for item in self.evidence)

    @property
    def uncertainty_evidence_count(self):
        return sum(item.evidence_class == ThreatEvidenceClass.UNCERTAINTY for item in self.evidence)

    def to_dict(self):
        result = super().to_dict()
        result.update(evidence_count=self.evidence_count,
                      direct_evidence_count=self.direct_evidence_count,
                      uncertainty_evidence_count=self.uncertainty_evidence_count,
                      score_semantics=('Uncalibrated maximum effective direct evidence strength; '
                                       '0 does not prove benign and 1 does not prove malicious.'))
        return result
