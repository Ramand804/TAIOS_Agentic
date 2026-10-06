from dataclasses import dataclass
from enum import Enum
from industrial.gateway.types import IndustrialRuntimeEvent,SynchronizedIndustrialState
from industrial.assets.registry import INDUSTRIAL_ASSETS
from industrial.process.constraints import ProcessLimits
class SemanticStatus(str,Enum): SUPPORTED_VALID='SUPPORTED_VALID';SUPPORTED_OUT_OF_LIMIT='SUPPORTED_OUT_OF_LIMIT';UNSUPPORTED_OPERATION='UNSUPPORTED_OPERATION';UNKNOWN_ASSET='UNKNOWN_ASSET';INVALID_MODE='INVALID_MODE';STATE_VERSION_MISMATCH='STATE_VERSION_MISMATCH'
class AuthorizationStatus(str,Enum): AUTHORIZED='AUTHORIZED';DENIED='DENIED';UNKNOWN_IDENTITY='UNKNOWN_IDENTITY';INVALID_ZONE='INVALID_ZONE';UNAUTHENTICATED='UNAUTHENTICATED'
@dataclass(frozen=True)
class IndustrialSemanticAssessment: status:SemanticStatus; reasons:tuple[str,...]
@dataclass(frozen=True)
class IndustrialAuthorizationAssessment: status:AuthorizationStatus; reasons:tuple[str,...]
@dataclass(frozen=True)
class IndustrialDecisionContext: event:IndustrialRuntimeEvent; state:SynchronizedIndustrialState; semantics:IndustrialSemanticAssessment; authorization:IndustrialAuthorizationAssessment
