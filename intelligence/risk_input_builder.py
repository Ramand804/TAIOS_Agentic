"""Label-safe adapter only. No detector, trust update or final risk calculation."""
from types import SimpleNamespace

from core.risk_input import RiskConfig, RiskInput, text_value
from core.runtime_inputs import OBSERVABLE_FIELDS
from core.trust_assessment import TrustAssessment
from core.trust_evidence import TrustDimension, unit_value
from environment.industrial_environment import OperatingMode, ProductionState
from environment.validators import validate_event_asset_integrity


def build_risk_input(safe_observation, trust_assessment, *, config=None, threat_assessment=None):
    """Caller pairs the current observation/assessment; audit never enters output."""
    o = safe_observation
    if type(o) is not dict or set(o) != set(OBSERVABLE_FIELDS) | {'contextual_features'}:
        raise ValueError('Expected exact safe observation, not raw event/evaluation data')
    for name in OBSERVABLE_FIELDS:
        if name not in {'requested_value', 'authentication_status', 'asset_criticality'}:
            text_value(o[name], name)
    if type(o['authentication_status']) is not bool:
        raise ValueError('authentication_status must be boolean')
    unit_value(o['asset_criticality'], 'asset_criticality')
    context = o['contextual_features']
    if type(context) is not dict or not set(context) <= {'production_state', 'operating_mode'}:
        raise ValueError('Only approved observable context fields are accepted')
    for key, enum in (('production_state', ProductionState), ('operating_mode', OperatingMode)):
        if key in context:
            enum(context[key])
    # Reuse Day-1 checks through a projection-only structural adapter. The
    # constant error label is not an experimental ID or an inference feature.
    validate_event_asset_integrity(SimpleNamespace(**o, event_id='risk-input'))
    if type(trust_assessment) is not TrustAssessment:
        raise ValueError('Expected public TrustAssessment')
    trust = trust_assessment.to_inference_dict()
    if trust['entity_id'] != 'asset:' + o['source_id']:
        raise ValueError('TrustAssessment entity does not match observation source')
    supported_behavior = trust['evidence_coverage']['BEHAVIOR'] != ['INSUFFICIENT']
    category = 'OPERATIONAL_LIMIT_SHARED_WITH_TRUST' if supported_behavior else 'NONE'
    threat_values = dict(
        threat_probability=None, threat_available=False, threat_score_kind='UNAVAILABLE',
        threat_assessment_reference=None, threat_evidence_coverage=None,
        threat_unavailable_reason='NO_THREAT_ASSESSMENT')
    threat_reason = 'NO_THREAT_ASSESSMENT: Threat signal is unavailable, not zero.'
    if threat_assessment is not None:
        from core.threat_assessment import ThreatAssessment, ThreatAssessmentStatus
        if type(threat_assessment) is not ThreatAssessment:
            raise ValueError('Expected ThreatAssessment')
        if (threat_assessment.source_id != o['source_id'] or
                threat_assessment.target_id != o['target_id'] or
                threat_assessment.identity_id != o['identity_id']):
            raise ValueError('ThreatAssessment scope does not match observation')
        threat_values.update(
            threat_assessment_reference=threat_assessment.reference,
            threat_evidence_coverage=threat_assessment.evidence_coverage)
        if threat_assessment.status == ThreatAssessmentStatus.DIRECT_EVIDENCE:
            threat_values.update(
                threat_probability=threat_assessment.security_signal_score,
                threat_available=True, threat_score_kind='SECURITY_SIGNAL',
                threat_unavailable_reason=None)
            threat_reason = ('THREAT_DIRECT_EVIDENCE: Uncalibrated security signal is available; '
                             'it is not attack probability.')
        elif (threat_assessment.status == ThreatAssessmentStatus.NO_SECURITY_EVIDENCE and
              threat_assessment.evidence_coverage == 1):
            threat_values.update(
                threat_probability=0.0, threat_available=True,
                threat_score_kind='SECURITY_SIGNAL', threat_unavailable_reason=None)
            threat_reason = ('THREAT_CHECKS_COMPLETE_NO_EVIDENCE: All configured observable checks '
                             'were established and emitted no direct evidence; zero is observed, not proof of benign behavior.')
        elif threat_assessment.status == ThreatAssessmentStatus.UNCERTAINTY_ONLY:
            threat_values['threat_unavailable_reason'] = 'THREAT_EVIDENCE_UNCERTAIN'
            threat_reason = ('THREAT_EVIDENCE_UNCERTAIN: Score zero is not treated as confirmed '
                             'absence of threat evidence.')
        else:
            threat_values['threat_unavailable_reason'] = 'THREAT_EVIDENCE_INCOMPLETE'
            threat_reason = ('THREAT_EVIDENCE_INCOMPLETE: No direct evidence was emitted, but '
                             'configured observable checks were incomplete.')
    return RiskInput(
        source_id=o['source_id'], target_id=o['target_id'], operation=o['operation'],
        composite_trust=trust['composite_trust'], distrust_score=1-trust['composite_trust'],
        criticality_score=o['asset_criticality'], trust_state_version=trust['trust_state_version'],
        trust_evidence_coverage=trust['evidence_coverage'],
        prior_only_dimensions=tuple(d.value for d, count in zip(TrustDimension, trust['evidence_counts']) if count == 0),
        config=RiskConfig.load() if config is None else config, anomaly_category=category,
        **threat_values,
        reasons=('TRUST_PUBLIC_CONTRACT: Post-observation source trust; evidence coverage retained.',
                 'TARGET_REGISTRY: Criticality agrees with the registered target.',
                 threat_reason,
                 'EXCLUDED_CORRELATED: Operational behavior already contributes through trust; no independent anomaly.'
                 if supported_behavior else
                 'NO_INDEPENDENT_ANOMALY: Behavioral evidence is insufficient; anomaly remains unknown.'))
