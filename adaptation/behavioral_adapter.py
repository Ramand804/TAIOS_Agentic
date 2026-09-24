"""Deterministic gate for contextual behavioral-reference adaptation."""
from collections import defaultdict
from pathlib import Path

import yaml

from core.behavioral_reference import (
    AdaptationDecision, AdaptationMode, AdaptationProposal, AdaptationStatus,
    BehavioralReferenceSnapshot, ProposalStatus,
)
from core.drift_assessment import DriftAssessment, DriftStatus
from core.experiment import fingerprint
from core.feedback_assessment import FeedbackAssessment, FeedbackStatus
from core.operational_semantics import OperationalSemanticAssessment, SemanticStatus
from memory.behavioral_reference_store import BehavioralReferenceStore


ADAPTATION_VERSION = 'milestone7d-behavioral-adaptation-v1'


class BehavioralAdapter:
    def __init__(self, *, mode=None, store=None, path=None):
        path = Path(path) if path is not None else (
            Path(__file__).resolve().parents[1] / 'config' / 'behavioral_adaptation.yaml')
        with path.open(encoding='utf-8') as stream:
            config = yaml.safe_load(stream)
        expected = {'version', 'calibration_status', 'default_mode',
                    'minimum_new_regime_observations', 'eligible_drift_statuses',
                    'required_semantic_status', 'required_feedback_dimensions',
                    'baseline_scope', 'summary_method'}
        if not isinstance(config, dict) or set(config) != expected:
            raise ValueError('Invalid behavioral adaptation configuration')
        if (config['version'] != ADAPTATION_VERSION or
                config['calibration_status'] != 'PROVISIONAL_UNCALIBRATED' or
                config['eligible_drift_statuses'] != ['KNOWN_REGIME_CHANGE'] or
                config['required_semantic_status'] != 'SUPPORTED_VALID' or
                config['baseline_scope'] != 'SOURCE_TARGET_OPERATION_CONTEXT' or
                config['summary_method'] != 'COUNT_MEAN_MIN_MAX'):
            raise ValueError('Unsupported behavioral adaptation configuration')
        minimum = config['minimum_new_regime_observations']
        if type(minimum) is not int or minimum < 2:
            raise ValueError('minimum_new_regime_observations must be at least two')
        self.config = config
        self.configuration_fingerprint = fingerprint(config)
        self.mode = AdaptationMode(mode or config['default_mode'])
        self.store = store or BehavioralReferenceStore()
        self.reset()

    def reset(self):
        self.store.reset()
        self._support = defaultdict(list)
        self._history = []

    @staticmethod
    def _context(observation):
        values = observation['contextual_features']
        return {'operating_mode': values.get('operating_mode'),
                'production_state': values.get('production_state')}

    @staticmethod
    def _context_key(scope, context):
        return f'{scope}|{context.get("operating_mode")}|{context.get("production_state")}'

    def _checkpoint(self):
        return ({key: [dict(item) for item in values]
                 for key, values in self._support.items()},
                tuple(self._history), self.store._checkpoint())

    def _restore(self, checkpoint):
        support, history, store = checkpoint
        self._support = defaultdict(list, {
            key: [dict(item) for item in values] for key, values in support.items()})
        self._history = list(history)
        self.store._restore(store)

    def evaluate(self, observation, semantics, drift, feedback):
        if type(semantics) is not OperationalSemanticAssessment:
            raise ValueError('Expected OperationalSemanticAssessment')
        if type(drift) is not DriftAssessment:
            raise ValueError('Expected DriftAssessment')
        if type(feedback) is not FeedbackAssessment:
            raise ValueError('Expected FeedbackAssessment')
        if drift.event_reference != feedback.event_reference:
            raise ValueError('Adaptation input chain mismatch')
        context = self._context(observation)
        context_key = self._context_key(drift.scope, context)
        current = self.store.get(drift.scope, context)
        unresolved = []
        feedback_ready = (
            feedback.feedback_status == FeedbackStatus.OBSERVABLE_FEEDBACK and
            all(item in feedback.available_dimensions
                for item in self.config['required_feedback_dimensions']))
        known = drift.status == DriftStatus.KNOWN_REGIME_CHANGE
        valid = semantics.semantic_status == SemanticStatus.SUPPORTED_VALID

        if self.mode == AdaptationMode.STATIC:
            proposal_status = ProposalStatus.NOT_ELIGIBLE
            unresolved.append('Behavioral adaptation is disabled in STATIC mode.')
        elif drift.status == DriftStatus.UNEXPLAINED_PERSISTENT_DRIFT:
            proposal_status = ProposalStatus.NOT_ELIGIBLE
            unresolved.append('Unexplained behavior cannot redefine the behavioral reference.')
        elif current is not None:
            proposal_status = ProposalStatus.NOT_ELIGIBLE
            unresolved.append('A governed behavioral reference already exists for this context.')
        elif not known:
            proposal_status = ProposalStatus.NOT_ELIGIBLE
            unresolved.append(f'{drift.status.value} is not eligible for adaptation.')
        elif not valid:
            proposal_status = ProposalStatus.NOT_ELIGIBLE
            unresolved.append('A supported-valid semantic assessment is required.')
        elif not all(context.values()):
            proposal_status = ProposalStatus.NOT_ELIGIBLE
            unresolved.append('Explicit operating mode and production state are required.')
        elif not feedback_ready:
            proposal_status = ProposalStatus.DEFERRED
            unresolved.append('Observable execution, state-effect, and operational feedback are required.')
        else:
            support = self._support[context_key]
            if not any(item['drift_reference'] == drift.reference for item in support):
                support.append({'drift_reference': drift.reference,
                                'event_reference': drift.event_reference,
                                'feedback_reference': feedback.reference,
                                'value': observation['requested_value']})
            if len(support) < self.config['minimum_new_regime_observations']:
                proposal_status = ProposalStatus.DEFERRED
                unresolved.append(
                    f'{self.config["minimum_new_regime_observations"]} supported new-regime observations are required.')
            else:
                proposal_status = ProposalStatus.ELIGIBLE

        support = self._support.get(context_key, [])
        values = [item['value'] for item in support]
        candidate = ({'count': len(values), 'mean': sum(values) / len(values),
                      'minimum': min(values), 'maximum': max(values)} if values else None)
        proposal = AdaptationProposal(
            trigger_drift_reference=drift.reference,
            event_reference=drift.event_reference, scope=drift.scope,
            context_key=context_key, status=proposal_status,
            current_reference=current.reference if current else None,
            candidate_reference=fingerprint(candidate) if candidate else None,
            candidate_summary=candidate,
            observable_support=tuple(item['drift_reference'] for item in support),
            semantic_support=semantics.semantic_status.value,
            feedback_support=feedback.feedback_status.value,
            unresolved_requirements=tuple(unresolved),
            proposal_version=ADAPTATION_VERSION,
            configuration_fingerprint=self.configuration_fingerprint)

        if (self.mode == AdaptationMode.ADAPTIVE and
                drift.status == DriftStatus.UNEXPLAINED_PERSISTENT_DRIFT):
            status = AdaptationStatus.REJECTED
            reasons = ('Unexplained persistent drift is a baseline-poisoning risk.',)
        elif proposal_status == ProposalStatus.DEFERRED:
            status = AdaptationStatus.DEFERRED
            reasons = tuple(unresolved)
        elif proposal_status != ProposalStatus.ELIGIBLE:
            status = AdaptationStatus.NOT_ELIGIBLE
            reasons = tuple(unresolved)
        else:
            version = 1 if current is None else current.version + 1
            provenance = tuple(
                f'{item["event_reference"]}:{item["feedback_reference"]}' for item in support)
            snapshot = BehavioralReferenceSnapshot(
                scope=drift.scope, sample_count=len(values),
                reference_summary=candidate, operating_context=context,
                version=version, provenance_references=provenance,
                model_version=ADAPTATION_VERSION)
            self.store.put(snapshot)
            status = AdaptationStatus.APPLIED
            reasons = ('Known context, valid semantics, causal outcome feedback, and minimum support established.',)

        after = self.store.get(drift.scope, context)
        decision = AdaptationDecision(
            proposal_reference=proposal.reference, status=status, reasons=reasons,
            authorized_update=status == AdaptationStatus.APPLIED,
            before_reference=current.reference if current else None,
            after_reference=after.reference if status == AdaptationStatus.APPLIED else None,
            policy_version=ADAPTATION_VERSION,
            configuration_fingerprint=self.configuration_fingerprint)
        self._history.append((proposal, decision))
        return proposal, decision

    @property
    def history(self):
        return tuple(self._history)
