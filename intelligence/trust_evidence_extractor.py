"""Stateless extraction from the exact Day-1 runtime projection schema."""
from dataclasses import dataclass, fields
import math
from pathlib import Path
from types import MappingProxyType

import yaml

from core.runtime_inputs import OBSERVABLE_FIELDS
from core.trust_evidence import TrustEvidence, unit_value
from environment.assets import ASSET_REGISTRY
from environment.identities import DEFAULT_IDENTITIES
from environment.industrial_environment import OperatingMode, ProductionState
from environment.operational_limits import OperationalLimits


@dataclass(frozen=True)
class EvidenceConfig:
    version: str
    calibration_status: str
    identity_positive_strength: float
    identity_negative_strength: float
    identity_confidence: float
    device_positive_strength: float
    device_negative_strength: float
    device_confidence: float
    behavior_positive_strength: float
    behavior_confidence: float
    deviation_saturation: float

    def __post_init__(self):
        if self.version != 'day2b-evidence-v1' or self.calibration_status != 'UNCALIBRATED':
            raise ValueError('Unsupported evidence version/calibration status')
        for field in fields(self):
            if field.name not in {'version', 'calibration_status', 'deviation_saturation'}:
                unit_value(getattr(self, field.name), field.name)
        value = self.deviation_saturation
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError('deviation_saturation must be finite and positive')

    @classmethod
    def load(cls, path=None):
        path = Path(path) if path is not None else Path(__file__).resolve().parents[1] / 'config' / 'trust_evidence.yaml'
        with path.open(encoding='utf-8') as stream:
            values = yaml.safe_load(stream)
        if not isinstance(values, dict) or set(values) != {field.name for field in fields(cls)}:
            raise ValueError('Evidence configuration keys do not match the schema')
        return cls(**values)


class TrustEvidenceExtractor:
    def __init__(self, config=None, operational_limits=None):
        self.config = config if config is not None else EvidenceConfig.load()
        if not isinstance(self.config, EvidenceConfig):
            raise TypeError('config must be EvidenceConfig')
        self.assets = MappingProxyType(dict(ASSET_REGISTRY))
        self.identities = frozenset(identity.identity_id for identity in DEFAULT_IDENTITIES)
        self.limits = operational_limits if operational_limits is not None else OperationalLimits()
        if not isinstance(self.limits, OperationalLimits):
            raise TypeError('operational_limits must be OperationalLimits')

    @staticmethod
    def _validate(observation):
        if type(observation) is not dict or set(observation) != set(OBSERVABLE_FIELDS) | {'contextual_features'}:
            raise ValueError('Expected exact runtime_observation projection, not a raw event or enriched record')
        for name in OBSERVABLE_FIELDS:
            if name not in {'requested_value', 'authentication_status', 'asset_criticality'}:
                if not isinstance(observation[name], str) or not observation[name].strip():
                    raise ValueError(f'{name} must be a nonempty string')
        if type(observation['authentication_status']) is not bool:
            raise ValueError('authentication_status must be bool')
        unit_value(observation['asset_criticality'], 'asset_criticality')
        context = observation['contextual_features']
        if type(context) is not dict or not set(context) <= {'production_state', 'operating_mode'}:
            raise ValueError('Context must use only the existing safe projection fields')
        if 'production_state' in context:
            ProductionState(context['production_state'])
        if 'operating_mode' in context:
            OperatingMode(context['operating_mode'])

    def extract(self, observation):
        self._validate(observation)
        o, c = observation, self.config
        entity = 'asset:' + o['source_id']

        def item(dimension, direction, strength, confidence, reason):
            return TrustEvidence(entity, dimension, direction, strength, confidence,
                                 f'{c.version}:{dimension.lower()}', reason)

        def neutral(dimension, reason):
            return item(dimension, 'NEUTRAL', 0, 0, reason)

        identity = o['identity_id']
        if not o['authentication_status']:
            identity_evidence = item('IDENTITY', 'NEGATIVE', c.identity_negative_strength,
                                     c.identity_confidence, f'AUTH_FAILURE: Authentication failed for {identity}.')
        elif identity in self.identities:
            identity_evidence = item('IDENTITY', 'POSITIVE', c.identity_positive_strength,
                                     c.identity_confidence, f'AUTH_SUCCESS: Registered identity {identity} authenticated; authorization is not established.')
        else:
            identity_evidence = neutral('IDENTITY', f'UNKNOWN_IDENTITY: No trusted identity reference for {identity}; authentication success is insufficient.')

        source = self.assets.get(o['source_id'])
        if source is None:
            device_evidence = neutral('DEVICE', 'UNKNOWN_SOURCE: No registered device reference; no adverse inference.')
        else:
            mismatches = [name for name, actual, expected in (
                ('source_type', o['source_type'], source.asset_type),
                ('network_zone', o['network_zone'], source.network_zone),
                ('protocol', o['protocol'], source.protocol)) if actual != expected]
            if mismatches:
                device_evidence = item('DEVICE', 'NEGATIVE', c.device_negative_strength,
                                       c.device_confidence, 'DEVICE_MISMATCH: Registered source differs in ' + ', '.join(mismatches) + '.')
            else:
                device_evidence = item('DEVICE', 'POSITIVE', c.device_positive_strength,
                                       c.device_confidence, 'DEVICE_MATCH: Source type, network zone and protocol match the registered device; no attestation implied.')

        context = o['contextual_features']
        mode = context.get('operating_mode')
        has_reference = any(asset == o['target_id'] and operation == o['operation']
                            for asset, operation, _ in self.limits.limits)
        if not has_reference:
            behavior_evidence = neutral('BEHAVIOR', 'MISSING_LIMIT: No approved target/operation limits; no conformance conclusion.')
        elif mode is None:
            behavior_evidence = neutral('BEHAVIOR', 'MISSING_MODE: Current operating mode is unavailable; no fallback assumed.')
        elif (o['target_id'], o['operation'], OperatingMode(mode)) not in self.limits.limits:
            behavior_evidence = neutral('BEHAVIOR', 'MISSING_MODE_LIMIT: No approved limit for this operating mode.')
        else:
            limit = self.limits.check_operational_limit(o['target_id'], o['operation'], o['requested_value'], mode)
            facts = f"Value {limit.requested_value} in {mode}; inclusive limit [{limit.minimum}, {limit.maximum}], deviation {limit.deviation:.12g}."
            if limit.within_limit:
                behavior_evidence = item('BEHAVIOR', 'POSITIVE', c.behavior_positive_strength,
                                         c.behavior_confidence, 'WITHIN_LIMIT: ' + facts)
            else:
                behavior_evidence = item('BEHAVIOR', 'NEGATIVE', min(1, limit.deviation / c.deviation_saturation),
                                         c.behavior_confidence, 'OUTSIDE_LIMIT: ' + facts)

        missing = [name for name in ('production_state', 'operating_mode') if name not in context]
        context_evidence = neutral('CONTEXT',
            'MISSING_CONTEXT: Unavailable ' + ', '.join(missing) + '; no contextual conclusion.' if missing else
            'NO_CONTEXT_RULE: Production state and operating mode are available, but no independent context compatibility rule is approved.')
        history_evidence = neutral('HISTORY', 'NO_HISTORY: Day 2B does not retain or infer historical evidence.')
        return [identity_evidence, device_evidence, behavior_evidence, history_evidence, context_evidence]
