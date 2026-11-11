"""Real-session PostgreSQL manager recovery, without model or approval fabrication."""
from uuid import uuid4

from test_m7_http_postgres import case as case, post
from test_enterprise_http_21_27 import department, employee

BASE = '/v1/organization/company'


def test_intake_assigns_independent_pm_without_engineering_flags(case, monkeypatch):
    client, headers, info = case
    founder = headers['founder']
    monkeypatch.delenv('AGO_LOCAL_FULL_BOARD_REVIEW', raising=False)
    monkeypatch.delenv('AGO_LOCAL_ENGINEERING_CANDIDATES', raising=False)
    dept = department(client, founder)
    ceo = post(client, '/v1/organization/employees', founder, {
        'department_id': dept, 'name': 'CEO', 'kind': 'ai'})['id']
    post(client, BASE+'/board/appoint', founder,
         {'seat': 'Strategy & Vision', 'employee_id': ceo})
    pm = post(client, '/v1/organization/employees', founder, {
        'department_id': dept, 'name': 'Delivery manager', 'kind': 'ai',
        'manager_id': ceo})['id']
    response = client.put(BASE+'/employees/'+pm+'/role', headers=founder, json={
        'role_title': 'AI Project Manager',
        'core_responsibilities': 'Own delivery, maintenance and verified revenue',
        'extra_responsibilities': 'Coordinate independent testing'})
    assert response.status_code == 200, response.text
    developer = post(client, '/v1/organization/employees', founder, {
        'department_id': dept, 'name': 'Software Developer', 'kind': 'ai',
        'manager_id': pm})['id']
    payload = {'brief': 'Build and maintain a local scheduling application',
               'operation_key': str(uuid4())}
    project = post(client, BASE+'/projects/start', founder, payload)
    assert project['accountable_manager_id'] == pm
    assert project['automatic_execution'] is False
    assert project['approval_required'] is True
    assert post(client, BASE+'/projects/start', founder, payload)['id'] == project['id']
    notices = info['db'].execute(
        "SELECT body,employee_id FROM ago_company_chat WHERE tenant_id=%s "
        "AND author_name='AGO project assignment'", (info['tenant'],)).fetchall()
    assert len(notices) == 1
    assert str(notices[0]['employee_id']) == developer
    assert project['id'] in notices[0]['body'] and 'implementation' in notices[0]['body']
    assert 'acknowledgement pending' in notices[0]['body']
    assert client.get(BASE+'/chat?channel=employee:'+developer,
                      headers=headers['reviewer']).status_code == 403
    # Board oversight must stay independent from delivery ownership.
    post(client, BASE+'/board/appoint', founder,
         {'seat': 'Quality & Release', 'employee_id': pm})
    second = post(client, BASE+'/projects/start', founder,
                  {**payload, 'operation_key': str(uuid4())})
    assert second['accountable_manager_id'] != pm
    assert info['db'].execute('SELECT 1 FROM ago_agent_runs WHERE tenant_id=%s',
                              (info['tenant'],)).fetchone() is None


def test_founder_reassigns_existing_project_without_changing_work(case):
    client, headers, info = case
    founder = headers['founder']
    db, tenant = info['db'], info['tenant']
    dept = department(client, founder)
    worker = employee(client, founder, dept)
    project = post(client, BASE+'/projects/start', founder, {
        'brief': 'Build a local scheduling application with reviewed acceptance criteria',
        'operation_key': str(uuid4())})
    assert project['accountable_manager_id'] == info['founder_id']

    def ai(name, manager=None, kind='ai'):
        return post(client, '/v1/organization/employees', founder, {
            'department_id': dept, 'name': name, 'kind': kind,
            'manager_id': manager})['id']

    def pm_role(identity):
        response = client.put(BASE+'/employees/'+identity+'/role', headers=founder, json={
            'role_title': 'AI Project Manager',
            'core_responsibilities': 'Manage reviewed internal project delivery',
            'extra_responsibilities': 'Track independent acceptance evidence'})
        assert response.status_code == 200, response.text

    ceo = ai('Strategy leader')
    post(client, BASE+'/board/appoint', founder,
         {'seat': 'Strategy & Vision', 'employee_id': ceo})
    pm = ai('Delivery lead', ceo)
    pm_role(pm)
    endpoint = BASE+'/projects/'+project['id']+'/accountable-manager'
    assert client.post(endpoint, json={'employee_id': pm}).status_code == 401
    post(client, endpoint, headers['reviewer'], {'employee_id': pm}, expected=403)
    post(client, BASE+'/projects/'+str(uuid4())+'/accountable-manager', founder,
         {'employee_id': pm}, expected=404)
    post(client, endpoint, founder, {'employee_id': str(uuid4())}, expected=400)
    post(client, endpoint, founder, {'employee_id': info['founder_id']}, expected=400)
    post(client, endpoint, founder, {'employee_id': ceo}, expected=400)
    non_pm = ai('Engineer', ceo)
    post(client, endpoint, founder, {'employee_id': non_pm}, expected=400)
    wrong_chain = ai('Unassigned manager')
    pm_role(wrong_chain)
    post(client, endpoint, founder, {'employee_id': wrong_chain}, expected=400)
    board_pm = ai('Board manager', ceo)
    pm_role(board_pm)
    post(client, BASE+'/board/appoint', founder,
         {'seat': 'Technology Oversight', 'employee_id': board_pm})
    post(client, endpoint, founder, {'employee_id': board_pm}, expected=400)
    pm_role(worker)
    response = client.put(BASE+'/employees/'+worker+'/manager', headers=founder,
                          json={'manager_id': ceo})
    assert response.status_code == 200, response.text
    post(client, endpoint, founder, {'employee_id': worker}, expected=400)
    post(client, endpoint, founder,
         {'employee_id': pm, 'expected_manager_id': str(uuid4())}, expected=400)

    before = client.get(BASE+'/projects/'+project['id'], headers=founder).json()
    approvals_before = db.execute('SELECT count(*) AS n FROM ago_approval_requests WHERE tenant_id=%s',
                                  (tenant,)).fetchone()['n']
    result = post(client, endpoint, founder,
                  {'employee_id': pm, 'expected_manager_id': info['founder_id']})
    assert result['id'] == project['id']
    assert result['plan_id'] == project['plan_id']
    assert result['brief'] == before['brief']
    assert result['stages'] == before['stages']
    assert result['accountable_manager_id'] == pm
    assert result['accountable_manager_role'] == 'AI Project Manager'
    assert result['assignment_source'] == 'founder_reassignment'
    assert result['manager_change']['changed'] is True
    assert post(client, endpoint, founder, {'employee_id': pm})['manager_change']['changed'] is False
    changes = db.execute('SELECT * FROM ago_project_manager_changes WHERE tenant_id=%s AND intake_id=%s',
                         (tenant, project['id'])).fetchall()
    assert len(changes) == 1
    assert str(changes[0]['previous_manager_id']) == info['founder_id']
    assert str(changes[0]['manager_id']) == pm
    assert str(changes[0]['actor_id']) == info['founder_id']
    assert changes[0]['changed_at'] is not None
    assert db.execute('SELECT count(*) AS n FROM ago_approval_requests WHERE tenant_id=%s',
                      (tenant,)).fetchone()['n'] == approvals_before
    assert db.execute('SELECT 1 FROM ago_agent_runs WHERE tenant_id=%s', (tenant,)).fetchone() is None

    # A separately authenticated Founder cannot touch this company's project.
    from ago.bootstrap import bootstrap
    other, _ = bootstrap(db, organization='Other company', email='other-manager@example.test',
                         password='other-manager-password-123')
    other_auth = info['login']('other-manager@example.test', 'other-manager-password-123', other)
    post(client, endpoint, other_auth, {'employee_id': pm}, expected=404)
