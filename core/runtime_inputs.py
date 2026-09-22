"""Allowlisted observable input view for future consumers.

Full IndustrialEvent records are simulator/evaluation records, not agent inputs.
Unknown context keys are excluded by default. This module performs no inference.
"""
from copy import deepcopy
from environment.industrial_environment import ProductionState, OperatingMode

OBSERVABLE_FIELDS = (
    'source_id', 'source_type', 'target_id', 'target_type', 'identity_id',
    'event_type', 'operation', 'requested_value', 'network_zone', 'protocol',
    'authentication_status', 'asset_criticality',
)


def runtime_observation(event):
    result = {name: deepcopy(getattr(event, name)) for name in OBSERVABLE_FIELDS}
    context = {}
    for name, enum in (('production_state', ProductionState), ('operating_mode', OperatingMode)):
        if name in event.contextual_features:
            context[name] = enum(event.contextual_features[name]).value
    result['contextual_features'] = context
    return result
