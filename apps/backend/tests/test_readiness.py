from ago.readiness import ReadinessChecks


def test_readiness_requires_registered_healthy_checks():
    checks = ReadinessChecks()
    assert not checks.ready()
    checks.register("database", lambda: True)
    checks.register("queue", lambda: False)
    assert not checks.ready()
    assert [item.name for item in checks.run()] == ["database", "queue"]


def test_readiness_masks_internal_errors():
    checks = ReadinessChecks()

    def broken():
        raise RuntimeError("sensitive connection details")

    checks.register("database", broken)
    assert checks.run()[0].detail == "check_failed"
