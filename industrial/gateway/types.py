from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping
class Quality(str,Enum): GOOD='GOOD'; UNCERTAIN='UNCERTAIN'; BAD='BAD'
class Freshness(str,Enum): FRESH='FRESH'; STALE='STALE'; FUTURE_TIMESTAMP='FUTURE_TIMESTAMP'; TIMESTAMP_MISSING='TIMESTAMP_MISSING'
class GatewayReason(str,Enum): ACCEPTED='ACCEPTED'; QUALITY_REJECTED='QUALITY_REJECTED'; QUALITY_UNCERTAIN='QUALITY_UNCERTAIN'; STALE_INDUSTRIAL_CONTEXT='STALE_INDUSTRIAL_CONTEXT'; FUTURE_TIMESTAMP='FUTURE_TIMESTAMP'; MISSING_TIMESTAMP='MISSING_TIMESTAMP'; STATE_VERSION_MISMATCH='STATE_VERSION_MISMATCH'; INVALID_OBSERVATION='INVALID_OBSERVATION'; INVALID_EVENT_MAPPING='INVALID_EVENT_MAPPING'; INVALID_IDENTITY_CONTEXT='INVALID_IDENTITY_CONTEXT'
FORBIDDEN_EVALUATOR_FIELDS=frozenset({'ground_truth','expected_safe_action','scenario_id','experiment_id','phase','phase_label','attack_label','compromise_label','causal_label','causal_tags','test_oracle','expected_outcome'})
@dataclass(frozen=True)
class IndustrialObservation:
 observation_id:str; protocol:str; source_id:str; source_type:str; target_id:str; target_type:str; value:Any; network_zone:str; authentication_status:bool; asset_criticality:float; source_timestamp:datetime|None; server_timestamp:datetime|None; ingestion_timestamp:datetime; quality:Quality; state_version:int; identity_metadata:Mapping[str,Any]=field(default_factory=dict); protocol_metadata:Mapping[str,Any]=field(default_factory=dict)
@dataclass(frozen=True)
class IndustrialCommandRequest:
 request_id:str; timestamp:datetime; source_id:str; source_type:str; target_id:str; target_type:str; identity_id:str; operation:str; requested_value:Any; protocol:str; network_zone:str; authentication_status:bool; state_version:int|None=None; metadata:Mapping[str,Any]=field(default_factory=dict)
@dataclass(frozen=True)
class IndustrialRuntimeEvent:
 event_id:str; timestamp:datetime; source_id:str; source_type:str; target_id:str; target_type:str; identity_id:str; event_type:str; operation:str; requested_value:Any; network_zone:str; protocol:str; authentication_status:bool; asset_criticality:float; contextual_features:Mapping[str,Any]=field(default_factory=dict); sequence_number:int|None=None; provenance_reference:Mapping[str,Any]=field(default_factory=dict)
@dataclass(frozen=True)
class SynchronizedIndustrialState: observations:Mapping[str,IndustrialObservation]; state_version:int
@dataclass(frozen=True)
class GatewayResult: accepted:bool; reason:GatewayReason; observation:IndustrialObservation|None=None; synchronized_state:SynchronizedIndustrialState|None=None; runtime_event:IndustrialRuntimeEvent|None=None; freshness:Freshness|None=None
