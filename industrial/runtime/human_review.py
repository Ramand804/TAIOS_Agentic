from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ReviewStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class HumanReviewDecision:
    review_id: str
    governance_decision_id: str
    transaction_id: str
    runtime_event_id: str
    target_id: str
    operation: str
    requested_value: object
    state_version: int
    reviewer_id: str | None
    status: ReviewStatus
    expires_at: datetime
