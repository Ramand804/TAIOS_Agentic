"""Prepare observable semantics, never candidate lists or selected actions."""
from dataclasses import replace

from core.decision_context import (DecisionContext, CapabilityEnvelope, PolicyContext,
    OperationalValidity, load_policy_definitions)
from core.experiment import fingerprint
from core.risk_assessment import RiskAssessment
from core.trust_assessment import TrustAssessment
from environment.industrial_environment import IndustrialState, StateSnapshot
from environment.operational_limits import OperationalLimits
from intelligence.risk_input_builder import build_risk_input


def build_decision_context(safe_observation, trust_assessment, risk_assessment, *,
                           industrial_state=None, operational_limits=None,
                           policy_context=None, capability_context=None):
    if type(trust_assessment) is not TrustAssessment or type(risk_assessment) is not RiskAssessment:
        raise ValueError('Expected TrustAssessment and RiskAssessment')
    # Validates exact safe schema and existing authoritative asset semantics.
    build_risk_input(safe_observation,trust_assessment,config=risk_assessment.config)
    if trust_assessment.audit is not None and risk_assessment.audit is not None and trust_assessment.audit!=risk_assessment.audit:
        raise ValueError('Assessment audit correlation mismatch')
    o=safe_observation; context=o['contextual_features']; state_version=None
    if industrial_state is not None:
        if type(industrial_state) not in (IndustrialState,StateSnapshot): raise ValueError('Expected industrial state or snapshot')
        for name in ('production_state','operating_mode'):
            if name not in context or context[name]!=getattr(industrial_state,name).value:
                raise ValueError('Industrial state disagrees with observable current context')
        state_version=industrial_state.state_version
    limits=OperationalLimits() if operational_limits is None else operational_limits
    if type(limits) is not OperationalLimits: raise ValueError('Expected OperationalLimits')
    mode=context.get('operating_mode'); check=None
    if mode is None:
        reason='MISSING_MODE: No current mode; no fallback assumed.'
    else:
        try:
            check=limits.check_operational_limit(o['target_id'],o['operation'],o['requested_value'],mode)
            reason='CURRENT_MODE_LIMIT: Approved range checked; no transformation selected.'
        except KeyError:
            reason='MISSING_LIMIT: Operation/mode semantics unavailable.'
    validity=OperationalValidity(operating_mode=mode,reference_id=fingerprint(limits.to_dict()),check=check,reason=reason)
    ref=fingerprint(o)
    expected=CapabilityEnvelope(source_id=o['source_id'],target_id=o['target_id'],operation=o['operation'],
                                observation_reference=ref,operational_validity=validity)
    if capability_context is not None and (type(capability_context) is not CapabilityEnvelope or capability_context!=expected):
        raise ValueError('Capability context disagrees with current observation/limits')
    policies=PolicyContext(observation_reference=ref,policies=load_policy_definitions()) if policy_context is None else policy_context
    return DecisionContext(observation=o,trust_assessment=replace(trust_assessment,audit=None),
        risk_assessment=replace(risk_assessment,audit=None),capabilities=expected,policy_context=policies,state_version=state_version)
