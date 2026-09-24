"""Immutable multidimensional interpretation of observable runtime feedback."""
from dataclasses import dataclass
from enum import Enum

from core.decision_contracts import Record, texts
from core.risk_input import text_value
from core.trust_evidence import unit_value


FEEDBACK_VERSION = 'milestone7b-feedback-v1'


class FeedbackStatus(str, Enum):
    OBSERVABLE_FEEDBACK = 'OBSERVABLE_FEEDBACK'
    PARTIAL_FEEDBACK = 'PARTIAL_FEEDBACK'
    INSUFFICIENT_FEEDBACK = 'INSUFFICIENT_FEEDBACK'
    PENDING_EXTERNAL_FEEDBACK = 'PENDING_EXTERNAL_FEEDBACK'


class ExecutionFeedback(str, Enum):
    TECHNICAL_EXECUTION_SUCCEEDED = 'TECHNICAL_EXECUTION_SUCCEEDED'
    SUCCESSFUL_NOOP_CONFIRMED = 'SUCCESSFUL_NOOP_CONFIRMED'
    EXTERNAL_APPROVAL_PENDING = 'EXTERNAL_APPROVAL_PENDING'
    EXECUTION_PREVENTED = 'EXECUTION_PREVENTED'
    EXECUTION_RESULT_PARTIAL = 'EXECUTION_RESULT_PARTIAL'


class StateEffectFeedback(str, Enum):
    EXPECTED_STATE_EFFECT_OBSERVED = 'EXPECTED_STATE_EFFECT_OBSERVED'
    EXPECTED_NOOP_OBSERVED = 'EXPECTED_NOOP_OBSERVED'
    STATE_EFFECT_NOT_OBSERVED = 'STATE_EFFECT_NOT_OBSERVED'
    STATE_EFFECT_PARTIALLY_OBSERVED = 'STATE_EFFECT_PARTIALLY_OBSERVED'
    STATE_EFFECT_PENDING = 'STATE_EFFECT_PENDING'


class SecurityFeedback(str, Enum):
    UNAVAILABLE = 'UNAVAILABLE'


class OperationalFeedback(str, Enum):
    REQUESTED_STATE_OBSERVED = 'REQUESTED_STATE_OBSERVED'
    AUTHORIZED_NOOP_OBSERVED = 'AUTHORIZED_NOOP_OBSERVED'
    OPERATIONAL_EFFECT_PENDING = 'OPERATIONAL_EFFECT_PENDING'
    OPERATIONAL_EFFECT_UNAVAILABLE = 'OPERATIONAL_EFFECT_UNAVAILABLE'


@dataclass(frozen=True, kw_only=True)
class FeedbackEvidence(Record):
    category: str
    dimension: str
    observable_basis: str
    source_reference: str
    factual_reason: str

    def __post_init__(self):
        for name in ('category', 'dimension', 'observable_basis',
                     'source_reference', 'factual_reason'):
            text_value(getattr(self, name), name)
        if self.dimension not in {'EXECUTION', 'STATE_EFFECT', 'OPERATIONAL'}:
            raise ValueError('Unsupported feedback evidence dimension')


@dataclass(frozen=True, kw_only=True)
class FeedbackAssessment(Record):
    experience_reference: str
    event_reference: str
    execution_reference: str
    outcome_reference: str
    source_id: str
    target_id: str
    operation: str
    feedback_status: FeedbackStatus
    execution_feedback: ExecutionFeedback
    state_effect_feedback: StateEffectFeedback
    security_feedback: SecurityFeedback
    operational_feedback: OperationalFeedback
    evidence_items: tuple[FeedbackEvidence, ...]
    feedback_coverage: float
    available_dimensions: tuple[str, ...]
    unresolved_feedback_requirements: tuple[str, ...]
    feedback_version: str = FEEDBACK_VERSION

    def __post_init__(self):
        for name in ('experience_reference', 'event_reference', 'execution_reference',
                     'outcome_reference', 'source_id', 'target_id', 'operation',
                     'feedback_version'):
            text_value(getattr(self, name), name)
        object.__setattr__(self, 'feedback_status', FeedbackStatus(self.feedback_status))
        object.__setattr__(self, 'execution_feedback', ExecutionFeedback(self.execution_feedback))
        object.__setattr__(self, 'state_effect_feedback', StateEffectFeedback(self.state_effect_feedback))
        object.__setattr__(self, 'security_feedback', SecurityFeedback(self.security_feedback))
        object.__setattr__(self, 'operational_feedback', OperationalFeedback(self.operational_feedback))
        evidence = tuple(self.evidence_items)
        if any(type(item) is not FeedbackEvidence for item in evidence):
            raise ValueError('Expected FeedbackEvidence records')
        object.__setattr__(self, 'evidence_items', evidence)
        dimensions = tuple(self.available_dimensions)
        allowed = ('EXECUTION', 'STATE_EFFECT', 'SECURITY', 'OPERATIONAL')
        if len(dimensions) != len(set(dimensions)) or any(value not in allowed for value in dimensions):
            raise ValueError('Invalid available feedback dimensions')
        object.__setattr__(self, 'available_dimensions',
                           tuple(value for value in allowed if value in dimensions))
        unit_value(self.feedback_coverage, 'feedback_coverage')
        if self.feedback_coverage != len(dimensions) / len(allowed):
            raise ValueError('Feedback coverage must equal available dimension fraction')
        object.__setattr__(self, 'unresolved_feedback_requirements',
                           texts(self.unresolved_feedback_requirements))
        if self.feedback_version != FEEDBACK_VERSION:
            raise ValueError('Unsupported feedback version')
        if self.security_feedback != SecurityFeedback.UNAVAILABLE or 'SECURITY' in dimensions:
            raise ValueError('Current runtime cannot establish security correctness feedback')

    @property
    def configuration_fingerprint(self):
        from core.experiment import fingerprint
        return fingerprint({
            'feedback_version': self.feedback_version,
            'dimensions': ['EXECUTION', 'STATE_EFFECT', 'SECURITY', 'OPERATIONAL'],
            'security_feedback_policy': 'UNAVAILABLE_WITHOUT_EXTERNAL_CONFIRMATION',
            'coverage_policy': 'AVAILABLE_DIMENSION_FRACTION',
        })

    def to_dict(self):
        result = super().to_dict()
        result.update(
            configuration_fingerprint=self.configuration_fingerprint,
            interpretation=('Technical execution and state feedback do not establish security '
                            'correctness or policy quality.'))
        return result
