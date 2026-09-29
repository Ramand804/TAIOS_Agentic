import pytest
from agentic.adapter import resolve_advisory
from agentic.contracts import AgenticInput, ValidationStatus
from agentic.provider import ProviderFailure
from agentic.openai_provider import OpenAIProvider


def context():
 return AgenticInput(observation={'source_id':'PLC-01'},semantics={},authorization_status='AUTHORIZED',trust_summary={},threat_summary={},risk_summary={},drift_summary={},adaptation_summary={},assured_actions=('ALLOW',),planner_candidates=('ALLOW',),evidence_references=('evidence',))

@pytest.mark.parametrize('category,status',[
 ('AUTHENTICATION_FAILED',ValidationStatus.PROVIDER_ERROR),('RATE_LIMIT_OR_QUOTA',ValidationStatus.PROVIDER_ERROR),
 ('TIMEOUT',ValidationStatus.TIMEOUT),('CONNECTION_FAILED',ValidationStatus.PROVIDER_ERROR),
 ('MALFORMED_PROVIDER_RESPONSE',ValidationStatus.PROVIDER_ERROR)])
def test_typed_provider_failures_preserve_exact_baseline(category,status):
 class Failing:
  def reason(self,_): raise ProviderFailure(category)
 baseline=object(); actual,proposal,reason=resolve_advisory(context(),baseline,Failing())
 assert actual is status and proposal is baseline and reason==category

def test_malformed_openai_response_becomes_typed_failure():
 class Message: content='not-json'
 class Choice: message=Message()
 class Response: choices=[Choice()]; usage=None
 class Completions:
  def create(self,**kwargs): return Response()
 class Chat: completions=Completions()
 class Client: chat=Chat()
 with pytest.raises(ProviderFailure,match='MALFORMED_PROVIDER_RESPONSE'):
  OpenAIProvider(client=Client()).reason(type('Request',(),{'system_policy':'policy','runtime_instruction':'bounded','evidence':context()})())

def test_openai_exception_categories_are_normalized_without_details():
 import httpx
 from openai import AuthenticationError, RateLimitError, APITimeoutError, APIConnectionError
 request=httpx.Request('POST','https://api.openai.com/v1/chat/completions')
 cases=[(AuthenticationError('bad',response=httpx.Response(401,request=request),body={}), 'AUTHENTICATION_FAILED'),
        (RateLimitError('rate',response=httpx.Response(429,request=request),body={}), 'RATE_LIMIT_OR_QUOTA'),
        (APITimeoutError(request=request), 'TIMEOUT'),
        (APIConnectionError(request=request), 'CONNECTION_FAILED')]
 for exc,category in cases:
  class Completions:
   def create(self,**kwargs): raise exc
  class Chat: completions=Completions()
  class Client: chat=Chat()
  with pytest.raises(ProviderFailure,match=category):
   OpenAIProvider(client=Client()).reason(type('Request',(),{'system_policy':'policy','runtime_instruction':'bounded','evidence':context()})())
