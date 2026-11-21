"""QA-002 / QA-003: AGO runs the implementation stage's generated tests itself.

Before this, the AI engineer's code was only syntax-checked; AI QA and the Board
then failed every attempt with "tests are not executed" and the project could
never leave the implementation stage. Real signed sessions and PostgreSQL; the
builder, the QA model and the container runner are injected fakes.
"""
import json
import subprocess

import pytest

import ago.api_agents as api_agents
import ago.stage_progression as stage_progression
from ago.company_engineering import (
    assert_documented, failure_summary, receipt_text, reviewed_candidate, run_candidate_tests,
)
from test_m7_http_postgres import case as case, post
from test_stage_progression import STAGES, Company, formatted_draft

SOURCE = "def add(a, b):\n    return a + b\n"
TEST = ("import unittest\nfrom src.calc import add\n\n"
        "class T(unittest.TestCase):\n    def test_add(self):\n"
        "        self.assertEqual(add(2, 3), 5)\n")
DOCS = "# Calc\nadd(a, b) returns the sum of two numbers.\n"


def candidate():
    return assert_documented(reviewed_candidate(json.dumps({"files": [
        {"path": "src/calc.py", "content": SOURCE},
        {"path": "tests/test_calc.py", "content": TEST},
        {"path": "docs/calc.md", "content": DOCS},
    ], "acceptance_checks": ["add works"]})))


class Docker:
    """Fake `docker`: image presence and the outcome of each test container."""

    def __init__(self, outcomes, image=True):
        self.outcomes, self.image, self.commands = list(outcomes), image, []

    def __call__(self, command, **kwargs):
        self.commands.append(command)
        if command[:3] == ["docker", "image", "inspect"]:
            return subprocess.CompletedProcess(command, 0 if self.image else 1, "", "")
        if command[:2] == ["docker", "rm"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        outcome = self.outcomes.pop(0)
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(command, kwargs.get("timeout"))
        return subprocess.CompletedProcess(command, *outcome)


PASS = (0, "AGO_UNITTEST_CASES=1\n", "test_add ... ok\nRan 1 test in 0.001s\nOK\n")
FAIL = (1, "AGO_UNITTEST_CASES=1\n",
        "FAIL: test_add (test_calc.T.test_add)\n  File \"/work/tests/test_calc.py\", line 6\n"
        "AssertionError: -1 != 5\n\x1b[31mRan 1 test in 0.001s\nFAILED (failures=1)\n")


# -- the runner itself (no database) ----------------------------------------

def test_container_is_offline_read_only_unprivileged_and_never_pulls():
    docker = Docker([PASS])
    receipt = run_candidate_tests(candidate(), runner=docker)
    assert receipt["status"] == "passed" and receipt["tests_executed"] is True
    assert receipt["unittest_cases"] == 1
    command = docker.commands[-1]
    for flag in ("--network", "none", "--read-only", "--cap-drop=ALL", "--pull=never",
                 "--user=65534:65534", "--memory=256m", "--pids-limit=64"):
        assert flag in command
    assert any(part.endswith(",dst=/work,readonly") for part in command)


def test_failing_tests_return_the_bounded_real_error_without_control_codes():
    receipt = run_candidate_tests(candidate(), runner=Docker([FAIL]))
    assert receipt["status"] == "failed" and receipt["tests_passed"] is False
    assert receipt["failure_category"] == "assertion_failure"
    assert "AssertionError: -1 != 5" in receipt["failure_summary"]
    assert "FAIL: test_add" in receipt["failure_summary"]
    assert "\x1b" not in receipt["failure_summary"] and "/work/" not in receipt["failure_summary"]
    assert "tests FAILED" in receipt_text(receipt)
    assert len(failure_summary("x\n" * 50 + "AssertionError: " + "y" * 5000)) <= 700


def test_zero_tests_timeouts_and_missing_docker_never_count_as_passed():
    none = run_candidate_tests(candidate(), runner=Docker([(4, "AGO_UNITTEST_CASES=0\n", "")]))
    assert none["status"] == "failed" and none["failure_category"] == "tests_not_discovered"
    slow = run_candidate_tests(candidate(), runner=Docker(["timeout"]))
    assert slow["status"] == "timeout" and slow["tests_passed"] is False
    missing = run_candidate_tests(candidate(), runner=Docker([], image=False))
    assert missing["status"] == "runner_unavailable" and missing["tests_executed"] is False


def test_implementation_candidate_must_include_documentation():
    bare = reviewed_candidate(json.dumps({"files": [
        {"path": "src/calc.py", "content": SOURCE},
        {"path": "tests/test_calc.py", "content": TEST}], "acceptance_checks": ["add"]}))
    with pytest.raises(ValueError, match="docs"):
        assert_documented(bare)


# -- the workflow (PostgreSQL) ----------------------------------------------

@pytest.fixture
def company(case, monkeypatch):
    c = Company(case, monkeypatch)
    c.docker = Docker([])

    def handler(task):
        c.seen.append(dict(task.project_context))
        result = {'kind': 'local_company_governed_handoff', 'handoffs': [
            {'role': 'employee', 'employee_id': task.assignee_id, 'draft': formatted_draft(task.project_context.get('stage'))}]}
        if task.project_context.get('stage') == 'implementation':
            result['engineering_candidate'] = candidate()
            result['engineering_candidate_status'] = 'syntax_reviewed'
        return result

    monkeypatch.setattr(api_agents, 'optional_model_handlers',
                        lambda *a, **k: {'internal:brief': handler})
    real = stage_progression.run_candidate_tests
    monkeypatch.setattr(stage_progression, 'test_runner_available',
                        lambda runner=None: c.docker.image)
    monkeypatch.setattr(stage_progression, 'run_candidate_tests',
                        lambda value, runner=None: real(value, runner=c.docker))
    c.advance = '/v1/agents/projects/'+c.id+'/advance'
    return c


def steps_until(c, stage, kind, limit=40):
    taken = []
    for _ in range(limit):
        reply = post(c.client, c.advance, c.founder)
        taken.append((reply['stage'], reply['step']))
        if (reply['stage'], reply['step']) == (stage, kind):
            return reply, taken
    raise AssertionError(taken)


def receipts(c):
    return c.db.execute(
        "SELECT status,unittest_cases,failure_category,failure_summary"
        " FROM ago_stage_candidate_tests WHERE tenant_id=%s ORDER BY created_at",
        (c.tenant,)).fetchall()


def test_ago_runs_the_tests_before_qa_and_the_project_finishes(company):
    c = company
    c.docker.outcomes = [PASS]
    taken = []
    for _ in range(40):
        reply = post(c.client, c.advance, c.founder)
        if reply['done']:
            break
        assert reply['progressed'] is True and reply['needs_founder'] is False, reply
        taken.append((reply['stage'], reply['step']))
    expected = []
    for s in STAGES:
        expected += [(s, 'request'), (s, 'approve'), (s, 'run')]
        expected += [(s, 'qa')] * (2 if s == 'implementation' else 1)
    # The implementation stage gets ONE extra step: AGO's isolated test run.
    assert taken == expected
    [receipt] = receipts(c)
    assert receipt['status'] == 'passed' and receipt['unittest_cases'] == 1
    implementation_qa = next(p for p in c.qa_prompts if 'AGO ISOLATED TEST RECEIPT:' in p)
    assert 'were EXECUTED by AGO' in implementation_qa and 'ALL PASSED' in implementation_qa
    # Live 2026-11-18: quality QA failed six times for "no test cases or test
    # report". Quality and release now see AGO's record of the executed tests.
    quality_qa = next(p for p in c.qa_prompts if 'Stage: quality' in p)
    assert 'AGO TEST EVIDENCE' in quality_qa and 'test_add' in quality_qa
    assert '1 test(s) EXECUTED by AGO in offline Docker, ALL PASSED: test_add' in quality_qa
    contexts = {ctx.get('stage'): ctx for ctx in c.seen}
    assert 'test_add' in contexts['quality']['test_evidence']
    assert contexts['release']['test_evidence'] and not contexts['architecture'].get('test_evidence')
    assert post(c.client, c.advance, c.founder)['done'] is True


def test_failing_tests_send_the_real_error_back_to_the_developer(company):
    c = company
    c.docker.outcomes = [FAIL, PASS]
    c.qa_answer = 'FINDINGS:\n- looks fine\nQA_VERDICT: PASS'   # QA model would pass it
    reply, _ = steps_until(c, 'implementation', 'qa')            # the test step
    assert reply['test_status'] == 'failed' and 'AssertionError: -1 != 5' in reply['message']
    reply = post(c.client, c.advance, c.founder)                 # AI QA
    assert reply['qa_verdict'] == 'fail', reply                   # AGO rule overrides PASS
    evidence = c.db.execute(
        "SELECT q.evidence FROM ago_task_reviews q JOIN ago_governed_tasks t"
        " ON t.tenant_id=q.tenant_id AND t.id=q.task_id WHERE q.tenant_id=%s"
        " AND q.verdict='fail'", (c.tenant,)).fetchone()['evidence']
    assert 'tests FAILED' in evidence and 'AssertionError: -1 != 5' in evidence
    assert evidence.count('QA_VERDICT') == 1 and 'QA_VERDICT: FAIL' in evidence
    # The AI manager already created the rework; the developer sees the error.
    for _ in range(6):
        reply = post(c.client, c.advance, c.founder)
        if reply['step'] == 'run' and reply['stage'] == 'implementation':
            break
    assert 'AssertionError: -1 != 5' in c.seen[-1].get('recovery_feedback', '')
    reply, _ = steps_until(c, 'implementation', 'qa')
    assert reply['test_status'] == 'passed'
    assert [r['status'] for r in receipts(c)] == ['failed', 'passed']


def test_missing_docker_waits_without_failing_the_work_or_calling_the_founder(company):
    c = company
    c.docker.image = False
    reply, _ = steps_until(c, 'implementation', 'qa')
    assert reply['progressed'] is False and reply['needs_founder'] is False
    assert reply['followup']['code'] == 'test_runner_unavailable'
    assert reply['followup']['status'] == 'scheduled'
    assert receipts(c) == []          # nothing ran, nothing to replay or count
    # While the wait is scheduled the server does not hammer Docker.
    again = post(c.client, c.advance, c.founder)
    assert again['progressed'] is False and again['needs_founder'] is False


def test_receipts_are_immutable_and_only_for_completed_runs(company):
    c = company
    c.docker.outcomes = [PASS]
    steps_until(c, 'implementation', 'qa')
    with pytest.raises(Exception, match='immutable'):
        with c.db.transaction():
            c.db.execute("UPDATE ago_stage_candidate_tests SET status='failed'"
                         " WHERE tenant_id=%s", (c.tenant,))
    with pytest.raises(Exception, match='immutable'):
        with c.db.transaction():
            c.db.execute("DELETE FROM ago_stage_candidate_tests WHERE tenant_id=%s", (c.tenant,))


def test_a_source_file_that_imports_itself_is_sent_back_before_docker():
    """Live 2026-11-18: src/admission_flow.py line 3 was
    `from src.admission_flow import AdmissionFlow` -> circular import in Docker.
    The static check now names it, so the developer fixes it in the same run."""
    from ago.company_engineering import assert_discoverable_unittest
    for line in ("from src.calc import add\n", "import src.calc\n", "from calc import add\n"):
        bad = json.dumps({"files": [
            {"path": "src/calc.py", "content": line + SOURCE},
            {"path": "tests/test_calc.py", "content": TEST},
            {"path": "docs/calc.md", "content": DOCS}], "acceptance_checks": ["add"]})
        with pytest.raises(ValueError, match="imports itself"):
            assert_discoverable_unittest(reviewed_candidate(bad))
    assert assert_discoverable_unittest(candidate())["candidate_sha256"]


def test_a_stopped_ollama_makes_the_run_wait_without_spending_an_attempt(company, monkeypatch):
    """2026-11-18: with Ollama down every run failed as model_unreachable and used
    up the six automatic attempts. Now the run waits; nothing fails."""
    c = company
    monkeypatch.setattr(api_agents, 'local_model_unavailable', lambda: 'Ollama is down.')
    reply, _ = steps_until(c, 'discovery', 'run')
    assert reply['progressed'] is False and reply['needs_founder'] is False
    assert reply['followup']['code'] == 'model_runner_unavailable'
    assert reply['followup']['status'] == 'scheduled'
    assert c.seen == []                                   # no work ran
    assert c.db.execute("SELECT count(*) AS n FROM ago_agent_runs WHERE tenant_id=%s",
                        (c.tenant,)).fetchone()['n'] == 0


def test_ollama_probe_reads_only_the_installed_model_list():
    import io
    from ago.model_provider import OllamaLocalTextProvider

    def opener(listing):
        def open_(request, timeout):
            assert request.get_method() == 'GET' and request.full_url.endswith('/api/tags')
            if listing is None:
                raise OSError('connection refused')
            return io.BytesIO(json.dumps({'models': listing}).encode())
        return open_

    def provider(listing):
        return OllamaLocalTextProvider(model='qwen2.5-coder:3b', opener=opener(listing))
    assert provider([{'name': 'qwen2.5-coder:3b'}]).reachable() is True
    assert provider([{'name': 'qwen2.5:3b'}]).reachable() is False
    assert provider(None).reachable() is False


def test_a_solved_blocker_is_closed_when_the_stage_moves_on(company):
    """Old 'blocked' notes stayed open after the work had moved on, so the Founder
    kept seeing problems that were already solved."""
    c = company
    stale = stage_progression.StageProgression(c.db).route_followup(
        tenant_id=c.tenant, founder_id=c.info['founder_id'], project_id=c.id,
        stage='discovery', code='stage_not_staffed', feedback='old problem',
        owner_kind='ceo', blocked=True)
    assert stale['status'] == 'blocked'
    reply = post(c.client, c.advance, c.founder)
    assert (reply['stage'], reply['progressed']) == ('discovery', True)
    assert c.db.execute("SELECT status FROM ago_project_followups WHERE tenant_id=%s AND id=%s",
                        (c.tenant, stale['id'])).fetchone()['status'] == 'resolved'


def test_quality_without_its_labelled_lines_fails_with_the_exact_missing_labels(company):
    """Live 2026-11-21: QA failed quality six times as 'incomplete, not detailed'.
    Now the worker gets a fixed format and a missing line is named exactly."""
    c = company
    c.docker.outcomes = [PASS]
    real = api_agents.optional_model_handlers

    def partial(*a, **k):
        handler = real(*a, **k)['internal:brief']

        def run(task):
            result = handler(task)
            if task.project_context.get('stage') == 'quality':
                result['handoffs'][0]['draft'] = 'QA PLAN: smoke test\nTEST CASES: test_add'
            return result
        return {'internal:brief': run}
    api_agents.optional_model_handlers = partial
    try:
        reply, _ = steps_until(c, 'quality', 'qa', limit=60)
    finally:
        api_agents.optional_model_handlers = real
    assert reply['qa_verdict'] == 'fail'
    evidence = c.db.execute(
        "SELECT q.evidence FROM ago_task_reviews q WHERE q.tenant_id=%s AND q.verdict='fail'",
        (c.tenant,)).fetchone()['evidence']
    assert 'missing these labelled lines: TEST REPORT, ACCEPTANCE MAP, RELEASE BLOCKERS' in evidence
    quality_qa = next(p for p in c.qa_prompts if 'Stage: quality' in p)
    assert 'FORMAT CHECK' in quality_qa and 'ACCEPTANCE MAP' in quality_qa


def test_the_quality_worker_is_told_the_format_and_keeps_it_in_the_stored_draft():
    from ago.company_engineering import missing_stage_labels, stage_format_rule
    rule = stage_format_rule('quality')
    assert all(label + ':' in rule for label in
               ('QA PLAN', 'TEST CASES', 'TEST REPORT', 'ACCEPTANCE MAP', 'RELEASE BLOCKERS'))
    assert stage_format_rule('architecture') == ''
    assert missing_stage_labels('release', 'release package: a\nPR TITLE: b') == [
        'PR DESCRIPTION', 'RELEASE NOTES', 'RECOMMENDATION']
