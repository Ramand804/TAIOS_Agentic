"""Immutable per-entity trust state, without scenario or evaluation fields."""
from dataclasses import asdict, dataclass
import math
from core.trust_evidence import TrustDimension, unit_value

TRUST_FIELDS = ('identity_trust', 'device_trust', 'behavioral_trust', 'historical_trust', 'contextual_trust')


def validate_entity_id(entity_id):
    if not isinstance(entity_id, str):
        raise ValueError('entity_id must be a namespaced string')
    namespace, separator, value = entity_id.partition(':')
    if separator != ':' or namespace not in {'asset', 'identity'} or not value.strip():
        raise ValueError('entity_id must use asset: or identity: with a nonempty identifier')


@dataclass(frozen=True)
class EntityTrustState:
    entity_id: str
    identity_trust: float
    device_trust: float
    behavioral_trust: float
    historical_trust: float
    contextual_trust: float
    composite_trust: float
    observation_count: int = 0
    last_sequence_number: int = 0
    version: int = 0
    history_statistic: float = 0.0
    negative_history: tuple[bool, ...] = (False, False, False, False, False)
    evidence_counts: tuple[int, ...] = (0, 0, 0, 0, 0)

    def __post_init__(self):
        validate_entity_id(self.entity_id)
        for name in TRUST_FIELDS + ('composite_trust',):
            unit_value(getattr(self, name), name)
        for name in ('observation_count', 'last_sequence_number', 'version'):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise ValueError(f'{name} must be a nonnegative integer')
        h = self.history_statistic
        if isinstance(h, bool) or not isinstance(h, (int, float)) or not math.isfinite(h) or not -1 <= h <= 1:
            raise ValueError('history_statistic must be finite in [-1,1]')
        object.__setattr__(self, 'negative_history', tuple(self.negative_history))
        object.__setattr__(self, 'evidence_counts', tuple(self.evidence_counts))
        if len(self.negative_history) != len(TrustDimension) or any(type(x) is not bool for x in self.negative_history):
            raise ValueError('negative_history must contain five booleans')
        if len(self.evidence_counts) != len(TrustDimension) or any(type(x) is not int or x < 0 for x in self.evidence_counts):
            raise ValueError('evidence_counts must contain five nonnegative integers')

    def to_dict(self):
        result = asdict(self)
        result['negative_history'] = list(self.negative_history)
        result['evidence_counts'] = list(self.evidence_counts)
        return result
