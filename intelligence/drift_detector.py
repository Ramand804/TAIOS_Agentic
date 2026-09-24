"""Transparent causal detector for numeric behavior and explicit regime context."""
from collections import defaultdict
from pathlib import Path

import yaml

from core.drift_assessment import DriftAssessment, DriftEvidence, DriftStatus
from core.experiment import fingerprint
from core.operational_semantics import OperationalSemanticAssessment, SemanticStatus
from core.runtime_inputs import OBSERVABLE_FIELDS


DRIFT_MODEL_VERSION = 'milestone7c-drift-detection-v1'


class DriftDetector:
    def __init__(self, path=None, *, behavioral_reference_store=None, adaptive=False):
        path = Path(path) if path is not None else (
            Path(__file__).resolve().parents[1] / 'config' / 'drift_detection.yaml')
        with path.open(encoding='utf-8') as stream:
            config = yaml.safe_load(stream)
        expected = {'version', 'calibration_status', 'scope', 'minimum_history',
                    'reference_window', 'recent_window', 'persistence_requirement',
                    'normalized_change_threshold'}
        if not isinstance(config, dict) or set(config) != expected:
            raise ValueError('Invalid drift configuration')
        if (config['version'] != DRIFT_MODEL_VERSION or
                config['calibration_status'] != 'PROVISIONAL_UNCALIBRATED' or
                config['scope'] != 'SOURCE_TARGET_OPERATION'):
            raise ValueError('Unsupported drift configuration')
        for name in ('minimum_history', 'reference_window', 'recent_window',
                     'persistence_requirement'):
            if type(config[name]) is not int or config[name] < 1:
                raise ValueError(f'{name} must be positive')
        if config['recent_window'] != 1 or config['minimum_history'] < config['reference_window']:
            raise ValueError('Unsupported proof-of-concept window configuration')
        threshold = config['normalized_change_threshold']
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0 < threshold <= 1:
            raise ValueError('normalized_change_threshold must be in (0,1]')
        self.config = config
        self.configuration_fingerprint = fingerprint(config)
        self.behavioral_reference_store = behavioral_reference_store
        self.adaptive = bool(adaptive)
        self.reset()

    def reset(self):
        self._history = defaultdict(list)
        self._persistence = defaultdict(int)
        self._regimes = {}
        self._baselines = {}
        self._history_version = 0

    def _checkpoint(self):
        return ({scope: [dict(row) for row in rows] for scope, rows in self._history.items()},
                dict(self._persistence),
                {scope: dict(value) for scope, value in self._regimes.items()},
                {scope: [dict(row) for row in rows] for scope, rows in self._baselines.items()},
                self._history_version)

    def _restore(self, checkpoint):
        history, persistence, regimes, baselines, version = checkpoint
        self._history = defaultdict(list, {
            scope: [dict(row) for row in rows] for scope, rows in history.items()})
        self._persistence = defaultdict(int, persistence)
        self._regimes = {scope: dict(value) for scope, value in regimes.items()}
        self._baselines = {scope: [dict(row) for row in rows]
                           for scope, rows in baselines.items()}
        self._history_version = version

    @staticmethod
    def _scope(observation):
        return f'{observation["source_id"]}|{observation["target_id"]}|{observation["operation"]}'

    @staticmethod
    def _context(observation):
        context = observation['contextual_features']
        return {'operating_mode': context.get('operating_mode'),
                'production_state': context.get('production_state')}

    def _item(self, category, scope, feature, reference, recent, score,
              context_reference, semantic_reference, reason):
        return DriftEvidence(
            category=category, scope=scope, feature=feature,
            reference_summary=reference, recent_summary=recent,
            observed_change=score, context_reference=context_reference,
            semantic_reference=semantic_reference, reason=reason)

    def assess(self, observation, semantic_assessment, *, event_reference=None):
        if type(observation) is not dict or set(observation) != set(OBSERVABLE_FIELDS) | {'contextual_features'}:
            raise ValueError('Expected exact runtime_observation projection')
        if type(semantic_assessment) is not OperationalSemanticAssessment:
            raise ValueError('Expected OperationalSemanticAssessment')
        for name in ('source_id', 'target_id', 'operation'):
            if getattr(semantic_assessment, name) != observation[name]:
                raise ValueError('Semantic assessment scope mismatch')
        event_reference = event_reference or fingerprint(observation)
        scope = self._scope(observation)
        history = self._history[scope]
        history_count = len(history)
        context = self._context(observation)
        context_reference = fingerprint(context)
        evidence, unresolved = [], []
        score = 0.0
        persistence = self._persistence[scope]
        explanation = None
        value = observation['requested_value']
        comparable = (observation['operation'] == 'set_speed' and
                      isinstance(value, (int, float)) and not isinstance(value, bool) and
                      semantic_assessment.semantic_status in {
                          SemanticStatus.SUPPORTED_VALID, SemanticStatus.SUPPORTED_INVALID})

        if not comparable:
            status = DriftStatus.INSUFFICIENT_SEMANTIC_SCOPE
            unresolved.append(
                'A semantically comparable numeric operation identity and value are required.')
            self._persistence[scope] = 0
        else:
            prior_context = history[-1]['context'] if history else None
            context_changed = prior_context is not None and context != prior_context
            if (scope not in self._baselines and
                    history_count >= self.config['minimum_history']):
                self._baselines[scope] = [
                    dict(row) for row in history[:self.config['reference_window']]]
            reference_rows = self._baselines.get(
                scope, history[-self.config['reference_window']:])
            reference_values = [row['value'] for row in reference_rows]
            adaptive_reference = None
            if self.adaptive and self.behavioral_reference_store is not None:
                adaptive_reference = self.behavioral_reference_store.get(scope, context)
            constraints = semantic_assessment.known_constraints
            width = ((constraints['maximum'] - constraints['minimum'])
                     if constraints is not None else 1)
            if adaptive_reference is not None:
                summary = dict(adaptive_reference.reference_summary)
                reference_mean = summary['mean']
                reference_summary = dict(summary)
            elif reference_values:
                reference_mean = sum(reference_values) / len(reference_values)
                score = min(1.0, abs(value - reference_mean) / (width or 1))
            else:
                reference_mean = None
            if adaptive_reference is not None:
                score = min(1.0, abs(value - reference_mean) / (width or 1))
            else:
                reference_summary = {
                    'count': len(reference_values), 'mean': reference_mean,
                    'values': reference_values}
            recent_summary = {'count': 1, 'mean': value, 'values': [value]}

            if context_changed:
                categories = []
                if prior_context.get('operating_mode') != context.get('operating_mode'):
                    categories.append('OPERATING_MODE_CHANGE')
                if prior_context.get('production_state') != context.get('production_state'):
                    categories.append('PRODUCTION_STATE_CHANGE')
                for category in categories:
                    evidence.append(self._item(
                        category, scope, category.lower(), prior_context, context, score,
                        context_reference, semantic_assessment.reference,
                        f'Observable context changed from {prior_context} to {context}.'))
                if semantic_assessment.semantic_status == SemanticStatus.SUPPORTED_VALID:
                    status = DriftStatus.KNOWN_REGIME_CHANGE
                    explanation = ('Explicit operating/production context changed and the current '
                                   'value is valid under current-mode semantics.')
                    evidence.append(self._item(
                        'CONTEXT_EXPLAINED_SHIFT', scope, 'requested_value',
                        reference_summary, recent_summary, score, context_reference,
                        semantic_assessment.reference, explanation))
                    self._regimes[scope] = {
                        'context': context, 'reference_summary': reference_summary}
                else:
                    status = DriftStatus.TRANSIENT_DEVIATION
                    unresolved.append('Context changed but the current value is not valid under current semantics.')
                self._persistence[scope] = 0
                persistence = 0
            elif history_count < self.config['minimum_history']:
                status = DriftStatus.INSUFFICIENT_HISTORY
                unresolved.append(
                    f'At least {self.config["minimum_history"]} prior comparable observations are required.')
                self._persistence[scope] = 0
                persistence = 0
            else:
                active_regime = self._regimes.get(scope)
                shifted = score >= self.config['normalized_change_threshold']
                if (active_regime is not None and active_regime['context'] == context and
                        semantic_assessment.semantic_status == SemanticStatus.SUPPORTED_VALID and shifted):
                    status = DriftStatus.KNOWN_REGIME_CHANGE
                    explanation = ('Persistent numeric change remains valid under the explicitly '
                                   'observed current operational context.')
                    evidence.append(self._item(
                        'CONTEXT_EXPLAINED_SHIFT', scope, 'requested_value',
                        active_regime['reference_summary'], recent_summary, score,
                        context_reference, semantic_assessment.reference, explanation))
                    self._persistence[scope] = 0
                    persistence = 0
                elif shifted:
                    persistence += 1
                    self._persistence[scope] = persistence
                    evidence.append(self._item(
                        'NUMERIC_DISTRIBUTION_SHIFT', scope, 'requested_value',
                        reference_summary, recent_summary, score, context_reference,
                        semantic_assessment.reference,
                        'Current numeric value differs from the causal reference-window mean.'))
                    if persistence >= self.config['persistence_requirement']:
                        status = DriftStatus.UNEXPLAINED_PERSISTENT_DRIFT
                        category = ('UNEXPLAINED_INVALID_SHIFT'
                                    if semantic_assessment.semantic_status == SemanticStatus.SUPPORTED_INVALID
                                    else 'UNEXPLAINED_VALID_SHIFT')
                        evidence.append(self._item(
                            category, scope, 'requested_value', reference_summary,
                            recent_summary, score, context_reference,
                            semantic_assessment.reference,
                            'Configured persistence is established without an observable context explanation.'))
                    else:
                        status = DriftStatus.TRANSIENT_DEVIATION
                else:
                    status = DriftStatus.NO_CHANGE
                    self._persistence[scope] = 0
                    persistence = 0

            history.append({'value': value, 'context': context,
                            'semantic_status': semantic_assessment.semantic_status.value})

        result = DriftAssessment(
            event_reference=event_reference, scope=scope, status=status,
            evidence=tuple(evidence), history_count=history_count,
            reference_window_size=min(history_count, self.config['reference_window']),
            recent_window_size=1 if comparable else 0, change_score=score,
            persistence_count=persistence, context_explanation=explanation,
            unresolved_requirements=tuple(unresolved),
            model_version=DRIFT_MODEL_VERSION,
            configuration_fingerprint=self.configuration_fingerprint)
        self._history_version += 1
        return result
