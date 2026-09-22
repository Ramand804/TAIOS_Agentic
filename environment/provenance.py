"""Experimental origin only; no agent inference or decision explanation."""
from dataclasses import asdict, dataclass
from environment.scenarios import get_scenario_manifest
from core.experiment import GENERATOR_VERSION


class ProvenanceIntegrityError(ValueError):
    pass


@dataclass(frozen=True)
class EventProvenance:
    experiment_id: str
    scenario_id: str
    scenario_version: str
    generator_version: str
    sequence_number: int
    phase: str
    transition_type: str
    causal_tags: tuple[str, ...]
    total_events: int

    def __post_init__(self):
        for name in ('experiment_id', 'scenario_id', 'scenario_version', 'generator_version', 'phase', 'transition_type'):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ProvenanceIntegrityError(f"{name} must be nonempty")
        if type(self.total_events) is not int or type(self.sequence_number) is not int or not 1 <= self.sequence_number <= self.total_events:
            raise ProvenanceIntegrityError("Invalid sequence_number / total_events")
        if isinstance(self.causal_tags, str) or not self.causal_tags or any(not isinstance(t, str) or not t.strip() for t in self.causal_tags):
            raise ProvenanceIntegrityError("causal_tags must contain nonempty strings")
        object.__setattr__(self, 'causal_tags', tuple(self.causal_tags))

    def to_dict(self):
        row = asdict(self)
        row['causal_tags'] = list(self.causal_tags)
        return row


def validate_event_provenance(event, manifest=None, experiment=None):
    provenance = event.provenance
    if not isinstance(provenance, EventProvenance):
        raise ProvenanceIntegrityError(f"Event {event.event_id}: complete provenance required")
    try:
        canonical = get_scenario_manifest(event.scenario_id, provenance.total_events)
        if manifest is None:
            manifest = canonical
        errors = []
        for field in ('experiment_id', 'scenario_id', 'sequence_number'):
            if getattr(provenance, field) != getattr(event, field):
                errors.append(field)
        if manifest.to_dict() != canonical.to_dict():
            errors.append('manifest')
        if provenance.scenario_version != manifest.scenario_version:
            errors.append('scenario_version')
        if provenance.phase != manifest.phase_at(event.sequence_number):
            errors.append('phase')
        if provenance.transition_type != manifest.transition_type:
            errors.append('transition_type')
        if provenance.causal_tags != manifest.causal_tags_at(event.sequence_number):
            errors.append('causal_tags')
        if provenance.generator_version != GENERATOR_VERSION:
            errors.append('generator_version')
        if experiment is not None:
            if event.scenario_id != experiment.scenario_id:
                errors.append('scenario_id')
            expected_metadata = experiment.event_metadata(event.sequence_number)
            for field in ('event_id', 'timestamp'):
                if getattr(event, field) != expected_metadata[field]:
                    errors.append(field)
            if provenance.experiment_id != experiment.experiment_id:
                errors.append('experiment_id')
            if provenance.generator_version != experiment.generator_version:
                errors.append('generator_version')
            if provenance.total_events != experiment.total_events:
                errors.append('total_events')
        if errors:
            raise ProvenanceIntegrityError(', '.join(errors))
    except (ValueError, KeyError, TypeError) as exc:
        raise ProvenanceIntegrityError(f"Event {event.event_id}: {exc}") from exc
    return True
