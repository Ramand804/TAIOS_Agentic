from dataclasses import dataclass
from core.decision_contracts import Record
from core.risk_input import text_value
from agentic.contracts import ValidationStatus
@dataclass(frozen=True,kw_only=True)
class LLMProvenance(Record):
 llm_provider:str; llm_model:str; prompt_version:str; response_schema_version:str; raw_response_hash:str|None; validated_proposal:object|None; validation_status:ValidationStatus; fallback_reason:str|None=None
 def __post_init__(self):
  for n in ('llm_provider','llm_model','prompt_version','response_schema_version'):text_value(getattr(self,n),n)
  if self.raw_response_hash is not None:text_value(self.raw_response_hash,'raw_response_hash')
  object.__setattr__(self,'validation_status',ValidationStatus(self.validation_status))
  if self.fallback_reason is not None:text_value(self.fallback_reason,'fallback_reason')
