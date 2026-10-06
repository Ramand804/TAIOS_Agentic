"""Trusted composition root for industrial governance, review, and execution."""
from industrial.capabilities import (
    CapabilityExecutionGateway,
    ExecutionAuthorizationStore,
    ExecutionCapabilityIssuer,
)
from industrial.process.model import ManufacturingCell
from industrial.runtime.governance import OperatingMode
from industrial.trusted_services import HumanReviewService, IndustrialGovernanceService
from industrial.runtime.lifecycle import IndustrialLifecycle


class _ReadOnlyStore:
    def __init__(self, getter):
        self.__getter = getter

    def get(self, key):
        return self.__getter(key)

    def contains(self, key):
        return self.get(key) is not None


class TrustedRuntime:
    def __init__(self, governance, clock, mode=OperatingMode.SIMULATION):
        governance_records, review_records = {}, {}
        self.__mode = OperatingMode(mode)
        self.cell = ManufacturingCell()
        self.governance_store = _ReadOnlyStore(governance_records.get)
        self.review_store = _ReadOnlyStore(review_records.get)

        # Registration closures and authorization records stay local to composition.
        authorization_records = ExecutionAuthorizationStore()
        self.governance_service = IndustrialGovernanceService(
            governance, lambda decision: governance_records.__setitem__(decision.decision_id, decision)
        )
        self.review_service = HumanReviewService(
            self.governance_store,
            lambda review: review_records.__setitem__(review.review_id, review),
            clock,
        )
        self.lifecycle = IndustrialLifecycle(self.governance_service, clock)
        self.issuer = ExecutionCapabilityIssuer(
            self.governance_store, self.review_store, authorization_records._issue,
            self.cell, lambda: self.__mode, clock,
        )
        self.execution_gateway = CapabilityExecutionGateway(
            self.cell, authorization_records._claim, clock, lambda: self.__mode
        )
        self.__revoke_capability = authorization_records._revoke

    def operating_mode(self):
        return self.__mode

    def set_mode(self, mode):
        """Trusted configuration transition; runtime events never invoke this method."""
        self.__mode = OperatingMode(mode)

    def revoke_capability(self, capability):
        """Trusted lifecycle operation for explicit revocation tests and shutdown handling."""
        return self.__revoke_capability(getattr(capability, "authorization_id", None))


def build_trusted_runtime(governance, clock, mode=OperatingMode.SIMULATION):
    return TrustedRuntime(governance, clock, mode)
