from typing import Iterable
from environment.event import IndustrialEvent
from environment.validators import validate_event_asset_integrity

class EventManager:
    def validate(self, events: Iterable[IndustrialEvent]):
        validated = list(events)
        for event in validated:
            validate_event_asset_integrity(event)
        return validated
