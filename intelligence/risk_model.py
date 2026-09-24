"""Stateless available-component risk arithmetic; no detection or decisions."""
from dataclasses import fields
import math

from core.risk_input import COMPONENTS, RiskInput
from core.risk_assessment import RiskAssessment

MODEL_VERSION = 'day3c-model-v1'
THREAT_INTEGRATION_MODEL_VERSION = 'milestone6c-risk-threat-integration-v1'
BOUNDARY_TOLERANCE = 1e-12


class RiskModel:
    def evaluate(self, risk_input):
        """Use the immutable configuration already bound to the supplied input."""
        if type(risk_input) is not RiskInput:
            raise ValueError('Expected RiskInput, not raw observations or assessments')
        weights = risk_input.effective_weights
        availability = risk_input.component_availability
        values = dict(zip(COMPONENTS, (
            risk_input.threat_signal, risk_input.distrust_score,
            risk_input.criticality_score, risk_input.anomaly_score)))
        reasons = list(risk_input.reasons)
        if risk_input.coverage == 0:
            score = None
            contributions = {key: None for key in COMPONENTS}
            reasons.append('INSUFFICIENT_INPUTS: No available component has positive original weight; risk is unknown.')
        else:
            contributions = {key: weights[key] * values[key]
                             if availability[key] == 'AVAILABLE' else 0.0
                             for key in COMPONENTS}
            score = math.fsum(contributions.values())
            # Correct only representational roundoff, never invalid inputs.
            if not -BOUNDARY_TOLERANCE <= score <= 1 + BOUNDARY_TOLERANCE:
                raise ValueError('Computed risk lies outside numeric tolerance')
            score = min(1.0, max(0.0, score))
            reasons.append(f'RENORMALIZED: Available original weight is {risk_input.coverage:.12g}.')
        for key in COMPONENTS:
            if availability[key] == 'AVAILABLE':
                subject = (f'Source {risk_input.source_id} distrust' if key == 'TRUST' else
                           f'Target {risk_input.target_id} criticality' if key == 'CRITICALITY' else key)
                amount = 'unknown (no usable weight)' if contributions[key] is None else f'{contributions[key]:.12g}'
                reasons.append(f'{subject}: value {values[key]:.12g}; contribution {amount}.')
            elif availability[key] == 'EXCLUDED_CORRELATED':
                reasons.append(f'{key}: Correlated operational evidence excluded upstream; no independent anomaly contribution.')
            else:
                reasons.append(f'{key}: Signal unavailable; no value imputed.')
        payload = {field.name: getattr(risk_input, field.name) for field in fields(RiskInput)}
        payload['reasons'] = tuple(reasons)
        model_version = (THREAT_INTEGRATION_MODEL_VERSION
                         if risk_input.threat_assessment_reference is not None
                         else MODEL_VERSION)
        return RiskAssessment(**payload, risk_score=score, component_contributions=contributions,
                              model_version=model_version)
