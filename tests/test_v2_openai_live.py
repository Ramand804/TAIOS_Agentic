"""Optional smoke test. It never runs without an already configured credential."""
import os
import pytest
from agentic.contracts import AgenticInput
from agentic.openai_provider import OpenAIProvider
from agentic.provider import ProviderReasoner, ReasoningRequest

# A credential alone must never make the regression suite issue a paid request.
# Live validation is an intentional, separately invoked operation.
pytestmark=pytest.mark.skipif(
    not (os.environ.get('OPENAI_API_KEY') and os.environ.get('TAIOS_RUN_LIVE_SMOKE')=='1'),
    reason='NOT_RUN_LIVE_SMOKE_NOT_EXPLICITLY_ENABLED')

def test_openai_live_structured_smoke():
 evidence=AgenticInput(observation={'source_id':'PLC-01','target_id':'MOTOR-02','operation':'set_speed'},semantics={},authorization_status='AUTHORIZED',trust_summary={},threat_summary={},risk_summary={},drift_summary={},adaptation_summary={},assured_actions=('ALLOW',),planner_candidates=('ALLOW',),evidence_references=('test',))
 provider=OpenAIProvider(api_key=os.environ['OPENAI_API_KEY'])
 raw=provider.reason(ReasoningRequest('TAIOS advisory only','Recommend supplied candidate only.',evidence))
 assert raw['recommended_action']=='ALLOW'
