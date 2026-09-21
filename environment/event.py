from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

VALID_LABELS = {"BENIGN", "SUSPICIOUS", "MALICIOUS"}
VALID_ACTIONS = {"ALLOW", "MONITOR", "LIMIT", "REQUEST_APPROVAL", "BLOCK", "ISOLATE"}

@dataclass
class IndustrialEvent:
    source_id: str
    source_type: str
    target_id: str
    target_type: str
    identity_id: str
    event_type: str
    operation: str
    requested_value: Any
    network_zone: str
    protocol: str
    authentication_status: bool
    asset_criticality: float
    ground_truth: str
    scenario_id: str
    contextual_features: Dict[str, Any] = field(default_factory=dict)
    expected_safe_action: Optional[str] = None
    event_id: str = field(default_factory=lambda: f"EVT-{uuid.uuid4().hex[:12].upper()}")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    sequence_number: Optional[int] = None
    experiment_id: Optional[str] = None

    def __post_init__(self):
        if not 0.0 <= self.asset_criticality <= 1.0:
            raise ValueError("asset_criticality must be in [0, 1]")
        if self.ground_truth not in VALID_LABELS:
            raise ValueError(f"ground_truth must be one of {sorted(VALID_LABELS)}")
        if self.expected_safe_action is not None and self.expected_safe_action not in VALID_ACTIONS:
            raise ValueError(f"invalid expected_safe_action: {self.expected_safe_action}")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
