"""PROJ-006 / ACC-152: the server advances a project one governed step at a time,
and a Founder-started local runner keeps it moving without a browser.

Real signed sessions and PostgreSQL; builder runs and the QA model are injected
fakes (no Ollama). The runner is driven through the real HTTP application.
"""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from uuid import uuid4

import pytest

import ago.api_agents as api_agents
from ago.credit_domain import CreditBudgetMissing
from ago.stage_progression import next_step
from test_m7_http_postgres import case as case, post
from test_stage_progression import STAGES, Company

DIR = Path(__file__).resolve().parents[3]/"scripts"
sys.path.insert(0, str(DIR))
spec = spec_from_file_location("ago_project_runner", DIR/"ago_project_runner.py")
runner = module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.fixture
def company(case, monkeypatch):
    c = Company(case, monkeypatch)
    c.failures = []          # exceptions the next builder runs raise, in order

    def handler(task):
        c.seen.append(dict(task.project_context))
        if c.failures:
            raise c.failures.pop(0)
        return {'kind': 'local_company_governed_handoff', 'handoffs': [
            {'role': 'employee', 'employee_id': task.assignee_id, 'draft': 'stage deliverable'}]}

    monkeypatch.setattr(api_agents, 'optional_model_handlers',
                        lambda *a, **k: {'internal:brief': handler})
    c.advance = '/v1/agents/projects/'+c.id+'/advance'
    return c


def test_server_advances_a_whole_project_one_governed_step_at_a_time(company):
    c = company
    assert c.client.post(c.advance).status_code == 401
    post(c.client, c.advance, c.reviewer, expected=403)
    post(c.client, '/v1/agents/projects/'+str(uuid4())+'/advance', c.founder, expected=404)

    taken = []
    for _ in range(40):
        reply = post(c.client, c.advance, c.founder)
        assert reply['kind'] == 'ago_project_advance_v1'
        if reply['done']:
            break
        assert reply['progressed'] is True and reply['needs_founder'] is False, reply
        taken.append((reply['stage'], reply['step']))
    # Each stage: ask -> AI hierarchy approves -> run -> independent QA. The next
    # stage is opened by the AI manager inside the QA step, with no extra request.
    assert taken == [(s, k) for s in STAGES for k in ('request', 'approve', 'run', 'qa')]
    assert reply['message'] == 'Every stage passed independent AI QA.'
    assert [seen['stage'] for seen in c.seen] == list(STAGES)
    detail = c.client.get(c.url, headers=c.founder).json()
    assert detail['qa_passed_stages'] == 5
    # Done stays done: nothing more is requested, approved or run.
    runs = c.db.execute("SELECT count(*) AS n FROM ago_agent_runs WHERE tenant_id=%s",
                        (c.tenant,)).fetchone()['n']
    assert post(c.client, c.advance, c.founder)['done'] is True
    assert c.db.execute("SELECT count(*) AS n FROM ago_agent_runs WHERE tenant_id=%s",
                        (c.tenant,)).fetchone()['n'] == runs == 5


def test_advance_recovers_what_the_ai_manager_may_and_stops_for_the_founder(company):
    c = company
    c.failures = [TimeoutError('model timed out'), CreditBudgetMissing('No budget')]
    steps = [post(c.client, c.advance, c.founder) for _ in range(3)]
    assert [s['step'] for s in steps] == ['request', 'approve', 'run']
    assert steps[2]['run_status'] == 'failed' and steps[2]['progressed'] is True
    # The timeout was already recovered on the server: the new task just continues.
    assert len(c.recoveries('discovery')) == 1
    steps = [post(c.client, c.advance, c.founder) for _ in range(3)]
    assert [s['step'] for s in steps] == ['request', 'approve', 'run']
    # A credit failure is not the AI manager's to retry: the Founder is told why.
    held = post(c.client, c.advance, c.founder)
    assert (held['step'], held['progressed'], held['needs_founder']) == ('recover', False, True)
    assert 'credit_budget_missing' in held['message']
    assert len(c.recoveries('discovery')) == 1
    again = post(c.client, c.advance, c.founder)
    assert again['needs_founder'] is True and len(c.seen) == 2


def test_advance_never_reruns_a_task_and_reports_a_missing_tester(company):
    c = company
    for _ in range(3):
        post(c.client, c.advance, c.founder)            # request, approve, run
    # Both testers leave: QA cannot be independent, so the Founder is asked.
    for name in ('QA Specialist', 'Second Tester'):
        c.db.execute("UPDATE ago_employees SET role_title='Writer' WHERE tenant_id=%s AND id=%s",
                     (c.tenant, c.people[name]))
    held = post(c.client, c.advance, c.founder)
    assert (held['step'], held['needs_founder']) == ('qa', True)
    assert 'No independent AI tester' in held['message']
    assert len(c.seen) == 1 and c.qa_prompts == []


def test_next_step_is_decided_from_recorded_state_only():
    s = lambda stage, position, **extra: {'stage': stage, 'position': position,  # noqa: E731
                                          'task_id': stage+'-task', **extra}
    done = s('discovery', 1, task_status='completed', agent_run_status='completed',
             qa_verdict='pass')
    kind = lambda *stages: next_step(list(stages))['step']  # noqa: E731
    assert kind() == 'unstaffed' and kind(done) == 'done'
    assert kind(s('discovery', 1, task_status='proposed')) == 'request'
    assert kind(s('discovery', 1, task_status='waiting_approval')) == 'approve'
    assert kind(s('discovery', 1, task_status='waiting_approval',
                  task_approval_status='approved')) == 'run'
    assert kind(s('discovery', 1, task_status='waiting_approval',
                  task_approval_status='rejected')) == 'rejected'
    assert kind(s('discovery', 1, task_status='running')) == 'running'
    assert kind(s('discovery', 1, task_status='completed', agent_run_status='completed')) == 'qa'
    assert kind(s('discovery', 1, task_status='completed')) == 'unknown'
    assert kind(s('discovery', 1, task_status='failed')) == 'recover'
    assert kind(s('discovery', 1, task_status='completed', agent_run_status='completed',
                  qa_verdict='fail')) == 'recover'
    assert kind(s('discovery', 1, task_id=None)) == 'unstaffed'
    # Order is by position; a later stage without a task needs an approved specialist.
    assert next_step([s('architecture', 2, task_status='proposed'), done])['stage'] == 'architecture'
    assert kind(done, s('architecture', 2, task_id=None, approved_assignee_id='a')) == 'open_stage'
    assert kind(done, s('architecture', 2, task_id=None)) == 'unstaffed'


def _through(c, expire_after=None):
    """The runner's request function, bound to the real application."""
    calls = {'post': 0, 'logins': 0}

    def request(method, path, body=None):
        if method == 'POST':
            calls['post'] += 1
            if expire_after and calls['post'] == expire_after:
                raise runner.SessionExpired()
            response = c.client.post(path, json=body, headers=c.founder)
        else:
            response = c.client.get(path, headers=c.founder)
        assert response.status_code == 200, response.text
        return response.json()
    return request, calls


def test_runner_finishes_a_real_project_without_a_browser(company):
    c = company
    request, calls = _through(c, expire_after=4)
    preview = runner.run_session(request, project_id=c.id)
    assert preview['status'] == 'read_only_preview' and calls['post'] == 0
    with pytest.raises(PermissionError):
        runner.run_session(request, project_id=c.id, apply=True, confirmation='yes')
    with pytest.raises(PermissionError):
        runner.run_session(request, project_id=c.id, confirmation=runner.CONFIRM)
    assert calls['post'] == 0

    lines, pauses = [], []
    report = runner.run_session(
        request, project_id=c.id, apply=True, confirmation=runner.CONFIRM,
        relogin=lambda: calls.__setitem__('logins', calls['logins']+1),
        report=lines.append, pause=pauses.append)
    assert report['status'] == 'project_done' and report['steps_done'] == 20
    assert report['automatic_replay'] is False and report['service_started_at_boot'] is False
    assert calls['logins'] == 1 and pauses == []
    assert [line['step'] for line in lines[:4]] == ['request', 'approve', 'run', 'qa']
    assert c.client.get(c.url, headers=c.founder).json()['qa_passed_stages'] == 5
    assert len(c.seen) == 5


def test_runner_stops_for_the_founder_and_respects_its_limits(company):
    c = company
    request, _ = _through(c)
    limited = runner.run_session(request, project_id=c.id, apply=True,
                                 confirmation=runner.CONFIRM, max_steps=3)
    assert (limited['status'], limited['limit'], limited['steps_done']) == (
        'limit_reached', 'steps', 3)
    assert len(c.seen) == 1                      # exactly one run happened
    c.db.execute("UPDATE ago_employees SET role_title='Writer' WHERE tenant_id=%s "
                 "AND id IN (%s,%s)", (c.tenant, c.people['QA Specialist'],
                                       c.people['Second Tester']))
    held = runner.run_session(request, project_id=c.id, apply=True, confirmation=runner.CONFIRM)
    assert (held['status'], held['step'], held['steps_done']) == ('founder_needed', 'qa', 0)
    for bad in ({'hours': 0}, {'hours': 25}, {'max_steps': 0}, {'interval': 1}):
        with pytest.raises(ValueError):
            runner.run_session(request, project_id=c.id, **bad)


def test_runner_never_repeats_blindly_when_answers_are_lost_or_wrong():
    project = str(uuid4())
    base = {'kind': runner.KIND, 'step': 'run', 'stage': 'discovery', 'task_id': 't',
            'progressed': False, 'done': False, 'needs_founder': False, 'message': 'm'}

    def session(replies, **options):
        posts, pauses = [], []

        def request(method, path, body=None):
            if method == 'GET':
                return ({'roles': ['founder']} if path.endswith('/me')
                        else {'id': project, 'plan_status': 'active'})
            posts.append(path)
            reply = replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return reply
        ticks = iter(range(0, 10**6, 10))
        report = runner.run_session(
            request, project_id=project, apply=True, confirmation=runner.CONFIRM,
            pause=pauses.append, clock=lambda: next(ticks), **options)
        return report, posts, pauses

    lost, posts, pauses = session([URLError('down'), TimeoutError(), OSError()])
    assert lost['status'] == 'server_not_answering' and len(posts) == 3 and len(pauses) == 2
    # A lost answer is followed by a fresh state read, which may simply be "running".
    waited, posts, _ = session([TimeoutError(), {**base, 'step': 'running'},
                                {**base, 'done': True, 'step': 'done'}])
    assert waited['status'] == 'project_done' and waited['steps_done'] == 0
    with pytest.raises(PermissionError):
        session([{**base, 'kind': 'something_else'}])
    with pytest.raises(PermissionError):
        session([{**base, 'progressed': 'yes'}])
    # A refusal or server error stops at once; it is never retried as a "lost answer".
    for refusal in (HTTPError('http://127.0.0.1', 500, 'error', None, None),
                    PermissionError('refused')):
        with pytest.raises(type(refusal)):
            session([refusal, {**base, 'done': True}])
    expired, posts, _ = session([runner.SessionExpired()])
    assert expired['status'] == 'session_expired' and len(posts) == 1
    twice, _, _ = session([runner.SessionExpired(), runner.SessionExpired()], relogin=lambda: None)
    assert twice['status'] == 'session_expired'
    unclear, posts, _ = session([{**base, 'step': 'qa'}]*3)
    assert (unclear['status'], unclear['step'], len(posts)) == ('founder_needed', 'qa', 3)
    timed, posts, _ = session([{**base, 'step': 'running'}]*400, hours=1)
    assert (timed['status'], timed['limit']) == ('limit_reached', 'time')
    not_founder = lambda method, path, body=None: {'roles': ['reviewer']}  # noqa: E731
    with pytest.raises(PermissionError):
        runner.run_session(not_founder, project_id=project)
