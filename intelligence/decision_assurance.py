"""Stateless categorical evidence gate that can only restrict autonomy."""
from pathlib import Path

import yaml

from core.actions import Action
from core.assurance_assessment import (
    AssuranceAssessment, AssuranceCausalEffect, AssuranceEvidence, AssuranceStatus,
)
from core.autonomous_authority import AutonomousAuthorityAssessment, AuthorityStatus
from core.correlation_assessment import CorrelationAssessmentStatus
from core.drift_assessment import DriftStatus
from core.experiment import fingerprint
from core.operational_semantics import SemanticStatus
from core.threat_assessment import ThreatAssessmentStatus


ASSURANCE_POLICY_VERSION = 'milestone8b-decision-assurance-v1'
PERMISSIVE = (Action.ALLOW, Action.MONITOR)


class DecisionAssuranceGate:
    def __init__(self, *, enabled=None, path=None):
        path = Path(path) if path is not None else (
            Path(__file__).resolve().parents[1] / 'config' / 'decision_assurance.yaml')
        with path.open(encoding='utf-8') as stream:
            config = yaml.safe_load(stream)
        expected = {'version', 'enabled', 'direct_threat_review',
                    'persistent_unexplained_drift_review', 'trust_corroboration_required',
                    'risk_context_enabled', 'correlation_direct_review',
                    'known_regime_change_exemption', 'calibration_status'}
        if not isinstance(config, dict) or set(config) != expected:
            raise ValueError('Invalid assurance configuration')
        if config['version'] != ASSURANCE_POLICY_VERSION:
            raise ValueError('Unsupported assurance policy version')
        self.config = dict(config)
        if enabled is not None:
            self.config['enabled'] = bool(enabled)
        self.enabled = self.config['enabled']
        self.configuration_fingerprint = fingerprint(self.config)

    @staticmethod
    def _item(category, source, basis, reason):
        return AssuranceEvidence(category=category, source_reference=source,
                                 observable_basis=basis, reason=reason)

    def assess(self, *, event_reference, authority, trust, threat, risk, drift,
               correlation, semantics, authorization):
        trust_reference = fingerprint(trust.to_inference_dict())
        risk_reference = fingerprint(risk.to_inference_dict())
        existing = tuple(action.value for action in Action
                         if authority.status_for(action) == AuthorityStatus.PERMITTED)
        permissive = tuple(action.value for action in PERMISSIVE if action.value in existing)
        evidence = []
        adverse = []
        if threat.status == ThreatAssessmentStatus.DIRECT_EVIDENCE:
            adverse.append('DIRECT_THREAT')
            evidence.append(self._item(
                'DIRECT_SECURITY_EVIDENCE_PRESENT', threat.reference,
                f'{threat.direct_evidence_count} provenance-backed direct evidence item(s)',
                'Direct observable threat evidence requires review when autonomy exists.'))
        if drift.status == DriftStatus.UNEXPLAINED_PERSISTENT_DRIFT:
            adverse.append('PERSISTENT_DRIFT')
            evidence.append(self._item(
                'PERSISTENT_UNEXPLAINED_DRIFT', drift.reference,
                f'persistence_count={drift.persistence_count}',
                'Persistent unexplained behavioral change requires review; cause is not inferred.'))
        if correlation.status == CorrelationAssessmentStatus.DIRECT_EVIDENCE:
            adverse.append('DIRECT_CORRELATION')
            evidence.append(self._item(
                'CORRELATION_DIRECT_EVIDENCE', correlation.reference,
                f'{len(correlation.supporting_event_references)} supporting event reference(s)',
                'Direct cross-entity correlation evidence requires review when autonomy exists.'))
        elif correlation.status == CorrelationAssessmentStatus.UNCERTAINTY_ONLY:
            evidence.append(self._item(
                'INCOMPLETE_SECURITY_EVIDENCE', correlation.reference,
                'correlation status UNCERTAINTY_ONLY',
                'Correlation uncertainty is not adverse confirmation.'))
        known_regime = (drift.status == DriftStatus.KNOWN_REGIME_CHANGE and
                        semantics.semantic_status == SemanticStatus.SUPPORTED_VALID)
        if known_regime:
            evidence.append(self._item(
                'KNOWN_REGIME_CHANGE_EXPLAINED', drift.reference,
                drift.context_explanation or 'explicit valid operating context',
                'A valid known regime change is exempt from drift-only restriction.'))
        if trust.trust_delta < 0 and adverse:
            evidence.append(self._item(
                'TRUST_DEGRADATION_WITH_CORROBORATION', trust_reference,
                f'trust_delta={trust.trust_delta:.12g}',
                'Trust degradation is recorded only with independent adverse evidence.'))
        if self.config['risk_context_enabled']:
            evidence.append(self._item(
                'RISK_CONTEXT_RECORDED', risk_reference,
                f'risk_score={risk.risk_score:.12g}; coverage={risk.coverage:.12g}',
                'Numeric risk is contextual evidence and never independently restricts authority.'))

        unresolved = tuple(dict.fromkeys(
            tuple(threat.unresolved_requirements) +
            tuple(correlation.unresolved_requirements) +
            tuple(drift.unresolved_requirements)))
        if not self.enabled:
            status = AssuranceStatus.NOT_APPLICABLE
            effect = AssuranceCausalEffect.ASSURANCE_DISABLED
            assured = existing
            restrictions = ()
        elif adverse and permissive:
            status = AssuranceStatus.AUTONOMY_RESTRICTED
            effect = AssuranceCausalEffect.ASSURANCE_RESTRICTED_AUTHORITY
            restrictions = permissive
            assured = tuple(action.value for action in Action
                            if action.value in set(existing) - set(permissive) or
                            action == Action.REQUEST_APPROVAL)
        elif adverse:
            status = AssuranceStatus.REVIEW_REQUIRED
            effect = AssuranceCausalEffect.ALREADY_RESTRICTED_UPSTREAM
            restrictions = ()
            assured = existing
        elif known_regime and permissive:
            status = AssuranceStatus.AUTONOMY_CONFIRMED
            effect = AssuranceCausalEffect.ASSESSMENT_ONLY
            restrictions = ()
            assured = existing
        elif permissive:
            status = AssuranceStatus.INSUFFICIENT_ASSURANCE
            effect = AssuranceCausalEffect.ASSESSMENT_ONLY
            restrictions = ()
            assured = existing
            evidence.append(self._item(
                'NO_ADVERSE_SECURITY_EVIDENCE', threat.reference,
                threat.status.value,
                'No categorical adverse evidence is observed; absence is not proof of safety.'))
        else:
            status = AssuranceStatus.NOT_APPLICABLE
            effect = AssuranceCausalEffect.ASSESSMENT_ONLY
            restrictions = ()
            assured = existing
        coverage = (threat.evidence_coverage + correlation.evidence_coverage + risk.coverage) / 3
        return AssuranceAssessment(
            event_reference=event_reference, authority_reference=authority.reference,
            trust_reference=trust_reference, threat_reference=threat.reference,
            risk_reference=risk_reference, drift_reference=drift.reference,
            correlation_reference=correlation.reference, status=status,
            causal_effect=effect, existing_permitted_actions=existing,
            assured_permitted_actions=assured, restrictions=restrictions,
            evidence_items=tuple(evidence), coverage=coverage,
            unresolved_requirements=unresolved,
            policy_version=ASSURANCE_POLICY_VERSION,
            configuration_fingerprint=self.configuration_fingerprint)

    @staticmethod
    def apply(authority, assurance):
        if authority.reference != assurance.authority_reference:
            raise ValueError('Assurance/authority chain mismatch')
        assured = set(assurance.assured_permitted_actions)
        statuses = {
            action.value: (AuthorityStatus.PERMITTED.value if action.value in assured else
                           AuthorityStatus.NOT_PERMITTED.value
                           if authority.status_for(action) == AuthorityStatus.PERMITTED else
                           authority.status_for(action).value)
            for action in Action}
        reasons = {
            action.value: tuple(authority.reasons[action.value]) +
            ((f'ASSURANCE: {assurance.status.value}; action authority restricted or review introduced.',)
             if statuses[action.value] != authority.action_authority[action.value] else ())
            for action in Action}
        return AutonomousAuthorityAssessment(
            source_id=authority.source_id, identity_id=authority.identity_id,
            target_id=authority.target_id, operation=authority.operation,
            authorization_status=authority.authorization_status,
            operational_validity=authority.operational_validity,
            action_authority=statuses,
            matched_policy_ids=authority.matched_policy_ids,
            unresolved_requirements=authority.unresolved_requirements,
            reasons=reasons,
            authority_policy_version=authority.authority_policy_version,
            authority_policy_fingerprint=authority.authority_policy_fingerprint,
            context_input_reference=authority.context_input_reference)
