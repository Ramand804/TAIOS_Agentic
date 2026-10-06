from datetime import datetime,timezone
from industrial.assets.registry import INDUSTRIAL_ASSETS
from industrial.gateway.types import *
def _clean(data):
 return {k:v for k,v in dict(data).items() if k not in FORBIDDEN_EVALUATOR_FIELDS}
def _aware(t): return t is not None and t.tzinfo is not None and t.utcoffset() is not None
class IndustrialRuntimeEventValidator:
 def validate(self,event):
  if any(hasattr(event,x) for x in FORBIDDEN_EVALUATOR_FIELDS): raise ValueError('evaluator field in runtime event')
  a=INDUSTRIAL_ASSETS.get(event.target_id)
  if not a or a.asset_type!=event.target_type or event.operation not in a.allowed_operations or event.network_zone!=a.network_zone or event.asset_criticality!=a.criticality: raise ValueError('invalid industrial asset mapping')
  if not event.identity_id or not _aware(event.timestamp): raise ValueError('invalid runtime event')
  return True
class IndustrialGateway:
 def __init__(self,max_age_seconds=30,clock=None): self.max_age_seconds=max_age_seconds; self.clock=clock or (lambda:datetime.now(timezone.utc)); self._observations={}
 def ingest_observation(self,o):
  if o.target_id not in INDUSTRIAL_ASSETS or o.target_type!=INDUSTRIAL_ASSETS[o.target_id].asset_type: return GatewayResult(False,GatewayReason.INVALID_OBSERVATION,o)
  if not _aware(o.source_timestamp): return GatewayResult(False,GatewayReason.MISSING_TIMESTAMP,o,freshness=Freshness.TIMESTAMP_MISSING)
  now=self.clock(); delta=(now-o.source_timestamp).total_seconds()
  if delta<0:return GatewayResult(False,GatewayReason.FUTURE_TIMESTAMP,o,freshness=Freshness.FUTURE_TIMESTAMP)
  if delta>self.max_age_seconds:return GatewayResult(False,GatewayReason.STALE_INDUSTRIAL_CONTEXT,o,freshness=Freshness.STALE)
  if o.quality is Quality.BAD:return GatewayResult(False,GatewayReason.QUALITY_REJECTED,o,freshness=Freshness.FRESH)
  existing=self._observations.get(o.target_id)
  if existing and existing.state_version!=o.state_version:return GatewayResult(False,GatewayReason.STATE_VERSION_MISMATCH,o,freshness=Freshness.FRESH)
  clean=IndustrialObservation(**{**o.__dict__,'identity_metadata':_clean(o.identity_metadata),'protocol_metadata':_clean(o.protocol_metadata)})
  self._observations[clean.target_id]=clean; state=SynchronizedIndustrialState(dict(self._observations),clean.state_version)
  return GatewayResult(True,GatewayReason.QUALITY_UNCERTAIN if clean.quality is Quality.UNCERTAIN else GatewayReason.ACCEPTED,clean,state,freshness=Freshness.FRESH)
 def ingest_command(self,r):
  asset=INDUSTRIAL_ASSETS.get(r.target_id)
  source=INDUSTRIAL_ASSETS.get(r.source_id)
  if not asset or not source or source.asset_type!=r.source_type:return GatewayResult(False,GatewayReason.INVALID_EVENT_MAPPING)
  if r.target_type!=asset.asset_type or r.operation not in asset.allowed_operations or r.network_zone!=asset.network_zone:return GatewayResult(False,GatewayReason.INVALID_EVENT_MAPPING)
  if not r.identity_id or not _aware(r.timestamp):return GatewayResult(False,GatewayReason.INVALID_IDENTITY_CONTEXT)
  e=IndustrialRuntimeEvent(r.request_id,r.timestamp,r.source_id,r.source_type,r.target_id,r.target_type,r.identity_id,'control_command',r.operation,r.requested_value,r.network_zone,r.protocol,r.authentication_status,asset.criticality,{'state_version':r.state_version} if r.state_version is not None else {},provenance_reference={'request_id':r.request_id,'protocol':r.protocol})
  try: IndustrialRuntimeEventValidator().validate(e)
  except ValueError:return GatewayResult(False,GatewayReason.INVALID_EVENT_MAPPING)
  return GatewayResult(True,GatewayReason.ACCEPTED,runtime_event=e)
