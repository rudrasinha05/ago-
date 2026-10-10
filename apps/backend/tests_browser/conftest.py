"""Browser harness hooks for reliable failure screenshots and test outcomes."""
import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    result = outcome.get_result()
    if result.when == "call":
        item.rep_call = result
