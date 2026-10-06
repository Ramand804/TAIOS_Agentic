"""Safe local-only OPC UA configuration for the testbed."""
from dataclasses import dataclass
from enum import Enum
import ipaddress


class OpcUaSecurityMode(str, Enum):
    DEVELOPMENT_LOCAL = "DEVELOPMENT_LOCAL"
    SECURE_CERTIFICATE = "SECURE_CERTIFICATE"


@dataclass(frozen=True)
class OpcUaConfig:
    host: str = "127.0.0.1"
    port: int = 4840
    endpoint_path: str = "/taios/testbed/"
    namespace_uri: str = "urn:taios:industrial:testbed"
    connection_timeout_seconds: float = 2.0
    read_timeout_seconds: float = 2.0
    reconnect_attempts: int = 2
    reconnect_delay_seconds: float = 0.01
    synchronization_interval_seconds: float = 0.01
    security_mode: OpcUaSecurityMode = OpcUaSecurityMode.DEVELOPMENT_LOCAL
    allow_non_loopback: bool = False

    def __post_init__(self) -> None:
        try:
            is_loopback = ipaddress.ip_address(self.host).is_loopback
        except ValueError as exc:
            raise ValueError("host must be a literal IP address; host names are not allowed") from exc
        if not is_loopback and not self.allow_non_loopback:
            raise ValueError("non-loopback OPC UA binding requires allow_non_loopback=True")
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError("port must be in [1, 65535]")
        if not self.endpoint_path.startswith("/") or not self.endpoint_path.endswith("/"):
            raise ValueError("endpoint_path must start and end with '/'")
        if not self.namespace_uri.strip():
            raise ValueError("namespace_uri must be non-empty")
        for field_name in ("connection_timeout_seconds", "read_timeout_seconds", "reconnect_delay_seconds", "synchronization_interval_seconds"):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} must be non-negative")
        if type(self.reconnect_attempts) is not int or self.reconnect_attempts < 0:
            raise ValueError("reconnect_attempts must be a non-negative integer")
        object.__setattr__(self, "security_mode", OpcUaSecurityMode(self.security_mode))

    @property
    def endpoint(self) -> str:
        return f"opc.tcp://{self.host}:{self.port}{self.endpoint_path}"
