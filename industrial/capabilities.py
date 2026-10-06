"""Opaque, one-shot execution capabilities for the industrial simulator."""
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from hmac import compare_digest
from secrets import token_urlsafe
from threading import Lock

from industrial.process.commands import ProcessCommand
from industrial.process.enums import ProcessAsset, ProcessOperation


@dataclass(frozen=True)
class ExecutionCapability:
    authorization_id: str
    capability_token: str


@dataclass
class AuthorizationRecord:
    authorization_id: str
    transaction_id: str
    event_id: str
    target: str
    operation: str
    value: object
    state_version: int
    expires_at: datetime
    token_hash: str
    operating_mode: object
    consumed: bool = False
    revoked: bool = False


class ExecutionAuthorizationStore:
    """Authoritative records. It is retained privately by trusted composition only."""

    def __init__(self):
        self._records = {}
        self._lock = Lock()

    def _issue(self, transaction_id, event_id, target, operation, value, state_version, expires_at, operating_mode):
        token = token_urlsafe(32)
        authorization_id = f"cap-{token_urlsafe(12)}"
        record = AuthorizationRecord(
            authorization_id, transaction_id, event_id, target, operation, value,
            state_version, expires_at, sha256(token.encode()).hexdigest(), operating_mode,
        )
        with self._lock:
            self._records[authorization_id] = record
        return ExecutionCapability(authorization_id, token)

    def _claim(self, capability, now, state_version):
        with self._lock:
            authorization_id = getattr(capability, "authorization_id", None)
            token = getattr(capability, "capability_token", "")
            record = self._records.get(authorization_id)
            if (
                record is None or record.revoked or record.consumed or now > record.expires_at
                or record.state_version != state_version
                or not compare_digest(record.token_hash, sha256(token.encode()).hexdigest())
            ):
                return None
            record.consumed = True
            return record

    def _revoke(self, authorization_id):
        with self._lock:
            record = self._records.get(authorization_id)
            if record is None or record.consumed:
                return False
            record.revoked = True
            return True


class CapabilityExecutionGateway:
    """Only capability-backed commands can reach ManufacturingCell.apply()."""

    def __init__(self, cell, claim_capability, clock, operating_mode_provider):
        self._cell = cell
        self._claim_capability = claim_capability
        self._clock = clock
        self._operating_mode_provider = operating_mode_provider

    def execute(self, capability):
        record = self._claim_capability(capability, self._clock(), self._cell.state.state_version)
        if record is None:
            return False, "CAPABILITY_REJECTED", self._cell.state.state_version
        if self._operating_mode_provider() != record.operating_mode:
            return False, "OPERATING_MODE_MISMATCH", self._cell.state.state_version
        command = ProcessCommand(
            record.authorization_id,
            ProcessAsset(record.target),
            ProcessOperation(record.operation),
            record.value,
            self._clock(),
            record.state_version,
        )
        result = self._cell.apply(command)
        return result.allowed, result.interlock.status.value, self._cell.state.state_version


class ExecutionCapabilityIssuer:
    """Issues a capability only from records registered by trusted services."""

    def __init__(self, governance_store, review_store, issue_capability, cell, operating_mode_provider, clock):
        self._governance_store = governance_store
        self._review_store = review_store
        self._issue_capability = issue_capability
        self._cell = cell
        self._operating_mode_provider = operating_mode_provider
        self._clock = clock

    def issue(self, governance_id, review_id=None):
        governance = self._governance_store.get(governance_id)
        if (
            governance is None
            or governance.status.name not in ("APPROVED", "REVIEW_REQUIRED")
            or self._clock() > governance.expires_at
            or self._cell.state.state_version != governance.state_version
            or self._operating_mode_provider() != governance.operating_mode
        ):
            return None

        expiry = governance.expires_at
        if governance.requires_human_review:
            review = self._review_store.get(review_id)
            expected = (
                governance.decision_id, governance.transaction_id, governance.runtime_event_id,
                governance.state_version, governance.target_id, governance.operation,
                governance.requested_value,
            )
            actual = None if review is None else (
                review.governance_decision_id, review.transaction_id, review.runtime_event_id,
                review.state_version, review.target_id, review.operation, review.requested_value,
            )
            if (
                review is None or review.status.name != "APPROVED" or not review.reviewer_id
                or self._clock() > review.expires_at or actual != expected
            ):
                return None
            expiry = min(expiry, review.expires_at)

        return self._issue_capability(
            governance.transaction_id, governance.runtime_event_id, governance.target_id,
            governance.operation, governance.requested_value, governance.state_version,
            expiry, governance.operating_mode,
        )
