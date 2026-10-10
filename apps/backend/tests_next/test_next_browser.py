"""Shipped Next.js frontend against real signed sessions and PostgreSQL."""
from playwright.sync_api import expect
from test_m11_browser import PASSWORD_FOUNDER


def sign_in_next(page, app_url, tenant, role='founder'):
    email, password, _ = tenant[role]
    page.goto(app_url+'/workspace/', wait_until='domcontentloaded')
    page.get_by_label('Organization ID').fill(tenant['id'])
    page.get_by_label('Work email').fill(email)
    page.get_by_label('Password', exact=True).fill(password)
    page.get_by_role('button', name='Sign in', exact=True).click()
    expect(page.locator('#screen h1')).to_have_text('Your organization at a glance')


def navigate_next(page, name, heading):
    menu = page.get_by_role('button', name='Menu', exact=True)
    if menu.is_visible():
        menu.click()
    page.get_by_role('navigation', name='Workspaces').get_by_role(
        'link', name=name, exact=True,
    ).click()
    expect(page.locator('#screen h1')).to_have_text(heading)


def test_next_real_eight_routes_goal_and_session_revoke(page, app_url, tenant):
    sign_in_next(page, app_url, tenant)
    for label, heading in [
        ('Strategy', 'Strategy & execution'), ('Governance', 'Governance & oversight'),
        ('Organization', 'People & departments'), ('Knowledge', 'Institutional knowledge'),
        ('Operations & Tools', 'Enterprise operations'),
        ('Calendar', 'Organizational calendar'), ('Digital Twin', 'Organization Digital Twin'),
    ]:
        navigate_next(page, label, heading)
    navigate_next(page, 'Strategy', 'Strategy & execution')
    page.get_by_role('button', name='New goal').click()
    page.get_by_label('Goal title').fill('Next live goal '+tenant['id'][:8])
    page.get_by_label('Context').fill('Real HTTP and PostgreSQL persistence')
    page.locator('#operation-submit').click()
    expect(page.get_by_role('dialog')).to_be_hidden()
    expect(page.locator('#screen')).to_contain_text('Next live goal')
    page.get_by_role('button', name='Refresh', exact=True).click()
    expect(page.locator('#screen')).to_contain_text('Next live goal')
    page.get_by_role('button', name='Sign out', exact=True).click()
    expect(page.locator('#login-form')).to_be_visible()
    page.reload()
    expect(page.locator('#login-form')).to_be_visible()


def test_next_real_reviewer_remains_restricted(page, app_url, tenant):
    sign_in_next(page, app_url, tenant, 'reviewer')
    navigate_next(page, 'Strategy', 'Strategy & execution')
    expect(page.get_by_role('button', name='New goal')).to_have_count(0)
    navigate_next(page, 'Operations & Tools', 'Enterprise operations')
    expect(page.get_by_role('button', name='Enroll a tool')).to_have_count(0)
    # Changing client presentation cannot grant server authority.
    denied = page.evaluate('''async () => {
      const r = await fetch('/v1/brain/goals', {method:'POST',
        headers:{'Content-Type':'application/json'},body:JSON.stringify({title:'no session'})});
      return r.status;
    }''')
    assert denied == 401


def test_next_real_mobile_dashboards_and_exact_password(page, app_url, tenant):
    page.set_viewport_size({'width':390, 'height':844})
    sign_in_next(page, app_url, tenant)
    for view in ['Executive', 'Department', 'Employee']:
        page.get_by_role('button', name=view+' dashboard', exact=True).click()
        expect(page.get_by_role('heading', name=view+' dashboard', exact=True)).to_be_visible()
    navigate_next(page, 'Governance', 'Governance & oversight')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
    assert page.evaluate('localStorage.length === 0 && sessionStorage.length === 0')
    page.get_by_role('button', name='Sign out', exact=True).click()
    expect(page.locator('#login-form')).to_be_visible()
    page.get_by_label('Organization ID').fill(tenant['id'])
    page.get_by_label('Work email').fill(tenant['founder'][0])
    page.get_by_label('Password', exact=True).fill(' '+PASSWORD_FOUNDER+' ')
    page.get_by_role('button', name='Sign in', exact=True).click()
    expect(page.locator('#login-form [role=alert]')).to_contain_text('not accepted')


def test_next_governed_plan_two_humans_execution_and_qa(
    page, browser, tenant, app_url,
):
    """Founder never approves their own strategic plan or governed execution."""
    reviewer_context = browser.new_context(
        viewport={"width": 1330, "height": 900}, reduced_motion="reduce",
    )
    reviewer = reviewer_context.new_page()

    def task_rows(surface):
        return surface.locator(".panel").filter(
            has=surface.locator("h3", has_text="Task register"),
        ).locator("tr").filter(has_text="internal:brief")

    def task_approval_rows(surface):
        return surface.locator(".panel").filter(
            has=surface.locator("h3", has_text="Approvals"),
        ).locator("tr").filter(has_text="internal:brief")

    try:
        sign_in_next(page, app_url, tenant)
        sign_in_next(reviewer, app_url, tenant, role="reviewer")

        navigate_next(page, "Organization", "People & departments")
        page.get_by_role("button", name="Add AI employee").click()
        page.locator("#dlg-name").fill("Pilot AI Analyst")
        page.locator("#operation-submit").click()
        expect(page.locator("#action-dialog")).to_be_hidden(timeout=15000)
        expect(page.locator("#screen")).to_contain_text("Pilot AI Analyst")

        navigate_next(page, "Strategy", "Strategy & execution")
        page.get_by_role("button", name="New goal").click()
        page.locator("#dlg-title").fill("Governed pilot strategy")
        page.locator("#operation-submit").click()
        expect(page.locator("#action-dialog")).to_be_hidden(timeout=15000)
        expect(page.locator("#screen")).to_contain_text("Governed pilot strategy")
        page.get_by_role("button", name="New plan").click()
        page.locator("#dlg-title").fill("Pilot single-step brief")
        page.locator("#operation-submit").click()
        expect(page.locator("#action-dialog")).to_be_hidden(timeout=15000)

        plan = page.locator("tr").filter(has_text="Pilot single-step brief")
        expect(plan).to_be_visible()
        plan.get_by_role("button", name="Add step").click()
        page.locator("#dlg-action").fill("internal:brief")
        page.locator("#dlg-assignee_id").select_option(
            label="Pilot AI Analyst — Executive (ai)",
        )
        page.locator("#operation-submit").click()
        expect(page.locator("#action-dialog")).to_be_hidden(timeout=15000)
        plan = page.locator("tr").filter(has_text="Pilot single-step brief")
        plan.get_by_role("button", name="Submit", exact=True).click()
        expect(page.locator("#action-dialog")).to_be_visible()
        page.locator("#operation-submit").click()
        expect(page.locator("#action-dialog")).to_be_hidden(timeout=15000)
        expect(page.locator("tr").filter(has_text="Pilot single-step brief")).to_contain_text(
            "pending approval",
        )

        navigate_next(reviewer, "Governance", "Governance & oversight")
        review_row = reviewer.locator("tr").filter(has_text="brain:activate:")
        expect(review_row).to_be_visible()
        review_row.get_by_role("button", name="Approve", exact=True).click()
        reviewer.locator("#dlg-reason").fill("Independent human strategy review")
        reviewer.locator("#operation-submit").click()
        expect(reviewer.locator("#action-dialog")).to_be_hidden(timeout=15000)

        page.get_by_role("button", name="Refresh", exact=True).click()
        plan = page.locator("tr").filter(has_text="Pilot single-step brief")
        plan.get_by_role("button", name="Activate").click()
        page.locator("#operation-submit").click()
        expect(page.locator("#action-dialog")).to_be_hidden(timeout=15000)
        plan = page.locator("tr").filter(has_text="Pilot single-step brief")
        plan.get_by_role("button", name="Create tasks").click()
        page.locator("#operation-submit").click()
        expect(page.locator("#action-dialog")).to_be_hidden(timeout=15000)

        navigate_next(page, "Governance", "Governance & oversight")
        task_row = task_rows(page)
        expect(task_row).to_be_visible()
        task_row.get_by_role("button", name="Request approval").click()
        page.locator("#operation-submit").click()
        expect(page.locator("#action-dialog")).to_be_hidden(timeout=15000)

        reviewer.get_by_role("button", name="Refresh", exact=True).click()
        task_review = task_approval_rows(reviewer)
        expect(task_review).to_be_visible()
        task_review.get_by_role("button", name="Approve", exact=True).click()
        reviewer.locator("#dlg-reason").fill("Independent task execution authorization")
        reviewer.locator("#operation-submit").click()
        expect(reviewer.locator("#action-dialog")).to_be_hidden(timeout=15000)

        page.get_by_role("button", name="Refresh", exact=True).click()
        task_row = task_rows(page)
        task_row.get_by_role("button", name="Run approved AI").click()
        page.locator("#operation-submit").click()
        expect(page.locator("#action-dialog")).to_be_hidden(timeout=15000)
        expect(task_rows(page)).to_contain_text(
            "completed",
        )

        reviewer.get_by_role("button", name="Refresh", exact=True).click()
        task_row = reviewer.locator(".panel").filter(
            has=reviewer.locator("h3", has_text="Pending QA"),
        ).locator("tr").filter(has_text="internal:brief")
        expect(task_row).to_be_visible()
        task_row.get_by_role("button", name="Review outcome").click()
        reviewer.locator("#dlg-evidence").fill(
            "Independent quality inspection of the completed pilot brief",
        )
        reviewer.locator("#operation-submit").click()
        expect(reviewer.locator("#action-dialog")).to_be_hidden(timeout=15000)
        expect(reviewer.locator("#screen")).to_contain_text("pass")

    finally:
        reviewer_context.close()
