"""Read-only health and evidence projection; no command or execution methods."""
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class IndustrialHealth:
    status: str
    operating_mode: str
    state_version: int
    audit_entries: int
    observed_at: datetime


class IndustrialReadModel:
    def __init__(self, runtime, audit_log, clock=None):
        self._runtime = runtime
        self._audit_log = audit_log
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def health(self):
        return IndustrialHealth(
            "HEALTHY" if self._audit_log.verify() else "AUDIT_CHAIN_INVALID",
            self._runtime.operating_mode().value,
            self._runtime.cell.state.state_version,
            len(self._audit_log.entries()),
            self._clock(),
        )

    def snapshot(self):
        health = self.health()
        return {
            "health": health.status, "operating_mode": health.operating_mode,
            "state_version": health.state_version, "audit_entries": health.audit_entries,
            "process_state": self._runtime.cell.state,
        }
