"""Retired direct-DTO execution compatibility shell; cannot mutate process state."""
from dataclasses import dataclass
from datetime import datetime
@dataclass(frozen=True)
class IndustrialExecutionAuthorization:
 authorization_id:str;governance_id:str;transaction_id:str;runtime_event_id:str;target_id:str;operation:str;requested_value:object;state_version:int;expires_at:datetime;review_id:str|None=None
@dataclass(frozen=True)
class ExecutionResult: executed:bool;reason:str;state_version:int
class ExecutionGateway:
 """Disabled. Use CapabilityExecutionGateway with a runtime-issued opaque capability."""
 def __init__(self,cell,clock):self.cell=cell;self.clock=clock
 def execute(self,*args,**kwargs):return ExecutionResult(False,'LEGACY_DIRECT_EXECUTION_DISABLED',self.cell.state.state_version)
