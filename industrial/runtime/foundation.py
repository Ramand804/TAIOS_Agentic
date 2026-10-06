from industrial.runtime_types import *
from industrial.process.constraints import ProcessLimits
class IndustrialSemanticModel:
 def __init__(self,limits=None): self.limits=limits or ProcessLimits()
 def assess(self,event,state):
  asset=INDUSTRIAL_ASSETS.get(event.target_id)
  if not asset:return IndustrialSemanticAssessment(SemanticStatus.UNKNOWN_ASSET,('Unknown industrial asset.',))
  if event.operation not in asset.allowed_operations:return IndustrialSemanticAssessment(SemanticStatus.UNSUPPORTED_OPERATION,('Operation unsupported for asset.',))
  if state.state_version!=event.contextual_features.get('state_version',state.state_version):return IndustrialSemanticAssessment(SemanticStatus.STATE_VERSION_MISMATCH,('State version mismatch.',))
  limits={'SET_MIXER_SPEED_RPM':(self.limits.mixer_speed_rpm_min,self.limits.mixer_speed_rpm_max),'SET_PUMP_FLOW_RATE_LPM':(self.limits.pump_flow_rate_lpm_min,self.limits.pump_flow_rate_lpm_max),'SET_CONVEYOR_SPEED_MPS':(self.limits.conveyor_speed_mps_min,self.limits.conveyor_speed_mps_max),'SET_PRODUCTION_RATE_UNITS_PER_HOUR':(self.limits.production_rate_units_per_hour_min,self.limits.production_rate_units_per_hour_max)}
  if event.operation in limits:
   lo,hi=limits[event.operation]
   if not isinstance(event.requested_value,(int,float)) or isinstance(event.requested_value,bool) or not lo<=event.requested_value<=hi:return IndustrialSemanticAssessment(SemanticStatus.SUPPORTED_OUT_OF_LIMIT,('Requested value exceeds simulator constraints.',))
  return IndustrialSemanticAssessment(SemanticStatus.SUPPORTED_VALID,('Validated against authoritative simulator constraints.',))
class IndustrialAuthorization:
 identities={'operator-01':'HUMAN_OPERATOR','maintenance-01':'MAINTENANCE_APPLICATION','engineering-01':'ENGINEERING_WORKSTATION','industrial-gateway':'INDUSTRIAL_GATEWAY','controller-01':'CONTROLLER'}
 def assess(self,event):
  if not event.authentication_status:return IndustrialAuthorizationAssessment(AuthorizationStatus.UNAUTHENTICATED,('Authentication evidence failed.',))
  role=self.identities.get(event.identity_id)
  if not role:return IndustrialAuthorizationAssessment(AuthorizationStatus.UNKNOWN_IDENTITY,('Unknown testbed identity.',))
  if event.network_zone!='testbed':return IndustrialAuthorizationAssessment(AuthorizationStatus.INVALID_ZONE,('Invalid testbed zone.',))
  allowed={'HUMAN_OPERATOR':{'SET_MIXER_SPEED_RPM','SET_PUMP_FLOW_RATE_LPM','SET_CONVEYOR_SPEED_MPS','SET_PRODUCTION_RATE_UNITS_PER_HOUR'},'MAINTENANCE_APPLICATION':{'STOP_ASSET','RESET_EMERGENCY'},'ENGINEERING_WORKSTATION':{'START_ASSET','STOP_ASSET','CHANGE_OPERATING_MODE'},'INDUSTRIAL_GATEWAY':set(),'CONTROLLER':{'EMERGENCY_STOP'}}
  return IndustrialAuthorizationAssessment(AuthorizationStatus.AUTHORIZED if event.operation in allowed[role] else AuthorizationStatus.DENIED,('Explicit least-privilege testbed policy.',))
