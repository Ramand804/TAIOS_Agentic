from dataclasses import dataclass
from datetime import datetime,timezone
from enum import Enum
from industrial.runtime.decision import IndustrialShadowDecision
class TransactionStatus(str,Enum): CREATED='CREATED';SHADOW_DECIDED='SHADOW_DECIDED';DUPLICATE='DUPLICATE';FAILED='FAILED'
@dataclass(frozen=True)
class IndustrialTransaction:
 transaction_id:str; runtime_event_id:str; state_version:int; created_at:datetime; status:TransactionStatus; shadow_decision:IndustrialShadowDecision|None=None
class IndustrialTransactionStore:
 def __init__(self,clock=None):self.clock=clock or (lambda:datetime.now(timezone.utc));self._by_event={}
 def create(self,context):
  prior=self._by_event.get(context.event.event_id)
  if prior:return IndustrialTransaction(prior.transaction_id,prior.runtime_event_id,prior.state_version,prior.created_at,TransactionStatus.DUPLICATE,prior.shadow_decision)
  item=IndustrialTransaction('ITX-'+context.event.event_id,context.event.event_id,context.state.state_version,self.clock(),TransactionStatus.CREATED);self._by_event[item.runtime_event_id]=item;return item
 def attach_shadow(self,transaction,decision):
  if transaction.status is TransactionStatus.DUPLICATE:return transaction
  item=IndustrialTransaction(transaction.transaction_id,transaction.runtime_event_id,transaction.state_version,transaction.created_at,TransactionStatus.SHADOW_DECIDED,decision);self._by_event[item.runtime_event_id]=item;return item
