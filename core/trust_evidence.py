"""Immutable evidence records and post-inference audit correlation; no scores."""
from dataclasses import asdict, dataclass, replace
from enum import Enum
import math


class TrustDimension(str, Enum):
    IDENTITY = 'IDENTITY'
    DEVICE = 'DEVICE'
    BEHAVIOR = 'BEHAVIOR'
    HISTORY = 'HISTORY'
    CONTEXT = 'CONTEXT'


class EvidenceDirection(str, Enum):
    POSITIVE = 'POSITIVE'
    NEGATIVE = 'NEGATIVE'
    NEUTRAL = 'NEUTRAL'


def unit_value(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f'{name} must be finite and in [0, 1]')


@dataclass(frozen=True)
class TrustEvidence:
    entity_id: str
    dimension: TrustDimension
    direction: EvidenceDirection
    strength: float
    confidence: float
    source: str
    reason: str
    event_id: str | None = None
    sequence_number: int | None = None

    def __post_init__(self):
        for name in ('entity_id', 'source', 'reason'):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f'{name} must be a nonempty string')
        object.__setattr__(self, 'dimension', TrustDimension(self.dimension))
        object.__setattr__(self, 'direction', EvidenceDirection(self.direction))
        unit_value(self.strength, 'strength')
        unit_value(self.confidence, 'confidence')
        if (self.event_id is None) != (self.sequence_number is None):
            raise ValueError('Audit event_id and sequence_number must be supplied together')
        if self.event_id is not None:
            if not isinstance(self.event_id, str) or not self.event_id.strip():
                raise ValueError('event_id must be nonempty')
            if type(self.sequence_number) is not int or self.sequence_number < 1:
                raise ValueError('sequence_number must be a positive integer')

    @property
    def effective_magnitude(self):
        return self.strength * self.confidence

    def to_dict(self):
        result = asdict(self)
        result['dimension'] = self.dimension.value
        result['direction'] = self.direction.value
        return result


def attach_audit_correlation(evidence, *, event_id, sequence_number):
    """Stamp copies after inference; never pass the original IDs into extraction."""
    if event_id is None or sequence_number is None:
        raise ValueError("Audit correlation requires both event_id and sequence_number")
    records = list(evidence)
    # Validate metadata even for an empty collection.
    TrustEvidence('audit:validation', 'HISTORY', 'NEUTRAL', 0, 0,
                  'audit', 'Validate audit correlation.', event_id, sequence_number)
    if any(item.event_id is not None for item in records):
        raise ValueError('Evidence is already correlated')
    return [replace(item, event_id=event_id, sequence_number=sequence_number) for item in records]
