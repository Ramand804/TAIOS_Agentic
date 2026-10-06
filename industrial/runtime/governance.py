from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from enum import Enum
from industrial.runtime.decision import Disposition
class OperatingMode(str,Enum): SIMULATION='SIMULATION';SHADOW='SHADOW';SUPERVISED='SUPERVISED';CONTROLLED_EXECUTION='CONTROLLED_EXECUTION'
class GovernanceStatus(str,Enum): APPROVED='APPROVED';REJECTED='REJECTED';REVIEW_REQUIRED='REVIEW_REQUIRED'
@dataclass(frozen=True)
class IndustrialGovernanceDecision: decision_id:str;transaction_id:str;runtime_event_id:str;state_version:int;target_id:str;operation:str;requested_value:object;operating_mode:OperatingMode;status:GovernanceStatus;created_at:datetime;expires_at:datetime;requires_human_review:bool;reason:str
class IndustrialGovernance:
 def __init__(self,mode=OperatingMode.SIMULATION,clock=None,ttl=60):self.mode=OperatingMode(mode);self.clock=clock or(lambda:datetime.now(timezone.utc));self.ttl=ttl
 def review(self,transaction):
  d=transaction.shadow_decision
  if d is None:
   return IndustrialGovernanceDecision('IGD-'+transaction.transaction_id,transaction.transaction_id,transaction.runtime_event_id,transaction.state_version,'','',None,self.mode,GovernanceStatus.REJECTED,self.clock(),self.clock()+timedelta(seconds=self.ttl),False,'Missing shadow decision.')
  if d.disposition is not Disposition.REQUEST_APPROVAL:
   return IndustrialGovernanceDecision('IGD-'+transaction.transaction_id,transaction.transaction_id,transaction.runtime_event_id,transaction.state_version,d.context.event.target_id,d.context.event.operation,d.context.event.requested_value,self.mode,GovernanceStatus.REJECTED,self.clock(),self.clock()+timedelta(seconds=self.ttl),False,'Conservative disposition rejected.')
  if self.mode in (OperatingMode.SIMULATION,OperatingMode.SHADOW): status,review=GovernanceStatus.REJECTED,False
  elif self.mode is OperatingMode.SUPERVISED: status,review=GovernanceStatus.REVIEW_REQUIRED,True
  else: status,review=GovernanceStatus.APPROVED,False
  return IndustrialGovernanceDecision('IGD-'+transaction.transaction_id,transaction.transaction_id,transaction.runtime_event_id,transaction.state_version,transaction.shadow_decision.context.event.target_id,transaction.shadow_decision.context.event.operation,transaction.shadow_decision.context.event.requested_value,self.mode,status,self.clock(),self.clock()+timedelta(seconds=self.ttl),review,'Bound industrial governance.')
