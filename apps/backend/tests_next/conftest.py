"""Share disposable real-PostgreSQL/server/browser fixtures across interfaces."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tests_browser'))
from test_m11_browser import app_url, tenant, browser, page  # noqa: E402,F401


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    result = outcome.get_result()
    if result.when == 'call':
        item.rep_call = result
