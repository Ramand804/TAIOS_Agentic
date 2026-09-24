"""Deterministic episode-scoped storage for immutable experience records."""
from core.experience_record import ExperienceRecord
from core.experiment import fingerprint


MEMORY_VERSION = 'milestone7a-episodic-memory-v1'


class EpisodicMemory:
    def __init__(self):
        self.reset()

    def reset(self):
        self._records = []
        self._references = set()

    def _checkpoint(self):
        return tuple(self._records)

    def _restore(self, checkpoint):
        self._records = list(checkpoint)
        self._references = {record.reference for record in self._records}

    def append(self, experience):
        if type(experience) is not ExperienceRecord:
            raise ValueError('Expected ExperienceRecord')
        if experience.reference in self._references:
            return next(record for record in self._records
                        if record.reference == experience.reference)
        self._records.append(experience)
        self._references.add(experience.reference)
        return experience

    def get_by_event(self, event_reference):
        return tuple(record for record in self._records
                     if record.event_reference == event_reference)

    def get_by_source(self, source_id):
        return tuple(record for record in self._records if record.source_id == source_id)

    def get_by_target(self, target_id):
        return tuple(record for record in self._records if record.target_id == target_id)

    def get_by_operation(self, operation):
        return tuple(record for record in self._records if record.operation == operation)

    def recent(self, limit=10):
        if type(limit) is not int or limit < 0:
            raise ValueError('limit must be a nonnegative integer')
        return tuple(self._records[-limit:]) if limit else ()

    @property
    def records(self):
        return tuple(self._records)

    @property
    def count(self):
        return len(self._records)

    @property
    def memory_fingerprint(self):
        return fingerprint({
            'memory_version': MEMORY_VERSION,
            'ordered_experience_references': [record.reference for record in self._records],
        })
