"""Day 2C mathematical trust updater. No events, scenario labels or agent decisions."""
from dataclasses import dataclass, fields
import math
from pathlib import Path

import yaml

from core.trust_evidence import TrustDimension, EvidenceDirection, TrustEvidence, unit_value
from core.trust_state import EntityTrustState, TRUST_FIELDS, validate_entity_id
from environment.assets import ASSET_REGISTRY
from environment.identities import DEFAULT_IDENTITIES

WEIGHT_KEYS = ('identity', 'device', 'behavioral', 'historical', 'contextual')
DIMENSIONS = tuple(TrustDimension)


@dataclass(frozen=True)
class TrustModelConfig:
    known_prior: float
    unknown_prior: float
    minimum: float
    maximum: float
    weights: tuple[float, ...]
    positive_rate: float
    negative_rate: float
    recovery_rate: float
    recency: float
    history_confidence: float
    weight_tolerance: float
    version: str = 'day2c-model-v1'
    calibration_status: str = 'UNCALIBRATED'

    def __post_init__(self):
        for name in ('known_prior', 'unknown_prior', 'minimum', 'maximum', 'positive_rate',
                     'negative_rate', 'recovery_rate', 'recency', 'history_confidence'):
            unit_value(getattr(self, name), name)
        if not self.minimum < self.maximum or not self.minimum <= self.known_prior <= self.maximum:
            raise ValueError('Invalid trust bounds / known prior')
        if not self.minimum < self.unknown_prior < self.maximum:
            raise ValueError('Unknown prior must lie strictly inside bounds')
        if not 0 < self.recovery_rate <= self.positive_rate < self.negative_rate <= 1:
            raise ValueError('Require 0 < recovery <= positive < negative <= 1')
        if self.recency <= 0:
            raise ValueError('recency must be positive')
        unit_value(self.weight_tolerance, 'weight_tolerance')
        if not 0 < self.weight_tolerance <= 1e-6:
            raise ValueError('weight_tolerance must be a small positive tolerance <= 1e-6')
        object.__setattr__(self, 'weights', tuple(self.weights))
        if len(self.weights) != 5:
            raise ValueError('Exactly five weights required')
        for weight in self.weights: unit_value(weight, 'weight')
        if abs(math.fsum(self.weights) - 1) > self.weight_tolerance:
            raise ValueError('Weights must sum to 1; no automatic normalization')
        if self.version != 'day2c-model-v1' or self.calibration_status != 'UNCALIBRATED':
            raise ValueError('Unsupported trust model version/calibration status')

    @classmethod
    def load(cls, path=None):
        path = Path(path) if path is not None else Path(__file__).resolve().parents[1] / 'config' / 'trust_model.yaml'
        with path.open(encoding='utf-8') as stream: dynamic = yaml.safe_load(stream)
        required = {f.name for f in fields(cls)} - {'known_prior', 'minimum', 'maximum', 'weights'} | {'base_config'}
        if not isinstance(dynamic, dict) or set(dynamic) != required:
            raise ValueError('Trust model configuration keys do not match schema')
        base_path = dynamic.pop('base_config')
        with (path.parent / base_path).open(encoding='utf-8') as stream: base = yaml.safe_load(stream)['trust']
        if set(base) != {'initial_default', 'minimum', 'maximum', 'weights'} or set(base['weights']) != set(WEIGHT_KEYS):
            raise ValueError('Canonical trust configuration keys do not match schema')
        return cls(known_prior=base['initial_default'], minimum=base['minimum'], maximum=base['maximum'],
                   weights=tuple(base['weights'][key] for key in WEIGHT_KEYS), **dynamic)


class TrustModel:
    def __init__(self, config=None):
        self._config = config if config is not None else TrustModelConfig.load()
        if not isinstance(self._config, TrustModelConfig): raise TypeError('Expected TrustModelConfig')
        self._known = frozenset(['asset:' + key for key in ASSET_REGISTRY] +
                                ['identity:' + i.identity_id for i in DEFAULT_IDENTITIES])
        self._states = {}
        self._deliveries = {}

    @property
    def config(self):
        return self._config

    def _composite(self, values):
        # Clip only floating-point boundary drift; never normalize weights.
        return min(self.config.maximum, max(self.config.minimum,
                   math.fsum(weight * value for weight, value in zip(self.config.weights, values))))

    def initialize_entity(self, entity_id):
        validate_entity_id(entity_id)
        if entity_id in self._states:
            return self._states[entity_id]
        prior = self.config.known_prior if entity_id in self._known else self.config.unknown_prior
        state = EntityTrustState(entity_id, *([prior] * 5), self._composite([prior] * 5))
        self._states[entity_id] = state
        self._deliveries[entity_id] = set()
        return state

    def get_state(self, entity_id):
        return self._states[entity_id]

    def update(self, entity_id, evidence_batch, *, delivery_token, observation_number):
        """Apply one entity-local observation, using opaque transport ordering only.

        Correlated evidence is rejected: stamp original event metadata after this call.
        Invalid batches fail atomically without consuming a token or ordinal.
        """
        state = self.get_state(entity_id)
        if not isinstance(delivery_token, str) or not delivery_token.strip():
            raise ValueError('delivery_token must be nonempty and opaque to scoring')
        if delivery_token in self._deliveries[entity_id]:
            raise ValueError('Duplicate delivery')
        if type(observation_number) is not int or observation_number != state.last_sequence_number + 1:
            raise ValueError('Expected next entity-local observation number')
        if type(evidence_batch) not in (list, tuple):
            raise TypeError('Expected a list or tuple of uncorrelated TrustEvidence')
        unique = {}
        for evidence in evidence_batch:
            if type(evidence) is not TrustEvidence:
                raise TypeError('Only TrustEvidence records are accepted')
            if evidence.entity_id != entity_id:
                raise ValueError('Mixed entity batch')
            if evidence.event_id is not None or evidence.sequence_number is not None:
                raise ValueError('Attach audit correlation only after inference')
            if evidence.dimension == TrustDimension.HISTORY and evidence.direction != EvidenceDirection.NEUTRAL:
                raise ValueError('HISTORY is generated internally from prior observations')
            key = (evidence.entity_id, evidence.dimension, evidence.source, evidence.reason)
            if key in unique and unique[key] != evidence:
                raise ValueError('Conflicting duplicate evidence')
            unique[key] = evidence
        positive, negative = [0.0] * 5, [0.0] * 5
        for evidence in unique.values():
            index = DIMENSIONS.index(evidence.dimension)
            magnitude = evidence.effective_magnitude
            if evidence.direction == EvidenceDirection.POSITIVE:
                positive[index] = max(positive[index], magnitude)
            elif evidence.direction == EvidenceDirection.NEGATIVE:
                negative[index] = max(negative[index], magnitude)
        direct_positive, direct_negative = max(positive), max(negative)
        bearing = direct_positive > 0 or direct_negative > 0
        history = state.history_statistic
        if bearing:
            # Historical evidence uses the PREVIOUS statistic, never this event's z.
            if history > 0: positive[3] = history * self.config.history_confidence
            elif history < 0: negative[3] = -history * self.config.history_confidence
            z = -direct_negative if direct_negative > 0 else direct_positive
            history = (1 - self.config.recency) * history + self.config.recency * z
        counts = tuple(count + int(p > 0 or n > 0)
                       for count, p, n in zip(state.evidence_counts, positive, negative))
        if max(negative) > 0:
            positive = [0.0] * 5
        old_values = [getattr(state, name) for name in TRUST_FIELDS]
        values = []
        for x, p, n, had_negative in zip(old_values, positive, negative, state.negative_history):
            rate = self.config.recovery_rate if had_negative else self.config.positive_rate
            values.append(min(self.config.maximum, max(self.config.minimum, x + rate * p - self.config.negative_rate * n)))
        next_state = EntityTrustState(entity_id, *values, self._composite(values),
            observation_count=state.observation_count + 1, last_sequence_number=observation_number,
            version=state.version + 1, history_statistic=history,
            negative_history=tuple(old or n > 0 for old, n in zip(state.negative_history, negative)),
            evidence_counts=counts)
        self._states[entity_id] = next_state
        self._deliveries[entity_id].add(delivery_token)
        return next_state
