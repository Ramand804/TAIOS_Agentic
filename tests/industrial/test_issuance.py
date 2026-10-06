from industrial.issuance import CapabilityIssuer, GovernanceStore, ReviewStore


def test_legacy_direct_dto_issuance_api_is_fail_closed():
    assert CapabilityIssuer(GovernanceStore(), ReviewStore()).issue("anything") is None
    assert not hasattr(GovernanceStore(), "register")
    assert not hasattr(ReviewStore(), "register")
