"""Validate event references against authoritative static asset metadata."""

from environment.assets import ASSET_REGISTRY
from environment.event import IndustrialEvent


class EventIntegrityError(ValueError):
    """An event contains unknown assets or inconsistent asset metadata."""


def validate_event_asset_integrity(event: IndustrialEvent) -> bool:
    errors = []
    for role, fields in (
        ("source", (("source_type", "asset_type"),
                    ("network_zone", "network_zone"), ("protocol", "protocol"))),
        ("target", (("target_type", "asset_type"),
                    ("asset_criticality", "criticality"))),
    ):
        asset_id = getattr(event, f"{role}_id")
        asset = ASSET_REGISTRY.get(asset_id)
        if asset is None:
            errors.append(f"{role}_id={asset_id!r} is not registered")
            continue
        for event_field, asset_field in fields:
            actual = getattr(event, event_field)
            expected = getattr(asset, asset_field)
            if actual != expected:
                errors.append(
                    f"{event_field}={actual!r}; expected {expected!r} for {asset_id}"
                )
    if errors:
        raise EventIntegrityError(f"Event {event.event_id}: " + "; ".join(errors))
    return True
