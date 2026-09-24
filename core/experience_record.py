"""Immutable reference chain for one committed runtime experience."""
from dataclasses import dataclass

from core.decision_contracts import Record
from core.risk_input import text_value
from core.trust_evidence import unit_value


EXPERIENCE_VERSION = 'milestone7a-experience-v1'


@dataclass(frozen=True, kw_only=True)
class ExperienceRecord(Record):
    event_reference: str
    source_id: str
    target_id: str
    operation: str
    requested_value: object
    semantic_assessment_reference: str
    threat_assessment_reference: str
    correlation_assessment_reference: str
    trust_assessment_reference: str
    risk_assessment_reference: str
    authorization_assessment_reference: str
    authority_assessment_reference: str
    planning_result_reference: str
    proposed_decision_reference: str
    governance_decision_reference: str
    execution_result_reference: str
    observed_outcome_reference: str
    state_before_reference: str
    state_after_reference: str
    trust_before: float
    trust_after: float
    risk_score: float
    risk_coverage: float
    experience_version: str = EXPERIENCE_VERSION

    def __post_init__(self):
        for name in (
                'event_reference', 'source_id', 'target_id', 'operation',
                'semantic_assessment_reference', 'threat_assessment_reference',
                'correlation_assessment_reference', 'trust_assessment_reference',
                'risk_assessment_reference', 'authorization_assessment_reference',
                'authority_assessment_reference', 'planning_result_reference',
                'proposed_decision_reference', 'governance_decision_reference',
                'execution_result_reference', 'observed_outcome_reference',
                'state_before_reference', 'state_after_reference', 'experience_version'):
            text_value(getattr(self, name), name)
        for name in ('trust_before', 'trust_after', 'risk_score', 'risk_coverage'):
            unit_value(getattr(self, name), name)
        if self.experience_version != EXPERIENCE_VERSION:
            raise ValueError('Unsupported experience version')
