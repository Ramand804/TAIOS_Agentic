"""Explicit V2 review records; approval never fabricates execution authority."""
from dataclasses import dataclass
from enum import Enum
from core.experiment import fingerprint

class ReviewStatus(str, Enum):
    PENDING_HUMAN_REVIEW='PENDING_HUMAN_REVIEW'
    APPROVED='APPROVED'
    REJECTED='REJECTED'

@dataclass(frozen=True)
class HumanReviewRequest:
    review_id: str; event_reference: str; context_reference: str
    governance_reference: str; proposal_reference: str; status: ReviewStatus
    requested_action: str | None

@dataclass(frozen=True)
class HumanReviewResolution:
    review_id: str; status: ReviewStatus; reviewer_id: str; reason: str
    execution_authorized: bool = False

class HumanReviewLifecycle:
    def create(self, result):
        if result.execution_result.execution_status.value != 'PENDING_APPROVAL':
            raise ValueError('Only a pending governance result can enter human review')
        return HumanReviewRequest(
            review_id=fingerprint({'event':result.event_reference,'governance':result.governance_decision.reference,'proposal':result.proposed_decision.reference}),
            event_reference=result.event_reference, context_reference=result.decision_context.reference,
            governance_reference=result.governance_decision.reference, proposal_reference=result.proposed_decision.reference,
            status=ReviewStatus.PENDING_HUMAN_REVIEW,
            requested_action=(result.proposed_decision.selected_action.value if result.proposed_decision.selected_action else None))
    def resolve(self, request, *, status, reviewer_id, reason):
        if type(request) is not HumanReviewRequest or request.status is not ReviewStatus.PENDING_HUMAN_REVIEW:
            raise ValueError('Expected a pending human-review request')
        status=ReviewStatus(status)
        if status not in (ReviewStatus.APPROVED, ReviewStatus.REJECTED):
            raise ValueError('Human review must explicitly approve or reject')
        if not isinstance(reviewer_id,str) or not reviewer_id or not isinstance(reason,str) or not reason:
            raise ValueError('Reviewer identity and reason are required')
        # This records the response only. A separately authorized, scope-bound
        # governance/execution workflow is required before any future execution.
        return HumanReviewResolution(request.review_id,status,reviewer_id,reason,False)
