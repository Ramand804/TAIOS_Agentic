"""OpenAI structured-output adapter. No client is constructed without a supplied key."""
from dataclasses import dataclass
from hashlib import sha256
from time import perf_counter
import json
from agentic.provider import StructuredReasoningProvider, ModelUnavailableError, ProviderFailure
from agentic.prompts import PROMPT_VERSION, SCHEMA_VERSION, OUTPUT_SCHEMA, build_prompt

@dataclass(frozen=True)
class ProviderMetadata:
    provider: str; model: str; prompt_version: str; schema_version: str
    temperature: float; seed: int | None; request_hash: str; response_hash: str
    latency_seconds: float; token_usage: object | None

class OpenAIProvider(StructuredReasoningProvider):
    def __init__(self, *, model='gpt-4o-mini', api_key=None, temperature=0.0, seed=None, client=None):
        self.model=model; self.temperature=temperature; self.seed=seed; self._client=client
        if client is None and not api_key: raise ModelUnavailableError('MODEL_UNAVAILABLE')
        if client is None:
            from openai import OpenAI
            self._client=OpenAI(api_key=api_key)
        self.last_metadata=None
    def reason(self, request):
        messages=build_prompt(request)
        encoded=json.dumps(messages,sort_keys=True,separators=(',',':'))
        started=perf_counter()
        kwargs={'model':self.model,'messages':messages,'temperature':self.temperature,
                'response_format':{'type':'json_schema','json_schema':OUTPUT_SCHEMA}}
        if self.seed is not None: kwargs['seed']=self.seed
        try:
            response=self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            # Import lazily so deterministic/V1 execution never needs the SDK.
            from openai import AuthenticationError, RateLimitError, APITimeoutError, APIConnectionError, NotFoundError
            if isinstance(exc, AuthenticationError): raise ProviderFailure('AUTHENTICATION_FAILED') from exc
            if isinstance(exc, RateLimitError): raise ProviderFailure('RATE_LIMIT_OR_QUOTA') from exc
            if isinstance(exc, APITimeoutError): raise ProviderFailure('TIMEOUT') from exc
            if isinstance(exc, APIConnectionError): raise ProviderFailure('CONNECTION_FAILED') from exc
            if isinstance(exc, NotFoundError): raise ModelUnavailableError('MODEL_UNAVAILABLE') from exc
            raise ProviderFailure('PROVIDER_ERROR') from exc
        try:
            content=response.choices[0].message.content
            raw=json.loads(content)
        except (AttributeError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ProviderFailure('MALFORMED_PROVIDER_RESPONSE') from exc
        response_text=json.dumps(raw,sort_keys=True,separators=(',',':'))
        usage=getattr(response,'usage',None)
        self.last_metadata=ProviderMetadata('openai',self.model,PROMPT_VERSION,SCHEMA_VERSION,
            self.temperature,self.seed,sha256(encoded.encode()).hexdigest(),sha256(response_text.encode()).hexdigest(),
            perf_counter()-started, None if usage is None else {'prompt_tokens':getattr(usage,'prompt_tokens',None),'completion_tokens':getattr(usage,'completion_tokens',None),'total_tokens':getattr(usage,'total_tokens',None)})
        return raw
