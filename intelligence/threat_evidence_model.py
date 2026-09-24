"""Causal deterministic threat evidence from current observables and prior state."""
from collections import defaultdict
from pathlib import Path

import yaml

from core.authorization import AuthorizationAssessment, AuthorizationStatus
from core.experiment import fingerprint
from core.operational_semantics import OperationalSemanticAssessment, SemanticStatus
from core.runtime_inputs import OBSERVABLE_FIELDS
from core.threat_assessment import (
    ThreatAssessment, ThreatAssessmentStatus, ThreatEvidence, ThreatEvidenceClass,
)

THREAT_MODEL_VERSION = 'milestone6b-threat-evidence-v1'


class ThreatEvidenceModel:
    def __init__(self, path=None):
        path = Path(path) if path is not None else (
            Path(__file__).resolve().parents[1] / 'config' / 'threat_evidence.yaml')
        with path.open(encoding='utf-8') as stream:
            config = yaml.safe_load(stream)
        if not isinstance(config, dict) or set(config) != {
                'version', 'calibration_status', 'aggregation', 'evidence'}:
            raise ValueError('Invalid threat evidence configuration')
        if (config['version'] != THREAT_MODEL_VERSION or
                config['calibration_status'] != 'PROVISIONAL_UNCALIBRATED' or
                config['aggregation'] != 'MAX_EFFECTIVE_DIRECT_STRENGTH'):
            raise ValueError('Unsupported threat evidence configuration')
        required = {'strength', 'confidence', 'evidence_class'}
        for name, values in config['evidence'].items():
            if not isinstance(values, dict) or set(values) != required:
                raise ValueError(f'Invalid evidence configuration: {name}')
            ThreatEvidenceClass(values['evidence_class'])
            for key in ('strength', 'confidence'):
                value = values[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
                    raise ValueError(f'Invalid {name} {key}')
        self.config = config
        self.configuration_fingerprint = fingerprint(config)
        self.reset()

    def reset(self):
        self._history = defaultdict(lambda: {'version': 0, 'violations': 0,
                                             'authentication_failures': 0,
                                             'authorization_failures': 0})

    def _checkpoint(self):
        return {source: dict(values) for source, values in self._history.items()}

    def _restore(self, checkpoint):
        self._history = defaultdict(lambda: {'version': 0, 'violations': 0,
                                             'authentication_failures': 0,
                                             'authorization_failures': 0},
                                    {source: dict(values) for source, values in checkpoint.items()})

    def _item(self, category, observation, reason, semantic=None):
        values = self.config['evidence'][category]
        return ThreatEvidence(
            evidence_type=category, evidence_class=values['evidence_class'],
            source_id=observation['source_id'], target_id=observation['target_id'],
            strength=values['strength'], confidence=values['confidence'],
            observable_basis=f'{observation["source_id"]}:{observation["operation"]}:{observation["target_id"]}',
            semantic_rule_reference=(semantic.reference if semantic is not None else None),
            reason=reason, model_version=THREAT_MODEL_VERSION)

    def assess(self, observation, semantic_assessment, authorization_assessment):
        if type(observation) is not dict or set(observation) != set(OBSERVABLE_FIELDS) | {'contextual_features'}:
            raise ValueError('Expected exact runtime_observation projection')
        if type(semantic_assessment) is not OperationalSemanticAssessment:
            raise ValueError('Expected OperationalSemanticAssessment')
        if type(authorization_assessment) is not AuthorizationAssessment:
            raise ValueError('Expected AuthorizationAssessment')
        for name in ('source_id', 'target_id', 'operation'):
            if getattr(semantic_assessment, name) != observation[name]:
                raise ValueError('Semantic assessment scope mismatch')
        history = self._history[observation['source_id']]
        evidence, unresolved = [], []
        if not observation['authentication_status']:
            evidence.append(self._item(
                'AUTHENTICATION_FAILURE', observation,
                f'Authentication failed for observable identity {observation["identity_id"]}.'))
        if authorization_assessment.status == AuthorizationStatus.UNAUTHORIZED:
            evidence.append(self._item(
                'AUTHORIZATION_FAILURE', observation,
                f'Explicit authorization assessment denied {observation["operation"]} for '
                f'{observation["identity_id"]}.'))
        elif authorization_assessment.status == AuthorizationStatus.UNKNOWN:
            evidence.append(self._item(
                'AUTHORIZATION_UNRESOLVED', observation,
                'Authorization is unresolved; this is uncertainty, not evidence of attack.'))
            unresolved.append('Explicit operation authorization is unresolved.')
        if semantic_assessment.semantic_status == SemanticStatus.SUPPORTED_INVALID:
            constraints = semantic_assessment.known_constraints
            evidence.append(self._item(
                'OPERATIONAL_CONSTRAINT_VIOLATION', observation,
                f'Requested {observation["operation"]}={observation["requested_value"]} is outside '
                f'{observation["target_id"]} {constraints["operating_mode"]} inclusive range '
                f'[{constraints["minimum"]},{constraints["maximum"]}].', semantic_assessment))
            if history['violations'] > 0:
                evidence.append(self._item(
                    'REPEATED_OPERATIONAL_VIOLATION', observation,
                    f'Source {observation["source_id"]} has {history["violations"]} prior observable '
                    'operational constraint violation(s) in this episode.', semantic_assessment))
        elif semantic_assessment.semantic_status == SemanticStatus.UNDERSPECIFIED:
            evidence.append(self._item(
                'SEMANTIC_UNDERSPECIFICATION', observation,
                'Operation is recognized but required value semantics are unavailable; uncertainty only.',
                semantic_assessment))
            unresolved.extend(semantic_assessment.unresolved_semantic_requirements)
        elif semantic_assessment.semantic_status == SemanticStatus.UNSUPPORTED:
            evidence.append(self._item(
                'UNSUPPORTED_SEMANTICS', observation,
                'No complete operational envelope is declared for this request; uncertainty only.',
                semantic_assessment))
            unresolved.extend(semantic_assessment.unresolved_semantic_requirements)
        direct = [item.effective_strength for item in evidence
                  if item.evidence_class == ThreatEvidenceClass.DIRECT]
        status = (ThreatAssessmentStatus.DIRECT_EVIDENCE if direct else
                  ThreatAssessmentStatus.UNCERTAINTY_ONLY if evidence else
                  ThreatAssessmentStatus.NO_SECURITY_EVIDENCE)
        coverage = sum((True,
                        authorization_assessment.status != AuthorizationStatus.UNKNOWN,
                        semantic_assessment.fully_established)) / 3
        result = ThreatAssessment(
            source_id=observation['source_id'], target_id=observation['target_id'],
            identity_id=observation['identity_id'], evidence=tuple(evidence),
            security_signal_score=max(direct, default=0.0), evidence_coverage=coverage,
            status=status, observable_reasons=tuple(item.reason for item in evidence) or
            ('No direct or uncertainty security evidence was emitted from established observable facts.',),
            unresolved_requirements=tuple(dict.fromkeys(unresolved)),
            source_history_version=history['version'],
            prior_operational_violation_count=history['violations'],
            threat_model_version=THREAT_MODEL_VERSION,
            configuration_fingerprint=self.configuration_fingerprint)
        history['version'] += 1
        history['violations'] += semantic_assessment.semantic_status == SemanticStatus.SUPPORTED_INVALID
        history['authentication_failures'] += not observation['authentication_status']
        history['authorization_failures'] += authorization_assessment.status == AuthorizationStatus.UNAUTHORIZED
        return result
