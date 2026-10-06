"""Non-mutating industrial decision lifecycle before governed execution."""
from dataclasses import dataclass

from industrial.runtime.context import IndustrialContextBuilder
from industrial.runtime.decision import IndustrialDecisionEngine
from industrial.runtime.transaction import IndustrialTransactionStore, TransactionStatus


@dataclass(frozen=True)
class IndustrialLifecycleResult:
    transaction: object
    shadow_decision: object | None
    governance_decision: object | None


class IndustrialLifecycle:
    """Creates authoritative transactions; it cannot issue or execute capabilities."""

    def __init__(self, governance_service, clock, context_builder=None, decision_engine=None, transaction_store=None):
        self._governance_service = governance_service
        self._context_builder = context_builder or IndustrialContextBuilder()
        self._decision_engine = decision_engine or IndustrialDecisionEngine()
        self._transactions = transaction_store or IndustrialTransactionStore(clock)

    def assess(self, event, synchronized_state):
        context = self._context_builder.build(event, synchronized_state)
        transaction = self._transactions.create(context)
        if transaction.status is TransactionStatus.DUPLICATE:
            return IndustrialLifecycleResult(transaction, transaction.shadow_decision, None)
        shadow = self._decision_engine.decide(context)
        transaction = self._transactions.attach_shadow(transaction, shadow)
        governance = self._governance_service.evaluate(transaction)
        return IndustrialLifecycleResult(transaction, shadow, governance)
