"""Issue #8 M2: project tasks are approved by the AI hierarchy, not always the CEO.

Inside a Founder-approved project, governance picks the approver: the worker's
direct manager, else the project manager, else the AI CEO. Each must be an
active AI employee who is not the worker. The approver is recorded as
responsible, with every skipped level. Real signed sessions and PostgreSQL.
"""
from uuid import uuid4

import pytest

from test_enterprise_hr_21 import _change
from test_enterprise_http_21_27 import department
from test_m7_http_postgres import case as case, post

BASE = '/v1/organization/company'


def _company(client, founder):
    dept = department(client, founder)
    people = {}
    for name in ('CEO', 'Engineering Manager', 'Project Manager', 'Research Analyst',
                 'System Architect', 'Software Developer', 'QA Specialist',
                 'DevOps Release Specialist'):
        people[name] = post(client, '/v1/organization/employees', founder,
                            {'department_id': dept, 'name': name, 'kind': 'ai'})['id']
    response = client.put(BASE+'/employees/'+people['CEO']+'/role', headers=founder, json={
        'role_title': 'Chief Executive Officer',
        'core_responsibilities': 'Delivery leadership for Founder approved project',
        'extra_responsibilities': 'No unapproved external tools'})
    assert response.status_code == 200, response.text
    post(client, BASE+'/board/appoint', founder,
         {'seat': 'Strategy & Vision', 'employee_id': people['CEO']})
    return people


def _waiting_task(client, founder):
    project = post(client, BASE+'/projects/start', founder, {
        'brief': 'Build secure product with research, architecture, code, QA and release evidence',
        'operation_key': str(uuid4())})
    plan = post(client, '/v1/brain/plans/'+project['plan_id']+'/submit', founder)
    post(client, '/v1/governance/approvals/'+plan['approval_id']+'/decision', founder,
         {'approve': True, 'reason': 'Founder approves the project'})
    post(client, '/v1/brain/plans/'+project['plan_id']+'/activate', founder)
    task_id = post(client, '/v1/brain/plans/'+project['plan_id']+'/materialize',
                   founder)['task_ids'][0]
    post(client, '/v1/console/tasks/'+task_id+'/request-approval', founder)
    return project, task_id


def _set(db, tenant, project, task_id, *, manager, project_manager, founder_id):
    db.execute("UPDATE ago_governed_tasks SET accountable_manager_id=%s WHERE tenant_id=%s "
               "AND id=%s", (manager, tenant, task_id))
    db.execute("UPDATE ago_founder_project_lead SET accountable_manager_id=%s,assigned_by=%s "
               "WHERE tenant_id=%s AND intake_id=%s",
               (project_manager, founder_id, tenant, project['id']))


def _decision(db, tenant, task_id):
    return db.execute("""SELECT a.reviewer_id,a.status,a.reason,h.approver_level,h.skipped,
                                h.worker_id,h.founder_session_id
        FROM ago_governed_tasks t JOIN ago_approval_requests a
          ON a.tenant_id=t.tenant_id AND a.id=t.approval_id
        LEFT JOIN ago_hierarchy_task_approvals h
          ON h.tenant_id=a.tenant_id AND h.approval_id=a.id
        WHERE t.tenant_id=%s AND t.id=%s""", (tenant, task_id)).fetchone()


def test_direct_ai_manager_approves_and_is_recorded_as_responsible(case):
    client, headers, info = case
    db, tenant, founder = info['db'], info['tenant'], headers['founder']
    people = _company(client, founder)
    project, task_id = _waiting_task(client, founder)
    _set(db, tenant, project, task_id, manager=people['Engineering Manager'],
         project_manager=people['Project Manager'], founder_id=info['founder_id'])
    result = post(client, BASE+'/projects/'+project['id']+'/ceo/reconcile', founder)
    assert result['approved_task_ids'] == [task_id]
    assert result['task_approvers'] == [{'task_id': task_id,
        'approver_id': people['Engineering Manager'], 'approver_name': 'Engineering Manager',
        'approver_level': 'manager'}]
    row = _decision(db, tenant, task_id)
    assert str(row['reviewer_id']) == people['Engineering Manager'] and row['status'] == 'approved'
    assert row['approver_level'] == 'manager' and row['skipped'] == []
    assert 'is responsible for this decision' in row['reason']
    assert str(row['founder_session_id']) == info['founder_id']
    audit = db.execute("SELECT actor_id FROM ago_approval_audit WHERE tenant_id=%s AND "
                       "request_id=(SELECT approval_id FROM ago_governed_tasks WHERE "
                       "tenant_id=%s AND id=%s) AND event='approved'",
                       (tenant, tenant, task_id)).fetchone()
    assert str(audit['actor_id']) == people['Engineering Manager']
    with pytest.raises(Exception, match='append-only|cannot|immutable'):
        with db.transaction():
            db.execute("UPDATE ago_hierarchy_task_approvals SET approver_level='ceo' "
                       "WHERE tenant_id=%s", (tenant,))


def test_a_human_manager_escalates_to_the_ai_project_manager(case):
    client, headers, info = case
    db, tenant, founder = info['db'], info['tenant'], headers['founder']
    people = _company(client, founder)
    project, task_id = _waiting_task(client, founder)
    # The Founder (a human) is recorded as the worker's manager: AI hierarchy skips it.
    _set(db, tenant, project, task_id, manager=info['founder_id'],
         project_manager=people['Project Manager'], founder_id=info['founder_id'])
    result = post(client, BASE+'/projects/'+project['id']+'/ceo/reconcile', founder)
    assert result['task_approvers'][0]['approver_level'] == 'project_manager'
    row = _decision(db, tenant, task_id)
    assert str(row['reviewer_id']) == people['Project Manager']
    assert row['skipped'] == [{'level': 'manager', 'employee_id': info['founder_id'],
                               'reason': 'not an AI employee'}]
    assert 'escalated past: manager (not an AI employee)' in row['reason']


def test_when_manager_and_project_manager_are_the_worker_the_ai_ceo_decides(case):
    client, headers, info = case
    db, tenant, founder = info['db'], info['tenant'], headers['founder']
    people = _company(client, founder)
    project, task_id = _waiting_task(client, founder)
    worker = str(db.execute("SELECT assignee_id FROM ago_governed_tasks WHERE tenant_id=%s "
                            "AND id=%s", (tenant, task_id)).fetchone()['assignee_id'])
    _set(db, tenant, project, task_id, manager=worker, project_manager=worker,
         founder_id=info['founder_id'])
    result = post(client, BASE+'/projects/'+project['id']+'/ceo/reconcile', founder)
    assert result['task_approvers'][0]['approver_level'] == 'ceo'
    row = _decision(db, tenant, task_id)
    assert str(row['reviewer_id']) == people['CEO'] and str(row['worker_id']) == worker
    assert [s['reason'] for s in row['skipped']] == ['is the worker', 'is the worker']


def test_a_terminated_manager_is_skipped(case):
    client, headers, info = case
    db, tenant, founder = info['db'], info['tenant'], headers['founder']
    people = _company(client, founder)
    project, task_id = _waiting_task(client, founder)
    _set(db, tenant, project, task_id, manager=people['Engineering Manager'],
         project_manager=people['Project Manager'], founder_id=info['founder_id'])
    _change(client, founder, headers['reviewer'], 'terminated', people['Engineering Manager'])
    post(client, BASE+'/projects/'+project['id']+'/ceo/reconcile', founder)
    row = _decision(db, tenant, task_id)
    assert row['approver_level'] == 'project_manager'
    assert row['skipped'][0]['reason'] == 'no longer employed'
