from datetime import timedelta

from industrial.runtime.human_review import HumanReviewDecision, ReviewStatus


class IndustrialGovernanceService:
    """Trusted service that is the only governance-decision registrar."""

    def __init__(self, governance, register_governance):
        self._governance = governance
        self.__register_governance = register_governance

    def evaluate(self, transaction):
        decision = self._governance.review(transaction)
        self.__register_governance(decision)
        return decision


class HumanReviewService:
    """Creates reviews bound to an authoritative governance decision."""

    def __init__(self, governance_store, register_review, clock, ttl=60):
        self._governance_store = governance_store
        self.__register_review = register_review
        self._clock = clock
        self._ttl = ttl

    def decide(self, governance_decision_id, reviewer_id, approved):
        governance = self._governance_store.get(governance_decision_id)
        if governance is None or not reviewer_id:
            return None
        review = HumanReviewDecision(
            review_id=f"REV-{governance_decision_id}",
            governance_decision_id=governance_decision_id,
            transaction_id=governance.transaction_id,
            runtime_event_id=governance.runtime_event_id,
            target_id=governance.target_id,
            operation=governance.operation,
            requested_value=governance.requested_value,
            state_version=governance.state_version,
            reviewer_id=reviewer_id,
            status=ReviewStatus.APPROVED if approved else ReviewStatus.REJECTED,
            expires_at=self._clock() + timedelta(seconds=self._ttl),
        )
        self.__register_review(review)
        return review
