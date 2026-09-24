"""Experimental fixed-prior trust adapter; not part of frozen TAIOS inference."""
from core.trust_assessment import TrustAssessment
from intelligence.trust_model import TrustModelConfig
from intelligence.trust_evidence_extractor import EvidenceConfig, TrustEvidenceExtractor


NO_TRUST_VERSION = 'milestone8a-no-trust-v1'


class FixedNeutralTrustAgent:
    def __init__(self):
        self.config = TrustModelConfig.load()
        self.fixed_value = self.config.known_prior
        self._extractor = TrustEvidenceExtractor(EvidenceConfig.load())
        self.reset()

    def reset(self):
        self._states = {}
        self._deliveries = set()

    def _checkpoint(self):
        return dict(self._states), set(self._deliveries)

    def _restore(self, checkpoint):
        states, deliveries = checkpoint
        self._states = dict(states)
        self._deliveries = set(deliveries)

    def assess(self, observation, *, delivery_token, observation_number,
               correlation_metadata=None):
        if not isinstance(delivery_token, str) or not delivery_token:
            raise ValueError('delivery_token must be nonempty')
        if delivery_token in self._deliveries:
            raise ValueError('Duplicate delivery')
        entity_id = f'asset:{observation["source_id"]}'
        evidence = tuple(self._extractor.extract(observation))
        prior = self._states.get(entity_id)
        expected = 1 if prior is None else prior.observation_count + 1
        if observation_number != expected:
            raise ValueError('Expected next entity-local observation number')
        value = self.fixed_value
        result = TrustAssessment(
            entity_id=entity_id,
            identity_trust=value, device_trust=value, behavioral_trust=value,
            historical_trust=value, contextual_trust=value, composite_trust=value,
            observation_count=observation_number, last_sequence_number=observation_number,
            version=observation_number, history_statistic=0.0,
            negative_history=(False,) * 5, evidence_counts=(0,) * 5,
            previous_composite_trust=value, trust_delta=0.0,
            previous_behavioral_trust=value, evidence=evidence,
            reasons=(f'Experimental fixed known-entity prior {value:.2f}; numeric dynamic trust disabled.',
                     'Observable evidence coverage is retained for frozen authority prerequisites.'),
            audit=correlation_metadata)
        self._states[entity_id] = result
        self._deliveries.add(delivery_token)
        return result
