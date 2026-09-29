"""Isolated advisory boundary; does not alter the V1 pipeline."""
from enum import Enum
from agentic.contracts import ValidationStatus
from agentic.validator import validate
from agentic.provider import ModelUnavailableError, ProviderFailure

class ExecutionMode(str,Enum): DETERMINISTIC_V1='DETERMINISTIC_V1'; AGENTIC_MOCK='AGENTIC_MOCK'; AGENTIC_LLM='AGENTIC_LLM'
def resolve_advisory(context, deterministic_proposal, reasoner):
    """Return validated advice or the exact deterministic proposal as fallback."""
    try:
        raw=reasoner.reason(context)
        if raw is None:return ValidationStatus.MODEL_UNAVAILABLE,deterministic_proposal,'EMPTY_RESPONSE'
        status,proposal=validate(raw,context)
        return (status,proposal,None) if status==ValidationStatus.VALID else (status,deterministic_proposal,status.value)
    except TimeoutError:return ValidationStatus.TIMEOUT,deterministic_proposal,'TIMEOUT'
    except ModelUnavailableError:return ValidationStatus.MODEL_UNAVAILABLE,deterministic_proposal,'MODEL_UNAVAILABLE'
    except ProviderFailure as exc:
        status = ValidationStatus.TIMEOUT if exc.category == 'TIMEOUT' else ValidationStatus.PROVIDER_ERROR
        return status,deterministic_proposal,exc.category
    except RuntimeError:return ValidationStatus.PROVIDER_ERROR,deterministic_proposal,'PROVIDER_ERROR'
