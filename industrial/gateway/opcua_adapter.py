from industrial.gateway.types import IndustrialObservation,Quality
from industrial.assets.registry import INDUSTRIAL_ASSETS
from industrial.opcua.types import OpcUaObservation,ObservationQuality
_MAP={'ProductionController':'PRODUCTION_CONTROLLER','Mixer':'MIXER','Pump':'PUMP','Conveyor':'CONVEYOR'}
def from_opcua(observation:OpcUaObservation,state_version:int,identity_id='INDUSTRIAL_GATEWAY'):
 target=_MAP[observation.asset]; asset=INDUSTRIAL_ASSETS[target]
 return IndustrialObservation(observation.node, 'OPC_UA', 'PRODUCTION_CONTROLLER','controller',target,asset.asset_type,observation.value,asset.network_zone,True,asset.criticality,observation.source_timestamp,observation.server_timestamp,observation.ingestion_timestamp,Quality(observation.quality.value),state_version,{'identity_id':identity_id},{'endpoint':observation.endpoint,'node':observation.node})
