"""Deterministic causal correlation over current and prior local assessments."""
from pathlib import Path

import yaml

from core.correlation_assessment import (
    CorrelationAssessment, CorrelationAssessmentStatus, CorrelationEvidence,
    CorrelationEvidenceClass,
)
from core.experiment import fingerprint
from core.runtime_inputs import OBSERVABLE_FIELDS
from core.threat_assessment import ThreatAssessment, ThreatAssessmentStatus


CORRELATION_MODEL_VERSION = 'milestone6d-correlation-evidence-v1'


class CorrelationEvidenceModel:
    def __init__(self, path=None):
        path = Path(path) if path is not None else (
            Path(__file__).resolve().parents[1] / 'config' / 'correlation_evidence.yaml')
        with path.open(encoding='utf-8') as stream:
            config = yaml.safe_load(stream)
        required = {'version', 'calibration_status', 'history_window_events',
                    'minimum_distinct_sources', 'aggregation', 'evidence'}
        if not isinstance(config, dict) or set(config) != required:
            raise ValueError('Invalid correlation evidence configuration')
        if (config['version'] != CORRELATION_MODEL_VERSION or
                config['calibration_status'] != 'PROVISIONAL_UNCALIBRATED' or
                config['aggregation'] != 'MAX_EFFECTIVE_DIRECT_STRENGTH'):
            raise ValueError('Unsupported correlation evidence configuration')
        if type(config['history_window_events']) is not int or config['history_window_events'] < 1:
            raise ValueError('history_window_events must be positive')
        if config['minimum_distinct_sources'] != 2:
            raise ValueError('This model requires exactly the configured two-source minimum')
        expected_categories = {
            'MULTI_SOURCE_SAME_TARGET_SECURITY_ACTIVITY',
            'SHARED_IDENTITY_MULTI_SOURCE_SECURITY_ACTIVITY',
            'MULTI_SOURCE_SAME_TARGET_UNCERTAINTY',
            'SHARED_IDENTITY_MULTI_SOURCE_UNCERTAINTY',
        }
        if not isinstance(config['evidence'], dict) or set(config['evidence']) != expected_categories:
            raise ValueError('Unexpected correlation evidence categories')
        for category, values in config['evidence'].items():
            if set(values) != {'strength', 'confidence', 'evidence_class'}:
                raise ValueError(f'Invalid correlation evidence configuration: {category}')
            evidence_class = CorrelationEvidenceClass(values['evidence_class'])
            for name in ('strength', 'confidence'):
                value = values[name]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
                    raise ValueError(f'Invalid {category} {name}')
            if evidence_class == CorrelationEvidenceClass.UNCERTAINTY and values['strength'] != 0:
                raise ValueError('Uncertainty evidence cannot create a positive signal')
        self.config = config
        self.configuration_fingerprint = fingerprint(config)
        self.reset()

    def reset(self):
        self._history = []
        self._history_version = 0

    def _checkpoint(self):
        return ([dict(record) for record in self._history], self._history_version)

    def _restore(self, checkpoint):
        history, version = checkpoint
        self._history = [dict(record) for record in history]
        self._history_version = version

    def _evidence(self, category, observation, related, relationship_type):
        values = self.config['evidence'][category]
        related_sources = tuple(dict.fromkeys(row['source_id'] for row in related))
        related_targets = tuple(dict.fromkeys(row['target_id'] for row in related))
        references = tuple(dict.fromkeys(row['event_reference'] for row in related))
        return CorrelationEvidence(
            category=category, evidence_class=values['evidence_class'],
            current_source=observation['source_id'], related_sources=related_sources,
            current_target=observation['target_id'], related_targets=related_targets,
            relationship_type=relationship_type,
            supporting_prior_event_references=references,
            strength=values['strength'], confidence=values['confidence'],
            observable_basis=(f'{observation["source_id"]}:{observation["identity_id"]}:'
                              f'{observation["target_id"]}:{observation["operation"]}'),
            reason=(f'Current source {observation["source_id"]} and distinct prior source(s) '
                    f'{", ".join(related_sources)} share observable {relationship_type.lower()} '
                    f'within the last {self.config["history_window_events"]} events.'),
            model_version=CORRELATION_MODEL_VERSION)

    def assess(self, observation, threat_assessment, current_event_reference=None):
        if type(observation) is not dict or set(observation) != set(OBSERVABLE_FIELDS) | {'contextual_features'}:
            raise ValueError('Expected exact runtime_observation projection')
        if type(threat_assessment) is not ThreatAssessment:
            raise ValueError('Expected ThreatAssessment')
        if (threat_assessment.source_id != observation['source_id'] or
                threat_assessment.target_id != observation['target_id'] or
                threat_assessment.identity_id != observation['identity_id']):
            raise ValueError('ThreatAssessment scope mismatch')
        event_reference = current_event_reference or fingerprint(observation)
        if not isinstance(event_reference, str) or not event_reference:
            raise ValueError('current_event_reference must be nonempty text')
        window = self._history[-self.config['history_window_events']:]
        distinct = [row for row in window if row['source_id'] != observation['source_id']]
        current_direct = threat_assessment.status == ThreatAssessmentStatus.DIRECT_EVIDENCE
        current_uncertain = threat_assessment.status == ThreatAssessmentStatus.UNCERTAINTY_ONLY
        evidence = []
        same_target = [row for row in distinct if row['target_id'] == observation['target_id'] and
                       row['threat_status'] == threat_assessment.status.value]
        shared_identity = [row for row in distinct if row['identity_id'] == observation['identity_id'] and
                           row['threat_status'] == threat_assessment.status.value]
        if current_direct and same_target:
            evidence.append(self._evidence('MULTI_SOURCE_SAME_TARGET_SECURITY_ACTIVITY',
                                           observation, same_target, 'SAME_TARGET'))
        if current_direct and shared_identity:
            evidence.append(self._evidence('SHARED_IDENTITY_MULTI_SOURCE_SECURITY_ACTIVITY',
                                           observation, shared_identity, 'SHARED_IDENTITY'))
        if current_uncertain and same_target:
            evidence.append(self._evidence('MULTI_SOURCE_SAME_TARGET_UNCERTAINTY',
                                           observation, same_target, 'SAME_TARGET'))
        if current_uncertain and shared_identity:
            evidence.append(self._evidence('SHARED_IDENTITY_MULTI_SOURCE_UNCERTAINTY',
                                           observation, shared_identity, 'SHARED_IDENTITY'))
        direct = [item.effective_strength for item in evidence
                  if item.evidence_class == CorrelationEvidenceClass.DIRECT]
        status = (CorrelationAssessmentStatus.DIRECT_EVIDENCE if direct else
                  CorrelationAssessmentStatus.UNCERTAINTY_ONLY if evidence else
                  CorrelationAssessmentStatus.NO_CORRELATION_EVIDENCE)
        supporting = tuple(dict.fromkeys(
            reference for item in evidence for reference in item.supporting_prior_event_references))
        participants = tuple(dict.fromkeys(
            [observation['source_id']] +
            [source for item in evidence for source in item.related_sources])) if evidence else ()
        relevant_coverages = [threat_assessment.evidence_coverage] + [
            row['evidence_coverage'] for row in window
            if row['event_reference'] in supporting]
        unresolved = (() if status != CorrelationAssessmentStatus.UNCERTAINTY_ONLY else
                      ('Related local evidence remains uncertain; no direct coordination claim.',))
        reasons = tuple(item.reason for item in evidence) or (
            'No qualifying relationship between current and prior security-relevant local assessments.',)
        result = CorrelationAssessment(
            current_event_reference=event_reference,
            source_id=observation['source_id'], target_id=observation['target_id'],
            identity_id=observation['identity_id'], evidence=tuple(evidence),
            coordination_signal_score=max(direct, default=0.0),
            evidence_coverage=min(relevant_coverages), status=status,
            participating_entities=participants, supporting_event_references=supporting,
            history_version=self._history_version,
            configuration_fingerprint=self.configuration_fingerprint,
            unresolved_requirements=unresolved, reasons=reasons,
            model_version=CORRELATION_MODEL_VERSION)
        self._history.append({
            'event_reference': event_reference, 'source_id': observation['source_id'],
            'target_id': observation['target_id'], 'identity_id': observation['identity_id'],
            'threat_status': threat_assessment.status.value,
            'evidence_coverage': threat_assessment.evidence_coverage,
        })
        self._history_version += 1
        return result
