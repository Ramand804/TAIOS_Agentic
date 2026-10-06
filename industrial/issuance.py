"""Retired direct-DTO issuance API.

Industrial issuance is only available through ``build_trusted_runtime``.  These
compatibility names are deliberately read-only and cannot register authority.
"""


class GovernanceStore:
    def get(self, _decision_id):
        return None

    def contains(self, _decision_id):
        return False


class ReviewStore:
    def get(self, _review_id):
        return None

    def contains(self, _review_id):
        return False


class CapabilityIssuer:
    def __init__(self, *_args, **_kwargs):
        pass

    def issue(self, *_args, **_kwargs):
        return None
