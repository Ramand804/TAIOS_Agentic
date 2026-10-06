"""Adapters from authoritative runtime values to immutable dashboard view models."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Mapping


@dataclass(frozen=True)
class DashboardSnapshot:
    operating_mode: str
    process: Mapping[str, object]
    event: Mapping[str, object]
    decision: Mapping[str, object]
    governance: Mapping[str, object]
    execution: Mapping[str, object]
    health: Mapping[str, object]
    audit: tuple[Mapping[str, object], ...]


def _state_values(state):
    return {
        "machine_state": {str(key.value): value.value for key, value in state.machine_state.items()},
        "operating_mode": state.operating_mode.value,
        "mixer_speed_rpm": state.mixer_speed_rpm,
        "mixer_temperature_celsius": state.mixer_temperature_celsius,
        "pump_state": state.pump_state.value,
        "pump_pressure_bar": state.pump_pressure_bar,
        "pump_flow_rate_lpm": state.pump_flow_rate_lpm,
        "conveyor_state": state.conveyor_state.value,
        "conveyor_speed_mps": state.conveyor_speed_mps,
        "production_rate_units_per_hour": state.production_rate_units_per_hour,
        "maintenance_mode": state.maintenance_mode,
        "emergency_state": state.emergency_state,
        "state_version": state.state_version,
        "source_timestamp": state.source_timestamp.isoformat(),
    }


def from_runtime(runtime, *, event=None, lifecycle_result=None, audit_entries=()):
    """Read runtime state only. No service, store, or capability mutation occurs here."""
    decision = getattr(lifecycle_result, "shadow_decision", None)
    governance = getattr(lifecycle_result, "governance_decision", None)
    return DashboardSnapshot(
        operating_mode=runtime.operating_mode().value,
        process=_state_values(runtime.cell.state),
        event={} if event is None else {key: value for key, value in event.__dict__.items() if key not in {"ground_truth", "expected_safe_action", "scenario_id"}},
        decision={} if decision is None else {"disposition": decision.disposition.value, "authorization": decision.execution_authorization.value},
        governance={} if governance is None else {"status": governance.status.value, "requires_human_review": governance.requires_human_review, "expires_at": governance.expires_at.isoformat(), "transaction_id": governance.transaction_id},
        execution={"status": "Not issued", "interlock": "Not evaluated"},
        health={"industrial_runtime": "HEALTHY", "process_simulator": "HEALTHY", "opc_ua_adapter": "UNKNOWN", "mqtt_adapter": "UNKNOWN", "persistence": "UNKNOWN", "audit": "UNKNOWN", "agentic_provider": "NOT_CONFIGURED", "governance_service": "HEALTHY", "execution_gateway": "HEALTHY"},
        audit=tuple(audit_entries),
    )
