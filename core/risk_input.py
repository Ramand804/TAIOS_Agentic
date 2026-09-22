"""Immutable inference inputs and weight preparation; no risk scoring."""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from types import MappingProxyType

import yaml

from core.trust_evidence import TrustDimension, unit_value

COMPONENTS = ('THREAT', 'TRUST', 'CRITICALITY', 'ANOMALY')
WEIGHT_KEYS = ('threat', 'distrust', 'criticality', 'anomaly')
VERSION = 'day3b-input-v1'


def text_value(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a nonempty string')


def frozen_components(values):
    if not hasattr(values, 'keys') or set(values) != set(COMPONENTS):
        raise ValueError('Expected exactly the four risk components')
    return MappingProxyType({key: values[key] for key in COMPONENTS})


@dataclass(frozen=True)
class RiskConfig:
    """Canonical YAML weights only. Thresholds are neither changed nor activated."""
    original_weights: object

    def __post_init__(self):
        weights = frozen_components(self.original_weights)
        for key, value in weights.items():
            unit_value(value, key)
        if not math.isclose(math.fsum(weights.values()), 1, rel_tol=0, abs_tol=1e-9):
            raise ValueError('Original weights must sum to one; no implicit normalization')
        object.__setattr__(self, 'original_weights', weights)

    @classmethod
    def load(cls, path=None):
        path = Path(path) if path is not None else Path(__file__).resolve().parents[1] / 'config/risk.yaml'
        with path.open(encoding='utf-8') as stream:
            document = yaml.safe_load(stream)
        if not isinstance(document, dict) or not isinstance(document.get('risk'), dict):
            raise ValueError('Expected risk configuration')
        weights = document['risk'].get('weights')
        if not isinstance(weights, dict) or set(weights) != set(WEIGHT_KEYS):
            raise ValueError('Risk weight keys do not match the canonical schema')
        return cls(dict(zip(COMPONENTS, (weights[key] for key in WEIGHT_KEYS))))

    def to_dict(self):
        return {'version': VERSION, 'original_weights': dict(self.original_weights),
                'missing_policy': 'RENORMALIZE_AVAILABLE',
                'dependency_policy': 'EXCLUDE_OPERATIONAL_ANOMALY_WITH_TRUST',
                'calibration_status': 'UNCALIBRATED'}

    @property
    def fingerprint(self):
        encoded = json.dumps(self.to_dict(), sort_keys=True, separators=(',', ':'), allow_nan=False)
        return hashlib.sha256(encoded.encode('utf-8')).hexdigest()


@dataclass(frozen=True, kw_only=True)
class RiskInput:
    source_id: str
    target_id: str
    operation: str
    composite_trust: float
    distrust_score: float
    criticality_score: float
    trust_state_version: int
    trust_evidence_coverage: object
    prior_only_dimensions: tuple[str, ...]
    config: RiskConfig
    threat_probability: float | None = None
    threat_available: bool = False
    threat_score_kind: str = 'UNAVAILABLE'
    anomaly_score: float | None = None
    anomaly_available: bool = False
    anomaly_category: str = 'NONE'
    reasons: tuple[str, ...] = ()

    def __post_init__(self):
        for name in ('source_id', 'target_id', 'operation'):
            text_value(getattr(self, name), name)
        for name in ('composite_trust', 'distrust_score', 'criticality_score'):
            unit_value(getattr(self, name), name)
        if not math.isclose(self.distrust_score, 1-self.composite_trust, rel_tol=0, abs_tol=1e-12):
            raise ValueError('Distrust must be the complement of supplied trust')
        if type(self.trust_state_version) is not int or self.trust_state_version < 0:
            raise ValueError('trust_state_version must be a nonnegative integer')
        if type(self.config) is not RiskConfig:
            raise ValueError('Expected RiskConfig')
        for available, value in ((self.threat_available, self.threat_probability),
                                 (self.anomaly_available, self.anomaly_score)):
            if type(available) is not bool or available != (value is not None):
                raise ValueError('Availability must explicitly agree with a non-null value')
            if available:
                unit_value(value, 'available signal')
        kinds = {'CONFIDENCE', 'CALIBRATED_PROBABILITY'} if self.threat_available else {'UNAVAILABLE'}
        if self.threat_score_kind not in kinds:
            raise ValueError('Threat score kind disagrees with availability')
        if self.anomaly_category not in {'NONE', 'INDEPENDENT', 'OPERATIONAL_LIMIT_SHARED_WITH_TRUST'}:
            raise ValueError('Unknown anomaly category')
        if self.anomaly_available != (self.anomaly_category == 'INDEPENDENT'):
            raise ValueError('Only independent anomaly evidence may be available alongside trust')
        dimensions = tuple(d.value for d in TrustDimension)
        coverage = self.trust_evidence_coverage
        if not hasattr(coverage, 'keys') or set(coverage) != set(dimensions):
            raise ValueError('Expected all five trust coverage dimensions')
        validated = {}
        for dimension in dimensions:
            signs = tuple(coverage[dimension])
            if signs not in (('POSITIVE',), ('NEGATIVE',), ('POSITIVE', 'NEGATIVE'), ('INSUFFICIENT',)):
                raise ValueError('Invalid trust evidence coverage')
            validated[dimension] = signs
        object.__setattr__(self, 'trust_evidence_coverage', MappingProxyType(validated))
        prior = tuple(self.prior_only_dimensions)
        if len(set(prior)) != len(prior) or any(d not in dimensions for d in prior):
            raise ValueError('Invalid prior-only dimensions')
        object.__setattr__(self, 'prior_only_dimensions', tuple(d for d in dimensions if d in prior))
        if isinstance(self.reasons, str) or not self.reasons:
            raise ValueError('Expected nonempty reasons')
        for reason in self.reasons:
            text_value(reason, 'reason')
        object.__setattr__(self, 'reasons', tuple(self.reasons))

    @property
    def entity_id(self):
        return 'asset:' + self.source_id

    @property
    def component_availability(self):
        return MappingProxyType(dict(zip(COMPONENTS, (
            'AVAILABLE' if self.threat_available else 'MISSING', 'AVAILABLE', 'AVAILABLE',
            'AVAILABLE' if self.anomaly_available else
            ('EXCLUDED_CORRELATED' if self.anomaly_category == 'OPERATIONAL_LIMIT_SHARED_WITH_TRUST' else 'MISSING')))))

    @property
    def original_weights(self):
        return self.config.original_weights

    @property
    def coverage(self):
        return math.fsum(self.original_weights[k] for k, v in self.component_availability.items() if v == 'AVAILABLE')

    @property
    def effective_weights(self):
        total = self.coverage
        return MappingProxyType({key: (None if total == 0 else
            self.original_weights[key]/total if self.component_availability[key] == 'AVAILABLE' else 0.0)
            for key in COMPONENTS})

    @property
    def coverage_details(self):
        states = self.component_availability
        return {'included_components': [k for k in COMPONENTS if states[k] == 'AVAILABLE'],
                'observed_components': [k for k in COMPONENTS if states[k] == 'AVAILABLE'],
                'missing_components': [k for k in COMPONENTS if states[k] == 'MISSING'],
                'excluded_components': [k for k in COMPONENTS if states[k] == 'EXCLUDED_CORRELATED'],
                'original_weight_coverage': self.coverage, 'observation_weight_coverage': self.coverage,
                'status': ('INSUFFICIENT_INPUTS' if self.coverage == 0 else 'INCOMPLETE'
                    if any(self.original_weights[k] > 0 and states[k] != 'AVAILABLE' for k in COMPONENTS)
                    or any(v == ('INSUFFICIENT',) for v in self.trust_evidence_coverage.values())
                    else 'COMPONENTS_PRESENT')}

    def to_dict(self):
        result = {name: getattr(self, name) for name in (
            'source_id', 'target_id', 'operation', 'entity_id', 'composite_trust', 'distrust_score',
            'criticality_score', 'trust_state_version', 'threat_probability', 'threat_available',
            'threat_score_kind', 'anomaly_score', 'anomaly_available', 'anomaly_category', 'coverage')}
        result.update(trust_evidence_coverage={k: list(v) for k, v in self.trust_evidence_coverage.items()},
                      prior_only_dimensions=list(self.prior_only_dimensions), reasons=list(self.reasons),
                      component_availability=dict(self.component_availability), coverage_details=self.coverage_details,
                      original_weights=dict(self.original_weights), effective_weights=dict(self.effective_weights),
                      configuration_fingerprint=self.config.fingerprint, configuration_version=VERSION,
                      calibration_status='UNCALIBRATED')
        return result
