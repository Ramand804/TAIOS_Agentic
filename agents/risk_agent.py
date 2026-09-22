"""Risk orchestration and optional pairing checks; no scoring mathematics."""
from dataclasses import replace

from agents.base_agent import BaseAgent
from core.risk_input import RiskConfig
from core.trust_assessment import AuditCorrelation, TrustAssessment
from intelligence.risk_input_builder import build_risk_input
from intelligence.risk_model import RiskModel


class RiskAgent(BaseAgent):
    def __init__(self, *, config=None):
        self._config = RiskConfig.load() if config is None else config
        if type(self._config) is not RiskConfig:
            raise ValueError('Expected RiskConfig')
        self._model = RiskModel()

    def assess(self, safe_observation, trust_assessment, *,
               expected_trust_state_version=None, correlation_metadata=None):
        """Stateless replay; caller supplies current pairing assertions when known.

        Correlation is compared as an opaque record, never parsed or scored.
        If trust lacks correlation, supplied metadata is audit attachment only.
        """
        if type(trust_assessment) is not TrustAssessment:
            raise ValueError('Expected public TrustAssessment')
        if expected_trust_state_version is not None:
            if type(expected_trust_state_version) is not int or expected_trust_state_version < 0:
                raise ValueError('expected_trust_state_version must be a nonnegative integer')
            if trust_assessment.trust_state_version != expected_trust_state_version:
                raise ValueError('TrustAssessment state version does not match expected version')
        if correlation_metadata is not None:
            if type(correlation_metadata) is not AuditCorrelation:
                raise ValueError('correlation_metadata must be AuditCorrelation')
            if trust_assessment.audit is not None and trust_assessment.audit != correlation_metadata:
                raise ValueError('TrustAssessment audit correlation does not match supplied correlation')
        risk_input = build_risk_input(safe_observation, trust_assessment, config=self._config)
        assessment = self._model.evaluate(risk_input)
        if correlation_metadata is not None:
            assessment = replace(assessment, audit=correlation_metadata)
        return assessment
