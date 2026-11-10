"""PROJ-006: the project's AI manager continues a project on the server.

Real signed sessions and PostgreSQL. Builder runs and the QA model are injected
fakes (no Ollama); every plan step, task, recovery, review and audit row that
AGO records about them is real.

Covered: a QA PASS opens the next stage's task for that stage's approved
specialist; a QA FAIL, a Board stop and a retryable run failure get a recovery
task decided by the AI manager (bounded); the server puts an independent tester
on every stage; the database refuses every shortcut around those rules.
"""
from types import SimpleNamespace
from uuid import uuid4

import pytest

import ago.ai_qa_review as ai_qa_review
import ago.api_agents as api_agents
from ago.company_ollama_chain import run_four_role_chain
from ago.company_ollama_chain_queries import CompanyOllamaChainQueries
from ago.credit_domain import CreditBudgetMissing
from test_local_company_ollama_chain import ApprovedProjectDb, FakeModel
from test_enterprise_http_21_27 import department
from test_m7_http_postgres import case as case, post

BASE = '/v1/organization/company'
STAGES = ('discovery', 'architecture', 'implementation', 'quality', 'release')
PEOPLE = (
    ('CEO', 'Chief Executive Officer'),
    ('Research Analyst', 'Research Analyst'),
    ('System Architect', 'Solution Architect'),
    ('Software Developer', 'Software Developer'),
    ('QA Specialist', 'QA Specialist'),
    ('Second Tester', 'QA Engineer'),
    ('DevOps Release Specialist', 'Release Manager'),
)


class Company:
    """One Founder-approved, CEO-staffed project and the steps a session can take."""

    def __init__(self, case, monkeypatch):
        self.client, headers, self.info = case
        self.founder, self.reviewer = headers['founder'], headers['reviewer']
        self.db, self.tenant = self.info['db'], self.info['tenant']
        self.monkeypatch = monkeypatch
        self.seen = []            # project_context of every builder run
        self.qa_answer = 'FINDINGS:\n- acceptance met\nQA_VERDICT: PASS'
        self.qa_prompts = []
        dept = department(self.client, self.founder)
        self.people = {}
        for name, title in PEOPLE:
            self.people[name] = post(self.client, '/v1/organization/employees', self.founder, {
                'department_id': dept, 'name': name, 'kind': 'ai'})['id']
            update = self.client.put(BASE+'/employees/'+self.people[name]+'/role',
                                     headers=self.founder, json={
                'role_title': title, 'core_responsibilities': 'Deliver the assigned stage',
                'extra_responsibilities': 'Record evidence'})
            assert update.status_code == 200, update.text
        post(self.client, BASE+'/board/appoint', self.founder, {
            'seat': 'Strategy & Vision', 'employee_id': self.people['CEO']})
        self.project = post(self.client, BASE+'/projects/start', self.founder, {
            'brief': 'Build a local admissions tracker with reviewed acceptance criteria',
            'operation_key': str(uuid4())})
        self.id, plan_id = self.project['id'], self.project['plan_id']
        self.url = BASE+'/projects/'+self.id
        plan = post(self.client, '/v1/brain/plans/'+plan_id+'/submit', self.founder)
        post(self.client, '/v1/governance/approvals/'+plan['approval_id']+'/decision',
             self.founder, {'approve': True, 'reason': 'Founder approves the project scope'})
        post(self.client, '/v1/brain/plans/'+plan_id+'/activate', self.founder)
        post(self.client, '/v1/brain/plans/'+plan_id+'/materialize', self.founder)
        self.db.execute("INSERT INTO ago_credit_budgets(tenant_id,ceiling) VALUES (%s,50) "
                        "ON CONFLICT(tenant_id) DO UPDATE SET ceiling=50", (self.tenant,))
        company = self

        class Model:
            def generate(self, prompt):
                company.qa_prompts.append(prompt)
                return company.qa_answer

        monkeypatch.setattr(ai_qa_review, 'local_qa_provider', lambda: (Model(), 'qwen-test'))

    def stage(self, name):
        return self.db.execute("""
            SELECT s.position,s.plan_step_id,ps.task_id,ps.assignee_id,ps.depends_on,
                   ps.action,t.status,a.assignee_id AS approved
            FROM ago_founder_intake_stages s
            LEFT JOIN ago_plan_steps ps ON ps.tenant_id=s.tenant_id AND ps.id=s.plan_step_id
            LEFT JOIN ago_governed_tasks t ON t.tenant_id=ps.tenant_id AND t.id=ps.task_id
            LEFT JOIN ago_project_stage_delegation_activations a ON a.tenant_id=s.tenant_id
              AND a.intake_id=s.intake_id AND a.stage=s.stage
            WHERE s.tenant_id=%s AND s.intake_id=%s AND s.stage=%s""",
            (self.tenant, self.id, name)).fetchone()

    def approve(self, name):
        row = self.stage(name)
        task_id = str(row['task_id'])
        if row['status'] == 'proposed':
            post(self.client, '/v1/console/tasks/'+task_id+'/request-approval', self.founder)
            done = post(self.client, self.url+'/ceo/reconcile', self.founder)
            assert task_id in done['approved_task_ids'], done
        return task_id

    def run(self, name, *, fail=None, board_stop=False, expected=200):
        task_id = self.approve(name)
        assignee = str(self.stage(name)['assignee_id'])

        def handler(task):
            self.seen.append(dict(task.project_context))
            if fail is not None:
                raise fail
            result = {'kind': 'local_company_governed_handoff', 'handoffs': [
                {'role': 'employee', 'employee_id': assignee, 'draft': name+' deliverable'}]}
            if board_stop:
                result.update(board_blocked=True, blocked_by_board_seat='Risk & Compliance',
                              board_block_reason='deny', board_recommendations=[
                    {'seat': 'Risk & Compliance', 'recommendation': 'deny',
                     'denial_reason': 'No data retention rule'}])
            return result

        self.monkeypatch.setattr(api_agents, 'optional_model_handlers',
                                 lambda *a, **k: {'internal:brief': handler})
        response = self.client.post('/v1/agents/tasks/'+task_id+'/run', headers=self.founder)
        assert response.status_code == expected, response.text
        return task_id, (response.json() if expected == 200 else None)

    def qa(self, name, verdict='PASS', **extra):
        self.qa_answer = 'FINDINGS:\n- reviewed\nQA_VERDICT: '+verdict
        return post(self.client, self.url+'/stages/'+name+'/ai-qa', self.founder,
                    {'operation_key': str(uuid4()), **extra})

    def recoveries(self, name):
        return self.db.execute("""
            SELECT v.failed_task_id,v.recovery_task_id,v.actor_id,v.decided_by_employee_id,
                   v.reason
            FROM ago_plan_step_task_recoveries v
            WHERE v.tenant_id=%s AND v.plan_step_id=%s ORDER BY v.id""",
            (self.tenant, self.stage(name)['plan_step_id'])).fetchall()


@pytest.fixture
def company(case, monkeypatch):
    return Company(case, monkeypatch)


def test_qa_pass_opens_every_next_stage_until_the_project_is_done(company):
    c, db, tenant = company, company.db, company.tenant
    # Before any QA: stages 2-5 have no step and nothing is pending for the AI manager.
    assert all(c.stage(s)['plan_step_id'] is None for s in STAGES[1:])
    endpoint = c.url+'/continue'
    assert c.client.post(endpoint).status_code == 401
    post(c.client, endpoint, c.reviewer, expected=403)
    post(c.client, BASE+'/projects/'+str(uuid4())+'/continue', c.founder, expected=404)
    waiting = post(c.client, endpoint, c.founder)
    assert (waiting['action'], waiting['state']) == ('none', 'stage_in_progress')
    assert waiting['decided_by_employee_id'] == c.people['CEO']

    previous_task = None
    for index, name in enumerate(STAGES):
        row = c.stage(name)
        assert row['action'] == 'internal:brief' and row['status'] == 'proposed'
        task_id, ran = c.run(name)
        # The task belongs to the stage's approved specialist.
        assert str(row['assignee_id']) == str(c.stage(name)['approved'])
        assert ran['continuation'] is None
        assert c.seen[-1]['stage'] == name and c.seen[-1]['intake_id'] == c.id
        assert c.seen[-1]['deliverable']
        review = c.qa(name)
        assert review['verdict'] == 'pass' and review['qa_reviewer_auto_selected'] is True
        # The server-chosen tester has a QA role and did not build the work.
        assert review['qa_employee_id'] in (c.people['QA Specialist'], c.people['Second Tester'])
        assert review['qa_employee_id'] != str(row['assignee_id'])
        step = review['continuation']
        assert step['kind'] == 'ago_project_continuation_v1'
        assert step['task_approved'] is False and step['run_started'] is False
        if name == 'release':
            assert (step['action'], step['state']) == ('none', 'all_stages_passed')
            break
        nxt = STAGES[index+1]
        assert (step['action'], step['stage'], step['from_stage']) == ('opened_stage', nxt, name)
        assert step['decided_by_employee_id'] == c.people['CEO'] and not step['needs_founder']
        opened = c.stage(nxt)
        assert str(opened['task_id']) == step['task_id'] and opened['status'] == 'proposed'
        assert opened['position'] == index+2
        assert str(opened['depends_on']) == str(c.stage(name)['plan_step_id'])
        assert str(opened['assignee_id']) == str(opened['approved']) == step['assignee_id']
        # Opening a stage never approves or runs its task.
        assert db.execute("SELECT count(*) AS n FROM ago_agent_runs WHERE tenant_id=%s "
                          "AND task_id=%s", (tenant, step['task_id'])).fetchone()['n'] == 0
        assert db.execute("SELECT approval_id FROM ago_governed_tasks WHERE tenant_id=%s "
                          "AND id=%s", (tenant, step['task_id'])).fetchone()['approval_id'] is None
        # The governed model chain accepts this stage's own task: it gets past
        # the stage link and only then asks for the (here unappointed) Board.
        chain = CompanyOllamaChainQueries(db)
        bound = {'intake_id': c.id}
        with pytest.raises(PermissionError, match='Board seats'):
            chain.assignments(tenant_id=tenant, actor_id=c.info['founder_id'],
                              task=SimpleNamespace(id=step['task_id'], project_context=bound))
        with pytest.raises(PermissionError, match='linked discovery task'):
            chain.assignments(tenant_id=tenant, actor_id=c.info['founder_id'],
                              task=SimpleNamespace(id=str(uuid4()), project_context=bound))
        # Asking again changes nothing.
        again = post(c.client, endpoint, c.founder)
        assert (again['action'], again['state']) == ('none', 'stage_in_progress')
        previous_task = task_id

    # Quality work is done by one tester and reviewed by the other one.
    quality_worker = str(c.stage('quality')['assignee_id'])
    implementation_worker = str(c.stage('implementation')['assignee_id'])
    testers = {c.people['QA Specialist'], c.people['Second Tester']}
    assert quality_worker in testers and implementation_worker == c.people['Software Developer']
    quality_review = db.execute("""SELECT q.reviewer_id FROM ago_task_reviews q
        WHERE q.tenant_id=%s AND q.task_id=%s""",
        (tenant, c.stage('quality')['task_id'])).fetchone()
    assert {quality_worker, str(quality_review['reviewer_id'])} == testers

    audit = db.execute("""SELECT from_stage,to_stage,decided_by_employee_id,authorized_by,
        passed_task_id,task_id FROM ago_project_stage_progressions
        WHERE tenant_id=%s AND intake_id=%s ORDER BY id""", (tenant, c.id)).fetchall()
    assert [(a['from_stage'], a['to_stage']) for a in audit] == list(zip(STAGES, STAGES[1:]))
    assert all(str(a['decided_by_employee_id']) == c.people['CEO']
               and str(a['authorized_by']) == c.info['founder_id'] for a in audit)
    assert str(audit[-1]['passed_task_id']) == previous_task
    notices = db.execute("SELECT body FROM ago_company_chat WHERE tenant_id=%s "
                         "AND author_name='CEO (AI project manager)'", (tenant,)).fetchall()
    assert len(notices) == 4 and all('still needs approval' in n['body'] for n in notices)

    detail = c.client.get(c.url, headers=c.founder).json()
    assert detail['qa_passed_stages'] == 5 and detail['completion_percent'] == 100
    done = post(c.client, endpoint, c.founder)
    assert (done['action'], done['state'], done['needs_founder']) == (
        'none', 'all_stages_passed', False)


def test_failed_stage_is_recovered_by_the_ai_manager_within_a_limit(company):
    c, db, tenant = company, company.db, company.tenant
    c.run('discovery')
    assert c.qa('discovery')['continuation']['action'] == 'opened_stage'

    # 1. Independent QA FAIL -> rework task, decided by the AI manager.
    first, _ = c.run('architecture')
    failed_review = c.qa('architecture', 'FAIL')
    rework = failed_review['continuation']
    assert (rework['action'], rework['recovery_kind']) == ('recovered_stage', 'qa_rework')
    assert rework['failed_task_id'] == first and rework['ai_recovery_attempt'] == 1
    assert str(c.stage('architecture')['task_id']) == rework['task_id'] != first
    assert c.stage('architecture')['status'] == 'proposed'
    # A failed stage never opens the next one.
    assert c.stage('implementation')['plan_step_id'] is None

    # 2. Board stop -> revision task carrying the Board's feedback.
    #    The denial first stays on the stage (the Founder can read it and may
    #    still allow the project); the next explicit continue revises it.
    second, stopped = c.run('architecture', board_stop=True)
    shown = stopped['continuation']
    assert (shown['action'], shown['state'], shown['needs_founder']) == (
        'none', 'board_stopped', False)
    assert 'Risk & Compliance' in shown['reason']
    assert str(c.stage('architecture')['task_id']) == second
    revision = post(c.client, c.url+'/continue', c.founder)
    assert (revision['action'], revision['recovery_kind']) == ('recovered_stage', 'board_revision')
    assert revision['failed_task_id'] == second and revision['ai_recovery_attempt'] == 2
    assert 'Risk & Compliance: No data retention rule' in revision['reason']

    rows = c.recoveries('architecture')
    assert [str(r['failed_task_id']) for r in rows] == [first, second]
    assert all(str(r['decided_by_employee_id']) == c.people['CEO']
               and str(r['actor_id']) == c.info['founder_id'] for r in rows)
    # Old evidence is untouched.
    assert db.execute("SELECT verdict FROM ago_task_reviews WHERE tenant_id=%s AND task_id=%s",
                      (tenant, first)).fetchone()['verdict'] == 'fail'

    # 3. After two automatic attempts the AI manager stops and the Founder decides.
    third, _ = c.run('architecture', fail=TimeoutError('model timed out'), expected=502)
    assert str(c.stage('architecture')['task_id']) == third
    assert len(c.recoveries('architecture')) == 2
    limit = post(c.client, c.url+'/continue', c.founder)
    assert (limit['action'], limit['state'], limit['needs_founder']) == (
        'none', 'recovery_limit_reached', True)
    manual = post(c.client, c.url+'/stages/architecture/recovery', c.founder,
                  {'failed_task_id': third, 'reason': 'Founder retries after the limit'})
    assert manual['decided_by_employee_id'] is None
    assert c.recoveries('architecture')[-1]['decided_by_employee_id'] is None

    # The Founder's retry then passes, and the project moves on by itself.
    c.run('architecture')
    assert c.qa('architecture')['continuation']['stage'] == 'implementation'
    assert c.stage('implementation')['status'] == 'proposed'


def test_ai_manager_retries_a_timeout_but_never_a_credit_failure(company):
    c = company
    timed_out, _ = c.run('discovery', fail=TimeoutError('model timed out'), expected=502)
    rows = c.recoveries('discovery')
    assert len(rows) == 1 and str(rows[0]['failed_task_id']) == timed_out
    assert rows[0]['reason'] == 'Retry after run failure: model_timeout'
    assert str(rows[0]['decided_by_employee_id']) == c.people['CEO']
    assert c.stage('discovery')['status'] == 'proposed'

    no_credit, _ = c.run('discovery', fail=CreditBudgetMissing('No budget'), expected=502)
    assert str(c.stage('discovery')['task_id']) == no_credit
    assert len(c.recoveries('discovery')) == 1
    held = post(c.client, c.url+'/continue', c.founder)
    assert (held['action'], held['state'], held['needs_founder']) == (
        'none', 'failure_needs_founder', True)
    assert 'credit_budget_missing' in held['reason']


def test_without_an_ai_manager_or_staffing_the_founder_is_told_why(case, monkeypatch):
    client, headers, info = case
    founder, db, tenant = headers['founder'], info['db'], info['tenant']
    dept = department(client, founder)
    post(client, '/v1/organization/employees', founder,
         {'department_id': dept, 'name': 'Research Worker', 'kind': 'ai'})
    project = post(client, BASE+'/projects/start', founder, {
        'brief': 'Build a local admissions tracker with reviewed acceptance criteria',
        'operation_key': str(uuid4())})
    url = BASE+'/projects/'+project['id']
    draft = post(client, url+'/continue', founder)
    assert (draft['action'], draft['state']) == ('none', 'project_not_active')
    plan = post(client, '/v1/brain/plans/'+project['plan_id']+'/submit', founder)
    post(client, '/v1/governance/approvals/'+plan['approval_id']+'/decision', founder,
         {'approve': True, 'reason': 'Founder approves the project scope'})
    post(client, '/v1/brain/plans/'+project['plan_id']+'/activate', founder)
    # The Founder himself is the accountable manager here: no AI may decide for him.
    held = post(client, url+'/continue', founder)
    assert (held['action'], held['state'], held['needs_founder']) == (
        'none', 'no_ai_project_manager', True)
    assert db.execute("SELECT count(*) AS n FROM ago_project_stage_progressions "
                      "WHERE tenant_id=%s", (tenant,)).fetchone()['n'] == 0


def test_unstaffed_next_stage_waits_for_staffing_instead_of_guessing(company):
    c = company
    # Discovery is approved through the ordinary flow, but with only its own
    # stage activated: the CEO reconcile below is what activates all five.
    c.run('discovery')
    c.db.execute("ALTER TABLE ago_project_stage_delegation_activations DISABLE TRIGGER USER")
    c.db.execute("DELETE FROM ago_project_stage_delegation_activations WHERE tenant_id=%s "
                 "AND intake_id=%s AND stage='architecture'", (c.tenant, c.id))
    c.db.execute("ALTER TABLE ago_project_stage_delegation_activations ENABLE TRIGGER USER")
    held = c.qa('discovery')['continuation']
    assert (held['action'], held['state'], held['needs_founder']) == (
        'none', 'stage_not_staffed', True)
    assert c.stage('architecture')['plan_step_id'] is None


def test_stage_specialist_under_another_line_manager_still_answers_to_the_pm(
        company, monkeypatch):
    """Live finding 2026-11-11: the Software Architect reported to the Engineering
    Manager, so the architecture run was refused. Approved staffing on the
    project stage is the project reporting line; nothing else is."""
    c, db, tenant = company, company.db, company.tenant
    c.run('discovery')
    task_id = c.qa('discovery')['continuation']['task_id']
    dept = department(c.client, c.founder)
    seats = ('Technology Oversight', 'Finance & Budget', 'Risk & Compliance',
             'Quality & Release')
    for seat in seats:
        member = post(c.client, '/v1/organization/employees', c.founder,
                      {'department_id': dept, 'name': seat+' AI', 'kind': 'ai'})['id']
        post(c.client, BASE+'/board/appoint', c.founder, {'seat': seat, 'employee_id': member})
    monkeypatch.setenv('AGO_LOCAL_FULL_BOARD_REVIEW', 'true')
    monkeypatch.setenv('AGO_ENVIRONMENT', 'development')
    architect = str(c.stage('architecture')['assignee_id'])
    line = db.execute("SELECT manager_id FROM ago_employees WHERE tenant_id=%s AND id=%s",
                      (tenant, architect)).fetchone()['manager_id']
    assert str(line) != c.people['CEO']          # not under the project manager

    def check():
        CompanyOllamaChainQueries(db).assignments(
            tenant_id=tenant, actor_id=c.info['founder_id'],
            task=SimpleNamespace(id=task_id, project_context={'intake_id': c.id}))

    # With approved staffing the reporting rule passes; the check moves on to the
    # next rule (here the CEO is both Board seat and manager, which is refused).
    with pytest.raises(PermissionError, match='distinct employees'):
        check()
    # Without that approved staffing record the same worker is refused.
    db.execute("ALTER TABLE ago_project_stage_delegation_activations DISABLE TRIGGER USER")
    db.execute("DELETE FROM ago_project_stage_delegation_activations WHERE tenant_id=%s "
               "AND intake_id=%s AND stage='architecture'", (tenant, c.id))
    db.execute("ALTER TABLE ago_project_stage_delegation_activations ENABLE TRIGGER USER")
    with pytest.raises(PermissionError, match='employee-to-PM reporting hierarchy'):
        check()


def test_database_refuses_every_shortcut_around_stage_progression(company):
    c, db, tenant = company, company.db, company.tenant
    plan_id = c.project['plan_id']
    discovery = c.stage('discovery')
    architect = str(c.approve('discovery') and c.stage('architecture')['approved'])

    def refused(sql, params, match):
        with pytest.raises(Exception, match=match):
            with db.transaction():
                db.execute(sql, params)

    insert = ("INSERT INTO ago_plan_steps(id,tenant_id,plan_id,position,action,assignee_id,"
              "depends_on) VALUES (%s,%s,%s,%s,%s,%s,%s)")
    # Discovery has not passed QA yet: no architecture step may exist.
    refused(insert, (str(uuid4()), tenant, plan_id, 2, 'internal:brief', architect,
                     discovery['plan_step_id']), 'Approved plans cannot be edited')

    c.run('discovery')
    c.qa('discovery')
    opened = c.stage('architecture')
    developer = str(c.stage('implementation')['approved'])
    # Architecture exists but has not passed: implementation may not be opened,
    # and a passed stage cannot get a second step, another action or another worker.
    for position, action, worker, depends in (
        (3, 'internal:brief', developer, opened['plan_step_id']),
        (6, 'internal:brief', developer, opened['plan_step_id']),
        (3, 'project:plan', developer, opened['plan_step_id']),
        (3, 'internal:brief', developer, None),
    ):
        refused(insert, (str(uuid4()), tenant, plan_id, position, action, worker, depends),
                'Approved plans cannot be edited')

    stage = "UPDATE ago_founder_intake_stages SET {} WHERE tenant_id=%s AND intake_id=%s AND stage=%s"
    refused(stage.format("deliverable='Anything goes here now'"), (tenant, c.id, 'release'),
            'append-only')
    refused(stage.format("plan_step_id=NULL"), (tenant, c.id, 'architecture'), 'append-only')
    refused(stage.format("plan_step_id=%s"),
            (discovery['plan_step_id'], tenant, c.id, 'architecture'), 'append-only')
    # A stage without a step cannot be pointed at another stage's step.
    refused(stage.format("plan_step_id=%s"),
            (opened['plan_step_id'], tenant, c.id, 'release'), 'append-only')
    refused("DELETE FROM ago_founder_intake_stages WHERE tenant_id=%s AND intake_id=%s",
            (tenant, c.id), 'append-only')
    refused("UPDATE ago_project_stage_progressions SET to_stage='release' WHERE tenant_id=%s",
            (tenant,), 'append-only')
    refused("DELETE FROM ago_project_stage_progressions WHERE tenant_id=%s", (tenant,),
            'append-only')


def test_a_later_stage_run_asks_its_worker_for_that_stage_deliverable():
    db = ApprovedProjectDb()
    participants = CompanyOllamaChainQueries(db).assignments(
        tenant_id=db.tenant, actor_id=db.founder, task=db.task())

    def chain(stage, **options):
        task, model = db.task(), FakeModel()
        task.project_context = {**task.project_context, 'stage': stage,
                                'deliverable': 'Design the approved technical architecture'}
        return run_four_role_chain(task=task, participants=participants, provider=model,
                                   **options), model.prompts[-1]

    result, worker_prompt = chain('architecture')
    assert result['project_stage'] == 'architecture' and result['handoff_complete'] is True
    assert 'Produce the architecture stage deliverable of this project: Design the approved' \
        in worker_prompt
    assert 'internal discovery deliverable' not in worker_prompt
    # Discovery keeps its original goal, and a missing stage means discovery.
    legacy, legacy_prompt = chain('discovery')
    assert legacy['project_stage'] == 'discovery'
    assert 'internal discovery deliverable' in legacy_prompt
    plain = run_four_role_chain(task=db.task(), participants=participants, provider=FakeModel())
    assert plain['project_stage'] == 'discovery'
