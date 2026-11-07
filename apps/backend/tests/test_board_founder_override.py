"""Founder rule: after the AI CEO and CTO approve, a Finance/Risk/Quality denial is
shown to the Founder, who may allow the project. Real signed sessions and
PostgreSQL; the AI run is an injected handler returning the recorded Board shape.
"""
from uuid import uuid4

import pytest

from ago.company_ollama_chain_queries import CompanyOllamaChainQueries
from test_enterprise_http_21_27 import department
from test_m7_http_postgres import case as case, post

BASE = '/v1/organization/company'


def _vote(seat, recommendation, reason=''):
    return {'seat': seat, 'employee_id': str(uuid4()), 'recommendation': recommendation,
            'verifiable_model_output': recommendation != 'unverified',
            'binding_authorization': False, 'denial_reason': reason, 'founder_override': False}


def _blocked_discovery(client, headers, info, monkeypatch, *, cto='approve',
                       seat='Finance & Budget'):
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

    def board_stopped(task):
        votes = [_vote('Strategy & Vision', 'approve'), _vote('Technology Oversight', cto)]
        if cto == 'approve':
            votes.append(_vote(seat, 'deny', 'No cost estimate for the pilot.'))
        return {'kind': 'local_company_governed_handoff', 'handoffs': [],
                'board_recommendations': votes, 'board_blocked': True,
                'blocked_by_board_seat': seat if cto == 'approve' else 'Technology Oversight',
                'board_block_reason': 'deny'}

    import ago.api_agents as api_agents
    monkeypatch.setattr(api_agents, 'optional_model_handlers',
                        lambda *a, **k: {'internal:brief': board_stopped})
    response = client.post('/v1/agents/tasks/'+task_id+'/run', headers=founder)
    assert response.status_code == 200 and response.json()['delivery_status'] == 'blocked'
    return project, task_id


def test_founder_allows_the_project_past_a_finance_denial(case, monkeypatch):
    client, headers, info = case
    db, tenant, founder = info['db'], info['tenant'], headers['founder']
    project, failed = _blocked_discovery(client, headers, info, monkeypatch)
    assert db.execute("SELECT status FROM ago_governed_tasks WHERE tenant_id=%s AND id=%s",
                      (tenant, failed)).fetchone()['status'] == 'failed'
    endpoint = BASE+'/projects/'+project['id']+'/stages/discovery/board-override'
    body = {'failed_task_id': failed, 'seat': 'Finance & Budget',
            'reason': 'Budget is a local pilot with no spending; continue'}
    assert client.post(endpoint, json=body).status_code == 401
    post(client, endpoint, headers['reviewer'], body, expected=403)
    post(client, BASE+'/projects/'+str(uuid4())+'/stages/discovery/board-override', founder,
         body, expected=404)
    # CEO/CTO seats are never overridable; a seat that did not stop the run is refused.
    post(client, endpoint, founder, {**body, 'seat': 'Strategy & Vision'}, expected=422)
    post(client, endpoint, founder, {**body, 'seat': 'Risk & Compliance'}, expected=400)
    post(client, endpoint, founder, {**body, 'reason': ''}, expected=422)

    allowed = post(client, endpoint, founder, body)
    assert allowed['kind'] == 'ago_board_founder_override_v1'
    assert allowed['seat'] == 'Finance & Budget' and allowed['override_recorded'] is True
    assert allowed['denial_reason'] == 'No cost estimate for the pilot.'
    assert allowed['recovery_task_status'] == 'proposed' and allowed['run_started'] is False
    row = db.execute("SELECT seat,denial_vote,denial_reason,founder_id,reason "
                     "FROM ago_board_founder_overrides WHERE tenant_id=%s",
                     (tenant,)).fetchone()
    assert (row['seat'], row['denial_vote'], str(row['founder_id'])) == (
        'Finance & Budget', 'deny', info['founder_id'])
    # The chain sees the allowed seat for THIS project only.
    seats = CompanyOllamaChainQueries(db).founder_board_overrides(
        tenant_id=tenant, intake_id=project['id'])
    assert seats == frozenset({'Finance & Budget'})
    assert CompanyOllamaChainQueries(db).founder_board_overrides(
        tenant_id=tenant, intake_id=str(uuid4())) == frozenset()
    # deny -> revise -> resubmit: the new task carries the Board feedback.
    notes = CompanyOllamaChainQueries(db).revision_notes(
        tenant_id=tenant, task_id=allowed['recovery_task_id'])
    assert notes.startswith('Finance & Budget: No cost estimate for the pilot.')
    assert 'Founder allowed the project over the Finance & Budget denial' in notes
    assert CompanyOllamaChainQueries(db).revision_notes(tenant_id=tenant, task_id=failed) == ''
    # The stage now points at the new task; the old one cannot be allowed again.
    post(client, endpoint, founder, body, expected=400)
    with pytest.raises(Exception, match='append-only|cannot|immutable'):
        with db.transaction():
            db.execute("UPDATE ago_board_founder_overrides SET reason='x' WHERE tenant_id=%s",
                       (tenant,))


def test_no_override_when_the_cto_did_not_approve(case, monkeypatch):
    client, headers, info = case
    founder = headers['founder']
    project, failed = _blocked_discovery(client, headers, info, monkeypatch, cto='deny')
    endpoint = BASE+'/projects/'+project['id']+'/stages/discovery/board-override'
    # The CTO stopped it: the Finance seat did not, and CTO is never overridable.
    post(client, endpoint, founder, {'failed_task_id': failed, 'seat': 'Finance & Budget',
                                     'reason': 'Continue'}, expected=400)
    assert info['db'].execute("SELECT count(*) AS n FROM ago_board_founder_overrides "
                              "WHERE tenant_id=%s", (info['tenant'],)).fetchone()['n'] == 0
