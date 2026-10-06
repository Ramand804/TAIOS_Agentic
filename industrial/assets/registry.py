from dataclasses import dataclass
from industrial.process.enums import ProcessAsset, ProcessOperation

@dataclass(frozen=True)
class IndustrialAsset:
    asset_id:str; asset_type:str; criticality:float; network_zone:str; protocol:str; allowed_operations:frozenset[str]

INDUSTRIAL_ASSETS={
 ProcessAsset.PRODUCTION_CONTROLLER.value: IndustrialAsset('PRODUCTION_CONTROLLER','controller',.95,'testbed','OPC_UA',frozenset({ProcessOperation.SET_PRODUCTION_RATE_UNITS_PER_HOUR.value,ProcessOperation.CHANGE_OPERATING_MODE.value,ProcessOperation.REQUEST_SHUTDOWN.value,ProcessOperation.EMERGENCY_STOP.value,ProcessOperation.RESET_EMERGENCY.value,ProcessOperation.START_ASSET.value,ProcessOperation.STOP_ASSET.value})),
 ProcessAsset.MIXER.value: IndustrialAsset('MIXER','mixer',.85,'testbed','OPC_UA',frozenset({ProcessOperation.SET_MIXER_SPEED_RPM.value,ProcessOperation.START_ASSET.value,ProcessOperation.STOP_ASSET.value})),
 ProcessAsset.PUMP.value: IndustrialAsset('PUMP','pump',.9,'testbed','OPC_UA',frozenset({ProcessOperation.SET_PUMP_FLOW_RATE_LPM.value,ProcessOperation.START_ASSET.value,ProcessOperation.STOP_ASSET.value})),
 ProcessAsset.CONVEYOR.value: IndustrialAsset('CONVEYOR','conveyor',.8,'testbed','OPC_UA',frozenset({ProcessOperation.SET_CONVEYOR_SPEED_MPS.value,ProcessOperation.START_ASSET.value,ProcessOperation.STOP_ASSET.value})),}
def get_industrial_asset(asset_id): return INDUSTRIAL_ASSETS[asset_id]
