from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

VALID_ACTIONS = {"ALLOW","MONITOR","LIMIT","REQUEST_APPROVAL","BLOCK","ISOLATE"}

@dataclass
class DecisionRecord:
    event_id: str
    selected_action: str
    context: Dict[str, Any] = field(default_factory=dict)
    identity_trust: Optional[float] = None
    device_trust: Optional[float] = None
    behavioral_trust: Optional[float] = None
    historical_trust: Optional[float] = None
    contextual_trust: Optional[float] = None
    composite_trust: Optional[float] = None
    attack_probability: Optional[float] = None
    risk_score: Optional[float] = None
    candidate_actions: List[str] = field(default_factory=list)
    policy_checks: Dict[str, Any] = field(default_factory=dict)
    governance_status: str = "NOT_EVALUATED"
    explanation: str = ""
    execution_status: str = "NOT_EXECUTED"
    outcome: Optional[str] = None
    latency_ms: Optional[float] = None
    trust_before: Optional[float] = None
    trust_after: Optional[float] = None
    model_version: str = "day1b"
    policy_version: str = "1.0"
    decision_id: str = field(default_factory=lambda: f"DEC-{uuid.uuid4().hex[:12].upper()}")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        if self.selected_action not in VALID_ACTIONS:
            raise ValueError(f"invalid selected_action: {self.selected_action}")

    def to_dict(self):
        return asdict(self)
