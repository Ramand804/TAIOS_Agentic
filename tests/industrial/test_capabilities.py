from datetime import datetime, timedelta, timezone

from industrial.capabilities import ExecutionCapability
from industrial.gateway.types import IndustrialRuntimeEvent, SynchronizedIndustrialState
from industrial.runtime import IndustrialContextBuilder, IndustrialDecisionEngine, IndustrialTransactionStore
from industrial.runtime.governance import IndustrialGovernance, OperatingMode
from industrial.runtime.human_review import HumanReviewDecision, ReviewStatus
from industrial.trusted_runtime import build_trusted_runtime


class Clock:
    def __init__(self):
        self.value = datetime(2026, 1, 1, tzinfo=timezone.utc)
    def __call__(self):
        return self.value
    def advance(self, seconds):
        self.value += timedelta(seconds=seconds)


def event(event_id="evt-1", value=100):
    return IndustrialRuntimeEvent(
        event_id=event_id, timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        source_id="PRODUCTION_CONTROLLER", source_type="controller", target_id="MIXER",
        target_type="mixer", identity_id="engineering-01", event_type="control_command",
        operation="START_ASSET", requested_value=None, network_zone="testbed", protocol="OPC_UA",
        authentication_status=True, asset_criticality=.85,
        contextual_features={"state_version": 0},
    )


def authoritative_transaction(runtime, clock, event_id="evt-1"):
    context = IndustrialContextBuilder().build(event(event_id), SynchronizedIndustrialState({}, 0))
    transaction = IndustrialTransactionStore(clock).create(context)
    shadow = IndustrialDecisionEngine().decide(context)
    return IndustrialTransactionStore(clock).attach_shadow(transaction, shadow)


def make_runtime(mode):
    clock = Clock()
    runtime = build_trusted_runtime(IndustrialGovernance(mode, clock), clock, mode)
    return runtime, clock


def governed(runtime, clock, event_id="evt-1"):
    transaction = authoritative_transaction(runtime, clock, event_id)
    return transaction, runtime.governance_service.evaluate(transaction)


def test_default_simulation_remains_non_executable():
    runtime, clock = make_runtime(OperatingMode.SIMULATION)
    _, decision = governed(runtime, clock)
    assert decision.status.name == "REJECTED"
    assert runtime.issuer.issue(decision.decision_id) is None
    assert runtime.cell.state.state_version == 0


def test_shadow_mode_cannot_create_mutating_capability():
    runtime, clock = make_runtime(OperatingMode.SHADOW)
    _, decision = governed(runtime, clock)
    assert decision.status.name == "REJECTED"
    assert runtime.issuer.issue(decision.decision_id) is None
    assert runtime.cell.state.state_version == 0


def test_controlled_execution_uses_authoritative_governance_and_one_shot_capability():
    runtime, clock = make_runtime(OperatingMode.CONTROLLED_EXECUTION)
    transaction, decision = governed(runtime, clock)
    assert transaction.shadow_decision.disposition.name == "REQUEST_APPROVAL"
    assert decision.status.name == "APPROVED" and not decision.requires_human_review
    assert runtime.governance_store.get(decision.decision_id) == decision
    capability = runtime.issuer.issue(decision.decision_id)
    assert capability is not None
    assert runtime.execution_gateway.execute(capability)[0]
    assert runtime.cell.state.state_version == 1
    assert not runtime.execution_gateway.execute(capability)[0]
    assert runtime.cell.state.state_version == 1


def test_supervised_requires_authoritative_bound_review_then_can_execute():
    runtime, clock = make_runtime(OperatingMode.SUPERVISED)
    transaction, decision = governed(runtime, clock)
    assert transaction.shadow_decision.disposition.name == "REQUEST_APPROVAL"
    assert decision.status.name == "REVIEW_REQUIRED" and decision.requires_human_review
    assert runtime.issuer.issue(decision.decision_id) is None
    forged = HumanReviewDecision("fake", decision.decision_id, decision.transaction_id,
        decision.runtime_event_id, decision.target_id, decision.operation,
        decision.requested_value, decision.state_version, "reviewer", ReviewStatus.APPROVED,
        clock() + timedelta(seconds=10))
    assert runtime.issuer.issue(decision.decision_id, forged.review_id) is None
    review = runtime.review_service.decide(decision.decision_id, "reviewer-01", True)
    assert runtime.review_store.get(review.review_id) == review
    capability = runtime.issuer.issue(decision.decision_id, review.review_id)
    assert capability is not None
    assert runtime.execution_gateway.execute(capability)[0]
    assert runtime.cell.state.state_version == 1


def test_mode_race_consumes_capability_without_mutation():
    runtime, clock = make_runtime(OperatingMode.CONTROLLED_EXECUTION)
    _, decision = governed(runtime, clock)
    capability = runtime.issuer.issue(decision.decision_id)
    runtime.set_mode(OperatingMode.SUPERVISED)
    assert runtime.execution_gateway.execute(capability)[1] == "OPERATING_MODE_MISMATCH"
    runtime.set_mode(OperatingMode.CONTROLLED_EXECUTION)
    assert not runtime.execution_gateway.execute(capability)[0]
    assert runtime.cell.state.state_version == 0


def test_state_races_and_expiry_prevent_mutation():
    runtime, clock = make_runtime(OperatingMode.CONTROLLED_EXECUTION)
    _, decision = governed(runtime, clock)
    runtime.cell.apply(__import__('industrial.process.commands', fromlist=['ProcessCommand']).ProcessCommand(
        "test", "MIXER", "START_ASSET", None, clock(), 0
    ))
    assert runtime.issuer.issue(decision.decision_id) is None

    runtime, clock = make_runtime(OperatingMode.CONTROLLED_EXECUTION)
    _, decision = governed(runtime, clock)
    cap = runtime.issuer.issue(decision.decision_id)
    runtime.cell.apply(__import__('industrial.process.commands', fromlist=['ProcessCommand']).ProcessCommand(
        "test", "MIXER", "START_ASSET", None, clock(), 0
    ))
    assert not runtime.execution_gateway.execute(cap)[0]
    assert runtime.cell.state.state_version == 1

    runtime, clock = make_runtime(OperatingMode.CONTROLLED_EXECUTION)
    _, decision = governed(runtime, clock)
    clock.advance(61)
    assert runtime.issuer.issue(decision.decision_id) is None


def test_forged_random_wrong_and_revoked_capabilities_fail_closed():
    runtime, clock = make_runtime(OperatingMode.CONTROLLED_EXECUTION)
    _, decision = governed(runtime, clock)
    capability = runtime.issuer.issue(decision.decision_id)
    assert not runtime.execution_gateway.execute(ExecutionCapability(capability.authorization_id, "wrong"))[0]
    assert not runtime.execution_gateway.execute(ExecutionCapability("random", "random"))[0]
    # A fresh legitimate authorization can be explicitly revoked before use.
    runtime, clock = make_runtime(OperatingMode.CONTROLLED_EXECUTION)
    _, decision = governed(runtime, clock)
    capability = runtime.issuer.issue(decision.decision_id)
    assert runtime.revoke_capability(capability)
    assert not runtime.execution_gateway.execute(capability)[0]
    assert runtime.cell.state.state_version == 0


def test_stores_expose_no_registration_or_capability_minting_api():
    runtime, clock = make_runtime(OperatingMode.CONTROLLED_EXECUTION)
    assert not hasattr(runtime.governance_store, "register")
    assert not hasattr(runtime.review_store, "register")
    assert not hasattr(runtime, "capability_store")


def test_forged_governance_and_value_identical_dto_have_no_authority():
    runtime, clock = make_runtime(OperatingMode.CONTROLLED_EXECUTION)
    _, authoritative = governed(runtime, clock)
    # A value-identical DTO is not registered merely by construction.
    copied = type(authoritative)(**authoritative.__dict__)
    assert runtime.governance_store.get(copied.decision_id) == authoritative
    assert runtime.issuer.issue("forged-governance") is None
    assert runtime.issuer.issue(copied.decision_id) is not None


def test_review_binding_and_expiry_are_enforced():
    runtime, clock = make_runtime(OperatingMode.SUPERVISED)
    _, decision = governed(runtime, clock)
    review = runtime.review_service.decide(decision.decision_id, "reviewer-01", True)
    assert runtime.issuer.issue(decision.decision_id, review.review_id) is not None

    runtime, clock = make_runtime(OperatingMode.SUPERVISED)
    _, decision = governed(runtime, clock)
    review = runtime.review_service.decide(decision.decision_id, "reviewer-01", True)
    clock.advance(61)
    assert runtime.issuer.issue(decision.decision_id, review.review_id) is None

    runtime, clock = make_runtime(OperatingMode.SUPERVISED)
    _, decision = governed(runtime, clock)
    bad = HumanReviewDecision("unregistered", "different-governance", decision.transaction_id,
        decision.runtime_event_id, decision.target_id, decision.operation, decision.requested_value,
        decision.state_version, "reviewer-01", ReviewStatus.APPROVED, clock() + timedelta(seconds=10))
    assert runtime.issuer.issue(decision.decision_id, bad.review_id) is None


def test_concurrent_replay_allows_at_most_one_process_mutation():
    from concurrent.futures import ThreadPoolExecutor
    runtime, clock = make_runtime(OperatingMode.CONTROLLED_EXECUTION)
    _, decision = governed(runtime, clock)
    capability = runtime.issuer.issue(decision.decision_id)
    with ThreadPoolExecutor(max_workers=8) as workers:
        outcomes = list(workers.map(lambda _item: runtime.execution_gateway.execute(capability)[0], range(8)))
    assert outcomes.count(True) == 1
    assert runtime.cell.state.state_version == 1


def test_lifecycle_creates_authoritative_record_and_event_cannot_change_mode():
    runtime, clock = make_runtime(OperatingMode.CONTROLLED_EXECUTION)
    result = runtime.lifecycle.assess(event("lifecycle-event"), SynchronizedIndustrialState({}, 0))
    assert result.shadow_decision.disposition.name == "REQUEST_APPROVAL"
    assert result.governance_decision.status.name == "APPROVED"
    assert runtime.operating_mode() is OperatingMode.CONTROLLED_EXECUTION
    duplicate = runtime.lifecycle.assess(event("lifecycle-event"), SynchronizedIndustrialState({}, 0))
    assert duplicate.transaction.status.name == "DUPLICATE"
    assert duplicate.governance_decision is None
