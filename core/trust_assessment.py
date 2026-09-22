"""Immutable numeric trust output; audit identifiers are excluded from inference views."""
from dataclasses import dataclass
import math

from core.trust_evidence import TrustEvidence, TrustDimension, unit_value
from core.trust_state import EntityTrustState


@dataclass(frozen=True)
class AuditCorrelation:
    event_id: str
    sequence_number: int

    def __post_init__(self):
        if not isinstance(self.event_id, str) or not self.event_id.strip():
            raise ValueError('event_id must be nonempty')
        if type(self.sequence_number) is not int or self.sequence_number < 1:
            raise ValueError('sequence_number must be positive')


@dataclass(frozen=True)
class TrustAssessment(EntityTrustState):
    previous_composite_trust: float = 0.0
    trust_delta: float = 0.0
    previous_behavioral_trust: float = 0.0
    evidence: tuple[TrustEvidence, ...] = ()
    reasons: tuple[str, ...] = ()
    audit: AuditCorrelation | None = None

    def __post_init__(self):
        super().__post_init__()
        unit_value(self.previous_composite_trust, 'previous_composite_trust')
        unit_value(self.previous_behavioral_trust, 'previous_behavioral_trust')
        if isinstance(self.trust_delta, bool) or not isinstance(self.trust_delta, (int,float)) or not math.isfinite(self.trust_delta):
            raise ValueError('trust_delta must be finite')
        if not math.isclose(self.trust_delta, self.composite_trust-self.previous_composite_trust, abs_tol=1e-12):
            raise ValueError('trust_delta does not match composite change')
        object.__setattr__(self, 'evidence', tuple(self.evidence))
        object.__setattr__(self, 'reasons', tuple(self.reasons))
        for e in self.evidence:
            if type(e) is not TrustEvidence or e.entity_id != self.entity_id or e.event_id is not None or e.sequence_number is not None:
                raise ValueError('Assessment evidence must be uncorrelated and for the assessed entity')
        if not self.reasons or any(not isinstance(r,str) or not r.strip() for r in self.reasons):
            raise ValueError('Nonempty human-readable reasons required')
        if self.audit is not None and type(self.audit) is not AuditCorrelation:
            raise ValueError('Expected AuditCorrelation')

    @property
    def evidence_count(self): return len(self.evidence)

    @property
    def positive_evidence_count(self): return sum(e.direction == 'POSITIVE' for e in self.evidence)

    @property
    def negative_evidence_count(self): return sum(e.direction == 'NEGATIVE' for e in self.evidence)

    @property
    def neutral_evidence_count(self): return sum(e.direction == 'NEUTRAL' for e in self.evidence)

    @property
    def trust_state_version(self): return self.version

    @property
    def behavioral_trust_delta(self): return self.behavioral_trust-self.previous_behavioral_trust

    @property
    def evidence_coverage(self):
        result = {}
        for dimension in TrustDimension:
            signs = {e.direction.value for e in self.evidence if e.dimension == dimension and e.effective_magnitude > 0 and e.direction != 'NEUTRAL'}
            result[dimension.value] = [sign for sign in ('POSITIVE','NEGATIVE') if sign in signs] or ['INSUFFICIENT']
        return result

    def to_dict(self):
        result = super().to_dict()
        result.update(evidence=[e.to_dict() for e in self.evidence], reasons=list(self.reasons),
                      audit=None if self.audit is None else {'event_id':self.audit.event_id,'sequence_number':self.audit.sequence_number},
                      evidence_count=self.evidence_count, positive_evidence_count=self.positive_evidence_count,
                      negative_evidence_count=self.negative_evidence_count, neutral_evidence_count=self.neutral_evidence_count,
                      evidence_coverage=self.evidence_coverage, trust_state_version=self.version,
                      behavioral_trust_delta=self.behavioral_trust_delta)
        return result

    def to_inference_dict(self):
        result = self.to_dict()
        result.pop('audit')
        return result
