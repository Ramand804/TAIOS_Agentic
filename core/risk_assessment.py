"""Future evaluated-output contract. No factory computes a risk score."""
from dataclasses import dataclass
import math

from core.risk_input import COMPONENTS, RiskInput, frozen_components, text_value
from core.trust_assessment import AuditCorrelation
from core.trust_evidence import unit_value


@dataclass(frozen=True, kw_only=True)
class RiskAssessment(RiskInput):
    risk_score: float | None
    component_contributions: object
    model_version: str
    audit: AuditCorrelation | None = None

    def __post_init__(self):
        super().__post_init__()
        text_value(self.model_version, 'model_version')
        contributions = frozen_components(self.component_contributions)
        if self.coverage == 0:
            if self.risk_score is not None or any(v is not None for v in contributions.values()):
                raise ValueError('No weighted inputs requires null score and contributions')
        else:
            unit_value(self.risk_score, 'risk_score')
            values = dict(zip(COMPONENTS, (self.threat_probability, self.distrust_score,
                                          self.criticality_score, self.anomaly_score)))
            for key, value in contributions.items():
                unit_value(value, 'contribution')
                expected = self.effective_weights[key] * values[key] if values[key] is not None else 0.0
                if not math.isclose(value, expected, rel_tol=0, abs_tol=1e-12):
                    raise ValueError('Supplied contribution disagrees with input/effective weight')
            if not math.isclose(math.fsum(contributions.values()), self.risk_score, rel_tol=0, abs_tol=1e-12):
                raise ValueError('Supplied contributions do not sum to supplied risk_score')
        object.__setattr__(self, 'component_contributions', contributions)
        if self.audit is not None and type(self.audit) is not AuditCorrelation:
            raise ValueError('Expected separated AuditCorrelation')

    def to_inference_dict(self):
        result = super().to_dict()
        result.update(risk_score=self.risk_score, component_contributions=dict(self.component_contributions),
                      model_version=self.model_version, assessment_status=self.coverage_details['status'])
        return result

    def to_dict(self):
        result = self.to_inference_dict()
        result['audit'] = None if self.audit is None else {
            'event_id': self.audit.event_id, 'sequence_number': self.audit.sequence_number}
        return result
