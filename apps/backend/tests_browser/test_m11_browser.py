"""Real Chromium journeys against the shipped Next.js AGO frontend and PostgreSQL.

Only disposable CI identities; the retired /console static frontend is not used.
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
        pytest.skip("Browser acceptance needs disposable migrated PostgreSQL")
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "ago.main:app",
         "--host", "127.0.0.1", "--port", "18771", "--no-proxy-headers"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env=dict(os.environ, AGO_ENVIRONMENT="development"),
    )
    try:
        for _ in range(80):
            if process.poll() is not None:
                raise RuntimeError("AGO browser backend exited during startup")
            try:
                with urlopen(BASE_URL + "/health/live", timeout=1) as response:
                    if response.status == 200:
                        break
            except (URLError, TimeoutError, ConnectionError):
                time.sleep(0.25)
        else:
            raise RuntimeError("AGO browser backend did not become healthy")
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
    seed = str(uuid4())[:8]
    founder_mail = f"pilot-founder-{seed}@example.test"
    reviewer_mail = f"pilot-reviewer-{seed}@example.test"
    with psycopg.connect(os.environ["AGO_TEST_POSTGRES_DSN"],
                         row_factory=dict_row, autocommit=True) as db:
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
    context = browser.new_context(viewport={"width": 1440, "height": 900},
                                  reduced_motion="reduce")
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    yield page
    if getattr(getattr(request.node, "rep_call", None), "failed", False):
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(ARTIFACTS / (request.node.name + "-failure.png")),
                        full_page=True, timeout=10000)
    context.close()
    assert not errors, "Uncaught browser exceptions: " + repr(errors)


def sign_in(page, app_url, tenant, role="founder"):
    email, password, _ = tenant[role]
    page.goto(app_url + "/workspace/organization/", wait_until="domcontentloaded")
    expect(page.locator("#login-form")).to_be_visible()
    page.get_by_label("Organization ID").fill(tenant["id"])
    page.get_by_label("Work email").fill(email)
    page.get_by_label("Password", exact=True).fill(password)
    page.get_by_role("button", name="Sign in", exact=True).click()
    expect(page.get_by_role("heading", name="Company map", exact=True)).to_be_visible(
        timeout=15000
    )
    expect(page.locator("#login-form")).to_have_count(0)


def navigate(page, label, path):
    page.get_by_role("navigation", name="Workspaces").get_by_role(
        "link", name=label, exact=True
    ).click()
    expect(page).to_have_url(BASE_URL + "/workspace/" + path)
    content = "#screen .company-command" if path == "organization/" else "#screen .workspace-view"
    expect(page.locator(content)).to_be_visible(timeout=15000)


def test_only_company_map_and_eight_real_workspaces(page, tenant, app_url):
    for old in ("/console", "/console/"):
        page.goto(app_url + old)
        expect(page).to_have_url(app_url + "/workspace/organization/")
        expect(page.locator("#login-form")).to_be_visible()
    response = page.request.get(app_url + "/console/assets/app.js")
    assert response.status == 404
    sign_in(page, app_url, tenant)
    assert page.get_by_text("People & departments", exact=True).count() == 0
    for title, route in (
        ("Overview", ""), ("Strategy", "strategy/"),
        ("Governance", "governance/"), ("Organization", "organization/"),
        ("Knowledge", "knowledge/"), ("Operations & Tools", "tools/"),
        ("Calendar", "calendar/"), ("Digital Twin", "twin/"),
    ):
        navigate(page, title, route)
    expect(page.locator("#screen")).to_contain_text("Simulation only.")
    navigate(page, "Organization", "organization/")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(ARTIFACTS / "canonical-company-map.png"),
                    full_page=True)


def test_founder_goal_creation_and_refresh(page, tenant, app_url):
    sign_in(page, app_url, tenant)
    navigate(page, "Strategy", "strategy/")
    page.get_by_role("button", name="New goal", exact=True).click()
    expect(page.get_by_role("dialog")).to_be_visible()
    goal = "Real browser governed goal " + tenant["id"][:8]
    page.get_by_label("Goal title", exact=True).fill(goal)
    page.get_by_label("Context", exact=True).fill("Evidence-backed founder plan")
    page.locator("#operation-submit").click()
    expect(page.get_by_role("dialog")).to_be_hidden(timeout=15000)
    expect(page.locator("#screen")).to_contain_text(goal)
    page.get_by_role("button", name="Refresh", exact=True).click()
    expect(page.locator("#screen")).to_contain_text(goal)


def test_reviewers_never_gain_founder_actions(page, tenant, app_url):
    sign_in(page, app_url, tenant, role="reviewer")
    navigate(page, "Strategy", "strategy/")
    expect(page.get_by_role("button", name="New goal")).to_have_count(0)
    navigate(page, "Governance", "governance/")
    expect(page.get_by_role("button", name="Propose motion")).to_have_count(0)
    navigate(page, "Operations & Tools", "tools/")
    expect(page.get_by_role("button", name="Enroll a tool")).to_have_count(0)


def test_logout_and_refresh_do_not_persist_credentials(page, tenant, app_url):
    sign_in(page, app_url, tenant)
    with page.expect_response("**/v1/console/logout") as response:
        page.get_by_role("button", name="Sign out", exact=True).click()
    assert response.value.status == 200
    expect(page.locator("#login-form")).to_be_visible()
    page.reload()
    expect(page.locator("#login-form")).to_be_visible()
    assert not page.context.cookies()
    state = page.context.storage_state()
    assert not state["cookies"] and not state["origins"]


def test_mobile_menu_navigates_without_full_reload(browser, tenant, app_url):
    context = browser.new_context(viewport={"width": 390, "height": 844},
                                  is_mobile=True, has_touch=True)
    page = context.new_page()
    try:
        sign_in(page, app_url, tenant)
        page.get_by_role("button", name="Menu", exact=True).click()
        navigate(page, "Strategy", "strategy/")
        expect(page.get_by_role("button", name="New goal", exact=True)).to_be_visible()
        expect(page.locator("#login-form")).to_have_count(0)
    finally:
        context.close()
