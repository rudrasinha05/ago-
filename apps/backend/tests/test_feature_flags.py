from ago.feature_flags import FeatureFlags


def test_flags_default_off_and_tenant_override():
    flags = FeatureFlags()
    assert not flags.enabled("new-ui", "tenant-a")
    flags.set_default("new-ui", True)
    flags.set_tenant("new-ui", "tenant-b", False)
    assert flags.enabled("new-ui", "tenant-a")
    assert not flags.enabled("new-ui", "tenant-b")
