"""Issue #10: a failed project stage task gets an authorized, audited recovery task.

Real signed sessions and PostgreSQL. The run failure is produced by an injected
handler that raises the same typed credit error the live Founder PC hit (no
budget configured); no model is called. Nothing here approves or runs the
recovery task: it must pass the ordinary approval flow afterwards.
"""
from uuid import uuid4

import pytest

from ago.credit_domain import CreditBudgetMissing
from test_enterprise_http_21_27 import department
from test_m7_http_postgres import case as case, post

BASE = '/v1/organization/company'


def _failed_discovery(client, headers, info, monkeypatch):
    founder = headers['founder']
    dept = department(client, founder)
    post(client, '/v1/organization/employees', founder,
         {'department_id': dept, 'name': 'Research Worker', 'kind': 'ai'})
    project = post(client, BASE+'/projects/start', founder, {
        'brief': 'Build a local admissions tracker with reviewed acceptance criteria',
        'operation_key': str(uuid4())})
    plan = post(client, '/v1/brain/plans/'+project['plan_id']+'/submit', founder)
    post(client, '/v1/governance/approvals/'+plan['approval_id']+'/decision', founder,
         {'approve': True, 'reason': 'Founder approves the project scope'})
    post(client, '/v1/brain/plans/'+project['plan_id']+'/activate', founder)
    task_id = post(client, '/v1/brain/plans/'+project['plan_id']+'/materialize',
                   founder)['task_ids'][0]
    approval = post(client, '/v1/governance/approvals', founder, {'action': 'internal:brief'})
    post(client, '/v1/tasks/'+task_id+'/approval', founder,
         {'approval_id': approval['request_id']})
    post(client, '/v1/governance/approvals/'+approval['request_id']+'/decision',
         headers['reviewer'], {'approve': True, 'reason': 'Independent task review'})

    def no_budget(task):
        raise CreditBudgetMissing('No configured virtual-credit budget')

    import ago.api_agents as api_agents
    monkeypatch.setattr(api_agents, 'optional_model_handlers',
                        lambda *a, **k: {'internal:brief': no_budget})
    response = client.post('/v1/agents/tasks/'+task_id+'/run', headers=founder)
    assert response.status_code == 502, response.text
    return project, task_id


def test_failed_run_records_a_safe_reason_and_founder_recovers_the_stage(case, monkeypatch):
    client, headers, info = case
    db, tenant, founder = info['db'], info['tenant'], headers['founder']
    project, failed = _failed_discovery(client, headers, info, monkeypatch)

    run = db.execute("SELECT status,failure_code,result FROM ago_agent_runs "
                     "WHERE tenant_id=%s AND task_id=%s", (tenant, failed)).fetchone()
    assert (run['status'], run['failure_code'], run['result']) == (
        'failed', 'credit_budget_missing', None)

    # The read-only self-check now names the cause and refuses a replay.
    preflight = client.get('/v1/agents/tasks/'+failed+'/engineering-preflight', headers=founder)
    if preflight.status_code == 200:
        body = preflight.json()
        assert body['latest_run_failure_code'] == 'credit_budget_missing'
        assert 'prior_run_found_do_not_replay' in body['blocking_checks']

    endpoint = BASE+'/projects/'+project['id']+'/stages/discovery/recovery'
    body = {'failed_task_id': failed, 'reason': 'Credit allowance was 0; now configured'}
    assert client.post(endpoint, json=body).status_code == 401
    post(client, endpoint, headers['reviewer'], body, expected=403)
    post(client, BASE+'/projects/'+str(uuid4())+'/stages/discovery/recovery', founder,
         body, expected=404)
    post(client, endpoint, founder, {**body, 'failed_task_id': str(uuid4())}, expected=400)
    # A stage without a plan step (unstaffed here) has nothing to recover.
    post(client, BASE+'/projects/'+project['id']+'/stages/architecture/recovery', founder,
         body, expected=404)
    post(client, BASE+'/projects/'+project['id']+'/stages/marketing/recovery', founder,
         body, expected=422)
    post(client, endpoint, founder, {'failed_task_id': failed, 'reason': ''}, expected=422)
    post(client, endpoint, founder, {**body, 'extra': 1}, expected=422)

    recovered = post(client, endpoint, founder, body)
    assert recovered['kind'] == 'ago_stage_task_recovery_v1'
    assert recovered['failed_task_id'] == failed
    assert recovered['recovery_task_status'] == 'proposed'
    assert recovered['approval_required'] is True and recovered['run_started'] is False
    new = recovered['recovery_task_id']
    assert new != failed

    step = db.execute("""SELECT ps.task_id FROM ago_founder_intake_stages s
        JOIN ago_plan_steps ps ON ps.tenant_id=s.tenant_id AND ps.id=s.plan_step_id
        WHERE s.tenant_id=%s AND s.intake_id=%s AND s.stage='discovery'""",
        (tenant, project['id'])).fetchone()
    assert str(step['task_id']) == new
    old, fresh = (db.execute("SELECT status,action,assignee_id FROM ago_governed_tasks "
                             "WHERE tenant_id=%s AND id=%s", (tenant, t)).fetchone()
                  for t in (failed, new))
    assert old['status'] == 'failed' and fresh['status'] == 'proposed'
    assert (fresh['action'], fresh['assignee_id']) == (old['action'], old['assignee_id'])
    # Failed evidence is untouched and the recovery is audited.
    assert db.execute("SELECT status,failure_code FROM ago_agent_runs WHERE tenant_id=%s "
                      "AND task_id=%s", (tenant, failed)).fetchone()['failure_code'] == \
        'credit_budget_missing'
    audit = db.execute("SELECT failed_task_id,recovery_task_id,actor_id,reason "
                       "FROM ago_plan_step_task_recoveries WHERE tenant_id=%s",
                       (tenant,)).fetchall()
    assert len(audit) == 1
    assert (str(audit[0]['failed_task_id']), str(audit[0]['recovery_task_id']),
            str(audit[0]['actor_id'])) == (failed, new, info['founder_id'])
    assert audit[0]['reason'] == 'Credit allowance was 0; now configured'
    assert db.execute("SELECT count(*) AS n FROM ago_agent_runs WHERE tenant_id=%s "
                      "AND task_id=%s", (tenant, new)).fetchone()['n'] == 0

    # No second recovery of the same failure, and the new task is not failed.
    post(client, endpoint, founder, body, expected=400)
    post(client, endpoint, founder, {**body, 'failed_task_id': new}, expected=400)

    # The recovery task enters the ordinary approval flow.
    approval = post(client, '/v1/governance/approvals', founder, {'action': 'internal:brief'})
    post(client, '/v1/tasks/'+new+'/approval', founder, {'approval_id': approval['request_id']})
    assert db.execute("SELECT status FROM ago_governed_tasks WHERE tenant_id=%s AND id=%s",
                      (tenant, new)).fetchone()['status'] == 'waiting_approval'


def test_database_refuses_unaudited_relinks_and_audit_rewrites(case, monkeypatch):
    client, headers, info = case
    db, tenant = info['db'], info['tenant']
    project, failed = _failed_discovery(client, headers, info, monkeypatch)
    step = db.execute("""SELECT ps.id,ps.action,ps.assignee_id FROM ago_founder_intake_stages s
        JOIN ago_plan_steps ps ON ps.tenant_id=s.tenant_id AND ps.id=s.plan_step_id
        WHERE s.tenant_id=%s AND s.intake_id=%s AND s.stage='discovery'""",
        (tenant, project['id'])).fetchone()
    stray = str(uuid4())
    db.execute("INSERT INTO ago_governed_tasks(id,tenant_id,action,assignee_id,status) "
               "VALUES (%s,%s,%s,%s,'proposed')",
               (stray, tenant, step['action'], step['assignee_id']))
    with pytest.raises(Exception, match='Approved plans cannot be edited'):
        with db.transaction():
            db.execute("UPDATE ago_plan_steps SET task_id=%s WHERE tenant_id=%s AND id=%s",
                       (stray, tenant, step['id']))
    recovered = post(client, BASE+'/projects/'+project['id']+'/stages/discovery/recovery',
                     headers['founder'], {'failed_task_id': failed, 'reason': 'Retry after fix'})
    with pytest.raises(Exception, match='append-only|cannot|immutable'):
        with db.transaction():
            db.execute("UPDATE ago_plan_step_task_recoveries SET reason='changed' "
                       "WHERE tenant_id=%s", (tenant,))
    assert recovered['recovery_task_id'] != stray


@pytest.mark.parametrize("goal_status", ["cancelled", "completed"])
def test_recovery_rejects_inactive_goal_without_creating_work(case, monkeypatch, goal_status):
    client, headers, info = case
    db, tenant = info['db'], info['tenant']
    project, failed = _failed_discovery(client, headers, info, monkeypatch)
    before = db.execute("SELECT count(*) AS n FROM ago_governed_tasks WHERE tenant_id=%s",
                        (tenant,)).fetchone()['n']
    db.execute("UPDATE ago_goals SET status=%s WHERE tenant_id=%s AND id="
               "(SELECT goal_id FROM ago_strategy_plans WHERE tenant_id=%s AND id=%s)",
               (goal_status, tenant, tenant, project['plan_id']))
    post(client, BASE+'/projects/'+project['id']+'/stages/discovery/recovery',
         headers['founder'], {'failed_task_id': failed, 'reason': 'Retry after fix'}, expected=403)
    assert db.execute("SELECT count(*) AS n FROM ago_governed_tasks WHERE tenant_id=%s",
                      (tenant,)).fetchone()['n'] == before
    assert db.execute("SELECT count(*) AS n FROM ago_plan_step_task_recoveries WHERE tenant_id=%s",
                      (tenant,)).fetchone()['n'] == 0


def test_recovered_task_runs_only_after_new_approval_and_keeps_failed_evidence(case, monkeypatch):
    client, headers, info = case
    db, tenant, founder = info['db'], info['tenant'], headers['founder']
    project, failed = _failed_discovery(client, headers, info, monkeypatch)
    recovered = post(client, BASE+'/projects/'+project['id']+'/stages/discovery/recovery',
                     founder, {'failed_task_id': failed, 'reason': 'Provider repaired'})
    new = recovered['recovery_task_id']
    calls = []

    def repaired_provider(task):
        calls.append(task.id)
        return {'summary': 'Controlled recovery test result'}

    import ago.api_agents as api_agents
    monkeypatch.setattr(api_agents, 'optional_model_handlers',
                        lambda *a, **k: {'internal:brief': repaired_provider})
    post(client, '/v1/agents/tasks/'+new+'/run', founder, expected=403)
    approval = post(client, '/v1/governance/approvals', founder, {'action': 'internal:brief'})
    post(client, '/v1/tasks/'+new+'/approval', founder, {'approval_id': approval['request_id']})
    post(client, '/v1/agents/tasks/'+new+'/run', founder, expected=403)
    assert calls == []
    post(client, '/v1/governance/approvals/'+approval['request_id']+'/decision',
         headers['reviewer'], {'approve': True, 'reason': 'Approve recovered task'})
    result = post(client, '/v1/agents/tasks/'+new+'/run', founder)
    assert result['status'] == 'completed'
    assert calls == [new]
    post(client, '/v1/agents/tasks/'+new+'/run', founder, expected=403)
    assert calls == [new]
    assert db.execute("SELECT status FROM ago_governed_tasks WHERE tenant_id=%s AND id=%s",
                      (tenant, new)).fetchone()['status'] == 'completed'
    old = db.execute("SELECT status,failure_code,result FROM ago_agent_runs "
                     "WHERE tenant_id=%s AND task_id=%s", (tenant, failed)).fetchone()
    assert (old['status'], old['failure_code'], old['result']) == (
        'failed', 'credit_budget_missing', None)
