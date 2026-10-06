"""Tamper-evident append-only audit chain for testbed evidence."""
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json


@dataclass(frozen=True)
class AuditEntry:
    sequence: int
    recorded_at: str
    category: str
    payload: dict
    previous_hash: str
    entry_hash: str


class AppendOnlyAuditLog:
    def __init__(self):
        self._entries = []

    @staticmethod
    def _hash(sequence, recorded_at, category, payload, previous_hash):
        material = json.dumps(
            {"sequence": sequence, "recorded_at": recorded_at, "category": category,
             "payload": payload, "previous_hash": previous_hash},
            sort_keys=True, default=str, separators=(",", ":"),
        )
        return sha256(material.encode()).hexdigest()

    def append(self, category, payload, recorded_at=None):
        sequence = len(self._entries) + 1
        timestamp = (recorded_at or datetime.now(timezone.utc)).isoformat()
        normalized = json.loads(json.dumps(payload, sort_keys=True, default=str))
        previous = self._entries[-1].entry_hash if self._entries else "0" * 64
        entry = AuditEntry(sequence, timestamp, str(category), normalized, previous,
                           self._hash(sequence, timestamp, category, normalized, previous))
        self._entries.append(entry)
        return entry

    def entries(self):
        return tuple(self._entries)

    def verify(self):
        previous = "0" * 64
        for index, entry in enumerate(self._entries, 1):
            if entry.sequence != index or entry.previous_hash != previous:
                return False
            if entry.entry_hash != self._hash(entry.sequence, entry.recorded_at, entry.category, entry.payload, previous):
                return False
            previous = entry.entry_hash
        return True
