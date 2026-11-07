"""Issue #8 M4: an independent AI QA employee reviews a finished stage task.

Real signed sessions and PostgreSQL. The builder run and the QA model are
injected fakes (no Ollama); everything AGO records about them is real.
"""
from uuid import uuid4

import pytest

import ago.ai_qa_review as ai_qa_review
from test_enterprise_http_21_27 import department
from test_m7_http_postgres import case as case, post

BASE = '/v1/organization/company'


class FakeModel:
    def __init__(self, answer):
        self.answer, self.prompts = answer, []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return self.answer


def _completed_discovery(client, headers, info, monkeypatch):
    founder, db, tenant = headers['founder'], info['db'], info['tenant']
    dept = department(client, founder)
    worker = post(client, '/v1/organization/employees', founder,
                  {'department_id': dept, 'name': 'Research Worker', 'kind': 'ai'})['id']
    qa = post(client, '/v1/organization/employees', founder,
              {'department_id': dept, 'name': 'QA Engineer', 'kind': 'ai'})['id']
    other = post(client, '/v1/organization/employees', founder,
                 {'department_id': dept, 'name': 'Marketing Writer', 'kind': 'ai'})['id']
    for who, title in ((qa, 'QA Engineer'), (other, 'Marketing Writer')):
        update = client.put(BASE+'/employees/'+who+'/role', headers=founder, json={
            'role_title': title, 'core_responsibilities': 'Review delivered work',
            'extra_responsibilities': 'Record findings'})
        assert update.status_code == 200, update.text
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
    assignee = str(db.execute("SELECT assignee_id FROM ago_governed_tasks WHERE tenant_id=%s "
                              "AND id=%s", (tenant, task_id)).fetchone()['assignee_id'])

    def built(task):
        return {'kind': 'local_company_governed_handoff', 'handoffs': [
            {'role': 'employee', 'employee_id': assignee, 'employee_name': 'Research Worker',
             'draft': 'DELIVERABLE: admissions tracker requirements and acceptance checklist'}]}

    import ago.api_agents as api_agents
    monkeypatch.setattr(api_agents, 'optional_model_handlers',
                        lambda *a, **k: {'internal:brief': built})
    response = client.post('/v1/agents/tasks/'+task_id+'/run', headers=founder)
    assert response.status_code == 200, response.text
    db.execute("INSERT INTO ago_credit_budgets(tenant_id,ceiling) VALUES (%s,5) "
               "ON CONFLICT(tenant_id) DO UPDATE SET ceiling=5", (tenant,))
    return project, task_id, {'worker': worker, 'qa': qa, 'other': other, 'assignee': assignee}


def _use_model(monkeypatch, answer):
    model = FakeModel(answer)
    monkeypatch.setattr(ai_qa_review, 'local_qa_provider', lambda: (model, 'qwen-test'))
    return model


def test_ai_qa_employee_records_a_real_pass_and_completes_the_stage(case, monkeypatch):
    client, headers, info = case
    db, tenant, founder = info['db'], info['tenant'], headers['founder']
    project, task_id, people = _completed_discovery(client, headers, info, monkeypatch)
    model = _use_model(monkeypatch, 'FINDINGS:\n- checklist present\nQA_VERDICT: PASS')
    endpoint = BASE+'/projects/'+project['id']+'/stages/discovery/ai-qa'
    body = {'qa_employee_id': people['qa'], 'operation_key': str(uuid4())}

    assert client.post(endpoint, json=body).status_code == 401
    post(client, endpoint, headers['reviewer'], body, expected=403)
    post(client, BASE+'/projects/'+str(uuid4())+'/stages/discovery/ai-qa', founder,
         body, expected=404)
    post(client, endpoint, founder, {**body, 'extra': 1}, expected=422)
    # Not a QA role, the builder itself, and an unknown employee are refused.
    post(client, endpoint, founder, {**body, 'qa_employee_id': people['other']}, expected=403)
    post(client, endpoint, founder, {**body, 'qa_employee_id': people['assignee']},
         expected=403)
    post(client, endpoint, founder, {**body, 'qa_employee_id': str(uuid4())}, expected=404)
    assert model.prompts == []

    result = post(client, endpoint, founder, body)
    assert result['kind'] == 'ago_ai_qa_review_v1'
    assert (result['verdict'], result['review_recorded']) == ('pass', True)
    assert result['qa_employee_name'] == 'QA Engineer' and result['model'] == 'qwen-test'
    assert result['executed_or_released'] is False
    assert len(model.prompts) == 1 and 'QA_VERDICT' in model.prompts[0]
    assert 'admissions tracker requirements' in model.prompts[0]

    review = db.execute("SELECT reviewer_id,author_id,verdict,evidence FROM ago_task_reviews "
                        "WHERE tenant_id=%s AND task_id=%s", (tenant, task_id)).fetchone()
    assert str(review['reviewer_id']) == people['qa']
    assert str(review['author_id']) == people['assignee']
    assert review['verdict'] == 'pass' and result['receipt_id'] in review['evidence']
    receipt = db.execute("SELECT verdict,model,response_text,requested_by,credit_usage_id "
                         "FROM ago_ai_qa_reviews WHERE tenant_id=%s AND task_id=%s",
                         (tenant, task_id)).fetchone()
    assert receipt['verdict'] == 'pass' and receipt['model'] == 'qwen-test'
    assert str(receipt['requested_by']) == info['founder_id']
    assert db.execute("SELECT consumed FROM ago_credit_budgets WHERE tenant_id=%s",
                      (tenant,)).fetchone()['consumed'] == 1

    detail = client.get(BASE+'/projects/'+project['id'], headers=founder).json()
    stage = next(s for s in detail['stages'] if s['stage'] == 'discovery')
    assert stage['qa_verdict'] == 'pass'
    # One verdict per task; receipts cannot be rewritten.
    post(client, endpoint, founder, {**body, 'operation_key': str(uuid4())}, expected=400)
    with pytest.raises(Exception, match='append-only|cannot|immutable'):
        with db.transaction():
            db.execute("UPDATE ago_ai_qa_reviews SET verdict='fail' WHERE tenant_id=%s",
                       (tenant,))


def test_an_unclear_ai_answer_records_a_receipt_but_no_verdict(case, monkeypatch):
    client, headers, info = case
    db, tenant, founder = info['db'], info['tenant'], headers['founder']
    project, task_id, people = _completed_discovery(client, headers, info, monkeypatch)
    _use_model(monkeypatch, 'Looks fine overall.\nQA_VERDICT: PASS\nQA_VERDICT: FAIL')
    endpoint = BASE+'/projects/'+project['id']+'/stages/discovery/ai-qa'
    key = str(uuid4())
    result = post(client, endpoint, founder, {'qa_employee_id': people['qa'],
                                              'operation_key': key})
    assert (result['verdict'], result['review_recorded']) == ('unverified', False)
    assert db.execute("SELECT count(*) AS n FROM ago_task_reviews WHERE tenant_id=%s AND "
                      "task_id=%s", (tenant, task_id)).fetchone()['n'] == 0
    assert db.execute("SELECT verdict FROM ago_ai_qa_reviews WHERE tenant_id=%s",
                      (tenant,)).fetchone()['verdict'] == 'unverified'
    # Re-sending the same request is not a free retry; a new request may try again.
    post(client, endpoint, founder, {'qa_employee_id': people['qa'], 'operation_key': key},
         expected=400)
    _use_model(monkeypatch, 'FINDINGS:\n- acceptance checklist missing\nQA_VERDICT: FAIL')
    failed = post(client, endpoint, founder, {'qa_employee_id': people['qa'],
                                              'operation_key': str(uuid4())})
    assert failed['verdict'] == 'fail'
    assert db.execute("SELECT verdict FROM ago_task_reviews WHERE tenant_id=%s AND task_id=%s",
                      (tenant, task_id)).fetchone()['verdict'] == 'fail'


def test_ai_qa_needs_the_local_model_and_a_finished_run(case, monkeypatch):
    client, headers, info = case
    founder = headers['founder']
    project, task_id, people = _completed_discovery(client, headers, info, monkeypatch)
    endpoint = BASE+'/projects/'+project['id']+'/stages/discovery/ai-qa'
    body = {'qa_employee_id': people['qa'], 'operation_key': str(uuid4())}
    monkeypatch.setattr(ai_qa_review, 'local_qa_provider', lambda: None)
    post(client, endpoint, founder, body, expected=403)

    class Broken:
        def generate(self, prompt):
            raise TimeoutError('model timed out')

    monkeypatch.setattr(ai_qa_review, 'local_qa_provider', lambda: (Broken(), 'qwen-test'))
    assert client.post(endpoint, json=body, headers=founder).status_code == 502
    # A stage with no plan step has nothing to review.
    post(client, BASE+'/projects/'+project['id']+'/stages/architecture/ai-qa', founder,
         {**body, 'operation_key': str(uuid4())}, expected=404)


def test_a_qa_fail_opens_an_audited_rework_task_and_a_fresh_qa(case, monkeypatch):
    client, headers, info = case
    db, tenant, founder = info['db'], info['tenant'], headers['founder']
    project, task_id, people = _completed_discovery(client, headers, info, monkeypatch)
    base = BASE+'/projects/'+project['id']+'/stages/discovery'
    recovery = {'failed_task_id': task_id, 'reason': 'Add the missing acceptance checklist'}
    # A completed task with no QA verdict (or a PASS) cannot be reworked.
    post(client, base+'/recovery', founder, recovery, expected=400)
    _use_model(monkeypatch, 'FINDINGS:\n- acceptance checklist missing\nQA_VERDICT: FAIL')
    post(client, base+'/ai-qa', founder, {'qa_employee_id': people['qa'],
                                          'operation_key': str(uuid4())})
    rework = post(client, base+'/recovery', founder, recovery)
    assert rework['recovery_kind'] == 'qa_rework'
    assert rework['recovery_task_status'] == 'proposed' and rework['run_started'] is False
    new = rework['recovery_task_id']
    old = db.execute("SELECT status FROM ago_governed_tasks WHERE tenant_id=%s AND id=%s",
                     (tenant, task_id)).fetchone()
    assert old['status'] == 'completed'
    assert db.execute("SELECT verdict FROM ago_task_reviews WHERE tenant_id=%s AND task_id=%s",
                      (tenant, task_id)).fetchone()['verdict'] == 'fail'
    detail = client.get(BASE+'/projects/'+project['id'], headers=founder).json()
    stage = next(s for s in detail['stages'] if s['stage'] == 'discovery')
    assert stage['task_id'] == new and stage['qa_verdict'] is None
    post(client, base+'/recovery', founder, recovery, expected=400)


def test_a_qa_pass_cannot_be_reworked(case, monkeypatch):
    client, headers, info = case
    founder = headers['founder']
    project, task_id, people = _completed_discovery(client, headers, info, monkeypatch)
    base = BASE+'/projects/'+project['id']+'/stages/discovery'
    _use_model(monkeypatch, 'FINDINGS:\n- ok\nQA_VERDICT: PASS')
    post(client, base+'/ai-qa', founder, {'qa_employee_id': people['qa'],
                                          'operation_key': str(uuid4())})
    post(client, base+'/recovery', founder,
         {'failed_task_id': task_id, 'reason': 'Try again'}, expected=400)
