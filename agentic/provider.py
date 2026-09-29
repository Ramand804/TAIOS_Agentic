"""Provider-neutral structured reasoning boundary; no external implementation here."""
from dataclasses import dataclass
from abc import ABC,abstractmethod
from agentic.contracts import AgenticInput
from agentic.prompts import SYSTEM_POLICY


class ModelUnavailableError(RuntimeError):
    """A provider-neutral signal that has no authority consequence."""


class ProviderFailure(RuntimeError):
    """Secret-free provider failure classification for deterministic fallback."""
    def __init__(self, category):
        self.category = category
        super().__init__(category)
@dataclass(frozen=True)
class ReasoningRequest:
 system_policy:str; runtime_instruction:str; evidence:AgenticInput; prompt_version:str='v1'; schema_version:str='v1'
class StructuredReasoningProvider(ABC):
 @abstractmethod
 def reason(self,request:ReasoningRequest)->dict: raise NotImplementedError
class UnavailableProvider(StructuredReasoningProvider):
 def reason(self,request): raise ModelUnavailableError('MODEL_UNAVAILABLE')


class ProviderReasoner:
 """Adapts a structured provider to the advisory-only reasoner protocol."""
 def __init__(self, provider, *, system_policy=SYSTEM_POLICY,
              runtime_instruction='Recommend one existing assured candidate only.'):
  self.provider=provider; self.system_policy=system_policy; self.runtime_instruction=runtime_instruction
 def reason(self, evidence):
  if type(evidence) is not AgenticInput: raise ValueError('Expected AgenticInput')
  return self.provider.reason(ReasoningRequest(
      system_policy=self.system_policy, runtime_instruction=self.runtime_instruction,
      evidence=evidence))
