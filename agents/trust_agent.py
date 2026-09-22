"""Trust orchestration only; all score calculations remain in TrustModel."""
from agents.base_agent import BaseAgent
from core.trust_assessment import AuditCorrelation, TrustAssessment
from intelligence.trust_evidence_extractor import EvidenceConfig, TrustEvidenceExtractor
from intelligence.trust_model import TrustModel, TrustModelConfig


class TrustAgent(BaseAgent):
    def __init__(self, *, model_config=None, evidence_config=None):
        self._model_config = model_config if model_config is not None else TrustModelConfig.load()
        self._evidence_config = evidence_config if evidence_config is not None else EvidenceConfig.load()
        self.reset()

    def reset(self):
        """Start an isolated run, retaining explicit configuration only."""
        self._model = TrustModel(self._model_config)
        self._extractor = TrustEvidenceExtractor(self._evidence_config)

    def assess(self, observation, *, delivery_token, observation_number, correlation_metadata=None):
        # Validate audit type before updating state, but never send it to inference.
        if correlation_metadata is not None and type(correlation_metadata) is not AuditCorrelation:
            raise ValueError('correlation_metadata must be AuditCorrelation')
        records = self._extractor.extract(observation)
        entity = records[0].entity_id
        previous = self._model.initialize_entity(entity)
        current = self._model.update(entity, records, delivery_token=delivery_token,
                                     observation_number=observation_number)
        reasons = tuple(f"{observation['operation']}: {e.reason}" for e in records)
        if current.historical_trust != previous.historical_trust:
            reasons += ('Historical trust changed from prior observable evidence retained by TrustModel; direct HISTORY coverage remains insufficient.',)
        return TrustAssessment(**current.to_dict(),
            previous_composite_trust=previous.composite_trust,
            trust_delta=current.composite_trust-previous.composite_trust,
            previous_behavioral_trust=previous.behavioral_trust,
            evidence=tuple(records), reasons=reasons, audit=correlation_metadata)
