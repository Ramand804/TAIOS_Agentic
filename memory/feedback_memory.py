"""Separate deterministic storage for immutable feedback interpretations."""
from core.experiment import fingerprint
from core.feedback_assessment import FeedbackAssessment


FEEDBACK_MEMORY_VERSION = 'milestone7b-feedback-memory-v1'


class FeedbackMemory:
    def __init__(self):
        self.reset()

    def reset(self):
        self._records = []
        self._by_experience = {}

    def _checkpoint(self):
        return tuple(self._records)

    def _restore(self, checkpoint):
        self._records = list(checkpoint)
        self._by_experience = {record.experience_reference: record for record in self._records}

    def append(self, feedback):
        if type(feedback) is not FeedbackAssessment:
            raise ValueError('Expected FeedbackAssessment')
        existing = self._by_experience.get(feedback.experience_reference)
        if existing is not None:
            if existing != feedback:
                raise ValueError('Conflicting feedback for canonical experience')
            return existing
        self._records.append(feedback)
        self._by_experience[feedback.experience_reference] = feedback
        return feedback

    def get_by_experience(self, experience_reference):
        return self._by_experience.get(experience_reference)

    def get_by_event(self, event_reference):
        return tuple(record for record in self._records if record.event_reference == event_reference)

    def get_by_source(self, source_id):
        return tuple(record for record in self._records if record.source_id == source_id)

    def get_by_target(self, target_id):
        return tuple(record for record in self._records if record.target_id == target_id)

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
            'memory_version': FEEDBACK_MEMORY_VERSION,
            'ordered_feedback_references': [record.reference for record in self._records],
        })
