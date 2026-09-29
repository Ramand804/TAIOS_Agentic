"""Bounded, sanitized per-workflow memory for V2 reasoning context."""
from collections import deque
from dataclasses import dataclass
from agentic.semantic_fingerprint import fingerprint

@dataclass(frozen=True)
class WorkingMemoryEntry:
    event_reference: str
    decision: str | None
    governance: str
    execution: str
    drift: str

class WorkingMemory:
    def __init__(self, capacity=8):
        if type(capacity) is not int or capacity < 1: raise ValueError('capacity must be positive')
        self.capacity=capacity; self._entries=deque(maxlen=capacity)
    def append_result(self,result):
        entry=WorkingMemoryEntry(event_reference=result.event_reference,decision=(result.proposed_decision.selected_action.value if result.proposed_decision.selected_action else None),governance=result.governance_decision.status.value,execution=result.execution_result.execution_status.value,drift=result.drift_assessment.status.value)
        self._entries.append(entry); return entry
    def snapshot(self): return tuple(self._entries)
    @property
    def semantic_fingerprint(self): return fingerprint(self.snapshot())

def retrieve(memory, *, decision=None, drift=None, limit=3):
    """Deterministic exact-match retrieval over sanitized working-memory entries."""
    if type(limit) is not int or limit < 1: raise ValueError('limit must be positive')
    entries=memory.snapshot()
    ranked=sorted(enumerate(entries), key=lambda item: (-(int(decision is not None and item[1].decision==decision)+int(drift is not None and item[1].drift==drift)), item[0]))
    return tuple(entry for _,entry in ranked[:limit])
