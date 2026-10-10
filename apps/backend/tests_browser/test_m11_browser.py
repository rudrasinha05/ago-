"""M11: actual Chromium exercise of AGO against a live FastAPI/PostgreSQL instance.

Only disposable CI identities. The browser must execute the shipped static
JavaScript and use HTTP, unlike the pure-JS M9 template/unit tests.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4

import psycopg
import pytest
from playwright.sync_api import expect, sync_playwright
from psycopg.rows import dict_row

from ago.bootstrap import bootstrap
from ago.provision import add_reviewer


BASE_URL = "http://127.0.0.1:18771"
ARTIFACTS = Path(__file__).parent / "artifacts"
PASSWORD_FOUNDER = "ci-browser-only-founder-password-123"
PASSWORD_REVIEWER = "ci-browser-only-reviewer-password-123"


@pytest.fixture(scope="session")
def app_url():
    if not os.getenv("AGO_TEST_POSTGRES_DSN"):
        pytest.skip("Browser acceptance requires disposable migrated PostgreSQL")
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "ago.main:app",
         "--host", "127.0.0.1", "--port", "18771", "--no-proxy-headers"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=dict(os.environ, AGO_ENVIRONMENT="development"),
    )
    try:
        for _ in range(80):
            if process.poll() is not None:
                raise RuntimeError("AGO pilot backend exited during startup")
            try:
                with urlopen(BASE_URL + "/health/live", timeout=1) as response:
                    if response.status == 200:
                        break
            except (URLError, TimeoutError, ConnectionError):
                time.sleep(0.25)
        else:
            raise RuntimeError("AGO pilot backend did not become healthy")
        yield BASE_URL
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.fixture
def tenant(app_url):
    """Each test receives an isolated tenant with a real independent reviewer."""
    dsn = os.environ["AGO_TEST_POSTGRES_DSN"]
    seed = str(uuid4())[:8]
    founder_mail = f"pilot-founder-{seed}@example.test"
    reviewer_mail = f"pilot-reviewer-{seed}@example.test"
    with psycopg.connect(dsn, row_factory=dict_row, autocommit=True) as db:
        org, founder_id = bootstrap(
            db, organization="AGO Pilot " + seed,
            email=founder_mail, password=PASSWORD_FOUNDER,
        )
        reviewer_id = add_reviewer(
            db, tenant_id=org, email=reviewer_mail,
            password=PASSWORD_REVIEWER,
        )
    return {
        "id": org,
        "founder": (founder_mail, PASSWORD_FOUNDER, founder_id),
        "reviewer": (reviewer_mail, PASSWORD_REVIEWER, reviewer_id),
    }


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        yield browser
        browser.close()


@pytest.fixture
def page(browser, request):
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        reduced_motion="reduce",
    )
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    yield page
    if request.node.rep_call.failed:
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(
            path=str(ARTIFACTS / (request.node.name + "-failure.png")),
            full_page=True, timeout=10000,
        )
    context.close()
    assert not errors, "Uncaught real browser exceptions: " + repr(errors)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call":
        item.rep_call = report


def sign_in(page, app_url, tenant, role="founder"):
    email, password, _ = tenant[role]
    page.goto(app_url + "/console/", wait_until="domcontentloaded")
    expect(page.locator("#login-form")).to_be_visible()
    page.locator("#tenant").fill(tenant["id"])
    page.locator("#email").fill(email)
    page.locator("#password").fill(password)
    page.locator("#login-button").click()
    expect(page.locator("#workspace")).to_be_visible(timeout=15000)
    expect(page.locator("#screen h1")).to_have_text(
        "Your organization at a glance", timeout=15000,
    )


def navigate(page, name, heading):
    page.locator(f'#primary-nav [data-page="{name}"]').click()
    expect(page.locator("#screen h1")).to_have_text(heading, timeout=15000)
    expect(page.locator("#screen .loading-screen")).to_have_count(0)


def submit_dialog(page, button):
    expect(page.locator("#action-dialog")).to_be_visible()
    page.locator("#operation-submit").get_by_text(button).click()
    expect(page.locator("#action-dialog")).to_be_hidden(timeout=15000)


def test_founder_real_navigation_and_goal_round_trip(page, tenant, app_url):
    sign_in(page, app_url, tenant)
    views = (
        ("strategy", "Strategy & execution"),
        ("governance", "Governance & oversight"),
        ("organization", "People & departments"),
        ("knowledge", "Institutional knowledge"),
        ("tools", "Enterprise operations"),
        ("calendar", "Organizational calendar"),
        ("twin", "Organization Digital Twin"),
        ("overview", "Your organization at a glance"),
    )
    for key, heading in views:
        navigate(page, key, heading)

    navigate(page, "strategy", "Strategy & execution")
    page.get_by_role("button", name="New goal").click()
    expect(page.locator("#action-dialog")).to_be_visible()
    goal = "Pilot organizational goal " + tenant["id"][:8]
    page.locator("#dlg-title").fill(goal)
    page.locator("#dlg-description").fill("Evidence-backed pilot planning")
    page.locator("#operation-submit").click()
    expect(page.locator("#action-dialog")).to_be_hidden(timeout=15000)
    expect(page.locator("#screen")).to_contain_text(goal)
    page.locator("#refresh").click()
    expect(page.locator("#screen")).to_contain_text(goal)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(ARTIFACTS / "founder-strategy.png"), full_page=True)


def test_real_digital_twin_never_applies_thresholds(page, tenant, app_url):
    sign_in(page, app_url, tenant)
    navigate(page, "twin", "Organization Digital Twin")
    expect(page.get_by_text("Simulation only.")).to_be_visible()
    page.get_by_role("button", name="Capture current evidence").click()
    expect(page.locator("#action-dialog")).to_be_visible()
    page.locator("#operation-submit").click()
    expect(page.locator("#action-dialog")).to_be_hidden(timeout=15000)
    expect(page.locator("#snapshot-select option")).to_have_count(1)
    page.locator("#range-qa_target_pct").evaluate("""node => {
      node.value = '90';
      node.dispatchEvent(new Event('input', { bubbles: true }));
      node.dispatchEvent(new Event('change', { bubbles: true }));
    }""")
    page.get_by_role("button", name="Run comparison").click()
    expect(page.get_by_text("Scenario evaluated. No changes were applied to AGO.")).to_be_visible()
    expect(page.locator("#screen")).to_contain_text("HYPOTHETICAL SCENARIO")
    # No new live DNA versions are created by a simulation.
    with psycopg.connect(os.environ["AGO_TEST_POSTGRES_DSN"], row_factory=dict_row) as db:
        n = db.execute(
            "SELECT count(*) AS n FROM ago_dna_versions WHERE tenant_id=%s",
            (tenant["id"],),
        ).fetchone()["n"]
        assert n == 0
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(ARTIFACTS / "digital-twin.png"), full_page=True)


def test_reviewer_is_not_a_founder_and_cannot_self_escalate(page, tenant, app_url):
    sign_in(page, app_url, tenant, role="reviewer")
    navigate(page, "strategy", "Strategy & execution")
    expect(page.get_by_role("button", name="New goal")).to_have_count(0)
    navigate(page, "governance", "Governance & oversight")
    expect(page.get_by_role("button", name="Propose motion")).to_have_count(0)
    navigate(page, "tools", "Enterprise operations")
    expect(page.get_by_role("button", name="Enroll a tool")).to_have_count(0)
    page.screenshot(path=str(ARTIFACTS / "reviewer-restricted.png"), full_page=True)


def test_real_logout_revokes_browser_session_and_reload_requires_login(page, tenant, app_url):
    sign_in(page, app_url, tenant)
    with page.expect_response("**/v1/console/logout") as response:
        page.locator("#signout").click()
    assert response.value.status == 200
    expect(page.locator("#auth")).to_be_visible()
    expect(page.locator("#workspace")).to_be_hidden()
    page.reload()
    expect(page.locator("#login-form")).to_be_visible()
    assert not page.context.cookies()
    state = page.context.storage_state()
    assert not state["cookies"] and not state["origins"]


def test_mobile_menu_and_keyboard_access(browser, tenant, app_url):
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        is_mobile=True, has_touch=True, reduced_motion="reduce",
    )
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        sign_in(page, app_url, tenant)
        menu = page.locator("#menu-button")
        expect(menu).to_be_visible()
        menu.click()
        expect(page.locator("#sidebar")).to_have_class(
            "sidebar open",
        )
        navigate(page, "strategy", "Strategy & execution")
        expect(page.locator("#mobile-shade")).to_be_hidden()
        page.get_by_role("button", name="New goal").click()
        expect(page.locator("#action-dialog")).to_be_visible()
        expect(page.locator("#dlg-title")).to_be_focused()
        page.keyboard.press("Escape")
        expect(page.locator("#action-dialog")).to_be_hidden()
        page.screenshot(path=str(ARTIFACTS / "mobile-strategy.png"), full_page=True)
        assert not errors, "Browser exceptions on mobile: " + repr(errors)
    finally:
        context.close()
