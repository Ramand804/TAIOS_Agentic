from dataclasses import dataclass, asdict
from typing import Dict, List

@dataclass(frozen=True)
class VirtualAsset:
    asset_id: str
    asset_type: str
    network_zone: str
    protocol: str
    criticality: float

    def __post_init__(self):
        if not self.asset_id or not self.asset_id.strip():
            raise ValueError("asset_id must not be empty")
        if not 0.0 <= self.criticality <= 1.0:
            raise ValueError("criticality must be in [0, 1]")

    def to_dict(self):
        return asdict(self)

DEFAULT_ASSETS: List[VirtualAsset] = [
    VirtualAsset("PLC-01", "PLC", "control", "modbus", 0.90),
    VirtualAsset("PLC-03", "PLC", "control", "modbus", 0.95),
    VirtualAsset("PLC-04", "PLC", "control", "modbus", 0.88),
    VirtualAsset("PLC-07", "PLC", "control", "modbus", 0.92),
    VirtualAsset("HMI-02", "HMI", "supervisory", "opcua", 0.82),
    VirtualAsset("MOTOR-02", "actuator", "control", "modbus", 0.91),
    VirtualAsset("PUMP-01", "actuator", "control", "modbus", 0.86),
    VirtualAsset("SERVICE-03", "service", "enterprise", "https", 0.60),
]

ASSET_REGISTRY: Dict[str, VirtualAsset] = {a.asset_id: a for a in DEFAULT_ASSETS}

def get_asset(asset_id: str) -> VirtualAsset:
    return ASSET_REGISTRY[asset_id]

def asset_index() -> Dict[str, VirtualAsset]:
    return dict(ASSET_REGISTRY)
