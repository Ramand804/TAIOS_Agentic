from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class VirtualIdentity:
    identity_id: str
    role: str
    authenticated: bool = True

DEFAULT_IDENTITIES: List[VirtualIdentity] = [
    VirtualIdentity("operator-01", "operator"),
    VirtualIdentity("operator-12", "operator"),
    VirtualIdentity("engineer-03", "engineer"),
    VirtualIdentity("service-account-03", "service"),
    VirtualIdentity("user-17", "operator"),
]
