"""Episode-scoped deterministic contextual behavioral-reference bank."""
from core.behavioral_reference import BehavioralReferenceSnapshot
from core.experiment import fingerprint


STORE_VERSION = 'milestone7d-behavioral-reference-store-v1'


class BehavioralReferenceStore:
    def __init__(self):
        self.reset()

    def reset(self):
        self._snapshots = {}

    @staticmethod
    def key(scope, context):
        return (scope, context.get('operating_mode'), context.get('production_state'))

    def get(self, scope, context):
        return self._snapshots.get(self.key(scope, context))

    def put(self, snapshot):
        if type(snapshot) is not BehavioralReferenceSnapshot:
            raise ValueError('Expected BehavioralReferenceSnapshot')
        context = dict(snapshot.operating_context)
        key = self.key(snapshot.scope, context)
        prior = self._snapshots.get(key)
        expected_version = 1 if prior is None else prior.version + 1
        if snapshot.version != expected_version:
            raise ValueError('Behavioral reference version must increase deterministically')
        self._snapshots[key] = snapshot
        return snapshot

    def _checkpoint(self):
        return dict(self._snapshots)

    def _restore(self, checkpoint):
        self._snapshots = dict(checkpoint)

    @property
    def snapshots(self):
        return tuple(self._snapshots[key] for key in sorted(self._snapshots))

    @property
    def fingerprint(self):
        return fingerprint({
            'store_version': STORE_VERSION,
            'ordered_snapshot_references': [item.reference for item in self.snapshots],
        })
