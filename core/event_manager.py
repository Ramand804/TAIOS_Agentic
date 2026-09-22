from typing import Iterable
from environment.event import IndustrialEvent
from environment.provenance import validate_event_provenance
from environment.validators import validate_event_asset_integrity

class EventManager:
    def validate(self, events: Iterable[IndustrialEvent], manifest=None, experiment=None):
        validated = list(events)
        for event in validated:
            validate_event_asset_integrity(event)
            if event.experiment_id is not None or event.provenance is not None:
                validate_event_provenance(event, manifest, experiment)
        return validated
