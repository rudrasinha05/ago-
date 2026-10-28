"""Private project execution must use current ownership, not cached token roles."""
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from ago.agent_runtime import AgentRuntime
from ago.agent_runtime_queries import AgentRuntimeQueries
from ago.enterprise_store import EnterpriseOperationsStore
from ago.security_controls import SecurityControls
from ago.task_store import TaskStore
from test_m7_http_postgres import case as case, post
from test_enterprise_http_21_27 import department, employee


@pytest.mark.parametrize('owner,current_founder', [(True, False), (False, True)])
def test_private_project_rejects_revoked_or_different_founder_before_dispatch(owner, current_founder):
    actor = SimpleNamespace(subject=str(uuid4()), tenant_id=str(uuid4()), roles=('founder',))
    queries, enterprise, security, tasks = Mock(), Mock(), Mock(), Mock()
    queries.select_ago_governed_tasks_01.return_value.fetchone.return_value = {
        'action': 'internal:brief', 'assignee_id': str(uuid4())}
    queries.select_ago_employees_02.return_value.fetchone.return_value = {'kind': 'ai'}
    queries.select_ago_founder_project_12.return_value.fetchone.return_value = {
        'id': str(uuid4()), 'title': 'Private project', 'brief': 'Confidential source',
        'founder_id': actor.subject if owner else str(uuid4())}
    security.permitted.return_value = current_founder
    tasks.authorize_and_start.side_effect = AssertionError('Must deny before consuming approval')
    repositories = Mock()
    repositories.resolve.side_effect = {
        AgentRuntimeQueries: queries, EnterpriseOperationsStore: enterprise,
        SecurityControls: security, TaskStore: tasks,
    }.__getitem__
    db = Mock()
    db.transaction.side_effect = nullcontext
    handler = Mock()
    runtime = AgentRuntime(db, handlers={'internal:brief': handler}, repositories=repositories)
    with pytest.raises(PermissionError, match='current project founder authority'):
        runtime.run(task_id=str(uuid4()), actor=actor)
    tasks.authorize_and_start.assert_not_called()
    queries.insert_ago_agent_runs_03.assert_not_called()
    handler.assert_not_called()
    if owner:
        security.permitted.assert_called_once_with(actor, 'approval:founder', actor.tenant_id)


@pytest.mark.parametrize('revoked', [True, False])
def test_signed_private_project_dispatch_requires_its_current_founder(case, revoked):
    client, headers, info = case
    founder, db = headers['founder'], info['db']
    dept = department(client, founder)
    employee(client, founder, dept)
    project = post(client, '/v1/organization/company/projects/start', founder, {
        'brief': 'Build a private student report with scoped confidential source evidence',
        'operation_key': str(uuid4()),
    })
    plan_url = '/v1/brain/plans/' + project['plan_id']
    plan = post(client, plan_url + '/submit', founder)
    post(client, '/v1/governance/approvals/' + plan['approval_id'] + '/decision',
         founder, {'approve': True, 'reason': 'Approve private project scope'})
    post(client, plan_url + '/activate', founder)
    task = post(client, plan_url + '/materialize', founder)['task_ids'][0]
    if revoked:
        # Retain dispatch permission through another real role while the token
        # still carries its former founder role. Revocation must be immediate.
        db.execute("INSERT INTO ago_user_roles(tenant_id,user_id,role) VALUES (%s,%s,'reviewer')",
                   (info['tenant'], info['founder_id']))
        db.execute("INSERT INTO ago_role_permissions(tenant_id,role,permission) "
                   "VALUES (%s,'reviewer','agent:dispatch') ON CONFLICT DO NOTHING",
                   (info['tenant'],))
        db.execute("DELETE FROM ago_user_roles WHERE tenant_id=%s AND user_id=%s AND role='founder'",
                   (info['tenant'], info['founder_id']))
        caller = founder
    else:
        # Another currently appointed founder is not this private brief's owner.
        db.execute("INSERT INTO ago_user_roles(tenant_id,user_id,role) VALUES (%s,%s,'founder')",
                   (info['tenant'], info['reviewer_id']))
        caller = info['login']('m7reviewer@example.test', 'reviewer-test-password-123')
    response = client.post('/v1/agents/tasks/' + task + '/run', headers=caller)
    assert response.status_code == 403, response.text
    assert 'current project founder authority' in response.json()['detail']
    assert db.execute('SELECT status FROM ago_governed_tasks WHERE tenant_id=%s AND id=%s',
                      (info['tenant'], task)).fetchone()['status'] == 'proposed'
    assert db.execute('SELECT 1 FROM ago_agent_runs WHERE tenant_id=%s AND task_id=%s',
                      (info['tenant'], task)).fetchone() is None
