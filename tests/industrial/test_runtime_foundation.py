from datetime import datetime,timezone
from industrial.gateway.types import IndustrialRuntimeEvent,SynchronizedIndustrialState
from industrial.runtime import *
N=datetime(2026,1,1,tzinfo=timezone.utc)
def e(**x):
 d=dict(event_id='x',timestamp=N,source_id='PRODUCTION_CONTROLLER',source_type='controller',target_id='MIXER',target_type='mixer',identity_id='operator-01',event_type='control_command',operation='SET_MIXER_SPEED_RPM',requested_value=100,network_zone='testbed',protocol='OPC_UA',authentication_status=True,asset_criticality=.85,contextual_features={'state_version':1});d.update(x);return IndustrialRuntimeEvent(**d)
def s():return SynchronizedIndustrialState({},1)
def test_semantics_delegates_to_testbed_limits():
 assert IndustrialSemanticModel().assess(e(),s()).status is SemanticStatus.SUPPORTED_VALID
 assert IndustrialSemanticModel().assess(e(requested_value=9999),s()).status is SemanticStatus.SUPPORTED_OUT_OF_LIMIT
def test_testbed_authorization_is_least_privilege():
 assert IndustrialAuthorization().assess(e()).status is AuthorizationStatus.AUTHORIZED
 assert IndustrialAuthorization().assess(e(identity_id='unknown')).status is AuthorizationStatus.UNKNOWN_IDENTITY
 assert IndustrialAuthorization().assess(e(operation='RESET_EMERGENCY')).status is AuthorizationStatus.DENIED
def test_shadow_disposition_is_idempotent_and_never_execution_authorized():
 from industrial.runtime import IndustrialContextBuilder,IndustrialDecisionEngine,ExecutionAuthorization
 engine=IndustrialDecisionEngine(); result=engine.decide(IndustrialContextBuilder().build(e(),s()))
 assert result.execution_authorization is ExecutionAuthorization.EXECUTION_PROHIBITED and result.shadow_only
 assert engine.decide(IndustrialContextBuilder().build(e(),s())).duplicate
def test_transaction_duplicate_cannot_create_second_record():
 from industrial.runtime import IndustrialContextBuilder,IndustrialTransactionStore,TransactionStatus
 c=IndustrialContextBuilder().build(e(),s()); store=IndustrialTransactionStore(lambda:N)
 assert store.create(c).status is TransactionStatus.CREATED
 assert store.create(c).status is TransactionStatus.DUPLICATE
