from datetime import timedelta
from industrial.gateway import *
from industrial.gateway.opcua_adapter import from_opcua
from industrial.opcua.types import OpcUaObservation,ObservationQuality
from datetime import datetime,timezone
NOW=datetime(2026,1,1,tzinfo=timezone.utc)
def obs(**x):
 d=dict(observation_id='o',protocol='OPC_UA',source_id='PRODUCTION_CONTROLLER',source_type='controller',target_id='MIXER',target_type='mixer',value=1,network_zone='testbed',authentication_status=True,asset_criticality=.85,source_timestamp=NOW,server_timestamp=NOW,ingestion_timestamp=NOW,quality=Quality.GOOD,state_version=1);d.update(x);return IndustrialObservation(**d)
def req(**x):
 d=dict(request_id='r',timestamp=NOW,source_id='PRODUCTION_CONTROLLER',source_type='controller',target_id='MIXER',target_type='mixer',identity_id='operator',operation='SET_MIXER_SPEED_RPM',requested_value=10,protocol='OPC_UA',network_zone='testbed',authentication_status=True,state_version=1);d.update(x);return IndustrialCommandRequest(**d)
def test_quality_freshness_and_telemetry():
 g=IndustrialGateway(10,lambda:NOW);assert g.ingest_observation(obs()).accepted
 assert g.ingest_observation(obs(quality=Quality.UNCERTAIN)).reason is GatewayReason.QUALITY_UNCERTAIN
 assert not g.ingest_observation(obs(quality=Quality.BAD)).accepted
 assert g.ingest_observation(obs(source_timestamp=NOW-timedelta(seconds=11))).freshness is Freshness.STALE
 assert g.ingest_observation(obs(source_timestamp=NOW+timedelta(seconds=1))).freshness is Freshness.FUTURE_TIMESTAMP
 assert g.ingest_observation(obs(source_timestamp=None)).freshness is Freshness.TIMESTAMP_MISSING
def test_versions_runtime_event_and_leakage():
 g=IndustrialGateway(10,lambda:NOW);assert g.ingest_observation(obs()).accepted
 assert g.ingest_observation(obs(state_version=2)).reason is GatewayReason.STATE_VERSION_MISMATCH
 r=g.ingest_command(req(metadata={'ground_truth':'MALICIOUS','scenario_id':'x'}));assert r.accepted and r.runtime_event
 assert not any(hasattr(r.runtime_event,n) for n in FORBIDDEN_EVALUATOR_FIELDS);IndustrialRuntimeEventValidator().validate(r.runtime_event)
def test_invalid_asset_and_opcua_adapter():
 assert not IndustrialGateway(clock=lambda:NOW).ingest_command(req(target_id='NO')).accepted
 o=OpcUaObservation('e','n','Mixer','Mixer.SpeedRPM',2,NOW,NOW,ObservationQuality.GOOD,NOW)
 assert from_opcua(o,1).target_id=='MIXER'
def test_required_fields_asset_integrity_and_no_frozen_event():
 g=IndustrialGateway(10,lambda:NOW)
 assert g.ingest_observation(obs(target_type='wrong')).reason is GatewayReason.INVALID_OBSERVATION
 assert not g.ingest_command(req(target_type='wrong')).accepted
 assert not g.ingest_command(req(operation='UNSUPPORTED')).accepted
 assert not g.ingest_command(req(source_id='UNKNOWN')).accepted
 event=g.ingest_command(req()).runtime_event
 assert event.protocol=='OPC_UA' and event.network_zone=='testbed' and event.asset_criticality==.85
 assert 'IndustrialEvent' not in open('industrial/gateway/gateway.py').read()
def test_metadata_is_sanitized_and_does_not_create_event_from_telemetry():
 g=IndustrialGateway(10,lambda:NOW)
 result=g.ingest_observation(obs(protocol_metadata={'attack_label':'x','ok':1},identity_metadata={'phase_label':'x'}))
 assert result.runtime_event is None and result.accepted
 assert result.observation.protocol_metadata=={'ok':1} and result.observation.identity_metadata=={}
