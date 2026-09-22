from typing import Iterable
from environment.event import IndustrialEvent
from environment.provenance import validate_event_provenance, ProvenanceIntegrityError
from environment.validators import validate_event_asset_integrity

class EventManager:
    def validate(self, events: Iterable[IndustrialEvent], manifest=None, experiment=None):
        validated = list(events)
        if experiment is not None:
            experiment.validate_identity()
            if len(validated) != experiment.total_events:
                raise ProvenanceIntegrityError("Event count does not match experiment")
            if [event.sequence_number for event in validated] != list(range(1, experiment.total_events + 1)):
                raise ProvenanceIntegrityError("Experiment sequences must be complete, ordered and unique")
        for event in validated:
            validate_event_asset_integrity(event)
            if experiment is not None or event.experiment_id is not None or event.provenance is not None:
                validate_event_provenance(event, manifest, experiment)
        return validated
