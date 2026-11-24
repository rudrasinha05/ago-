"""Exercise revision ownership, storage, Docker dispatch and replay over signed HTTP."""
from uuid import uuid4

import pytest

from test_m7_http_postgres import case as case
from test_stage_candidate_tests import PASS, company as company, steps_until


def test_founder_edits_tests_and_replays_one_attempt(company, case, monkeypatch):
    import ago.stage_progression as service
    from ago.company_engineering import run_candidate_tests

    monkeypatch.setattr(service, "run_candidate_tests", lambda value, **kw:
                        run_candidate_tests(value, runner=company.docker, **kw))
    client, headers, _ = case
    response, _ = steps_until(company, "implementation", "run")
    task = response["task_id"]
    path = f"/v1/agents/projects/{company.id}/tasks/{task}/workspace"
    assert client.get(path, headers=headers["reviewer"]).status_code == 403
    original = client.get(path, headers=company.founder)
    assert original.status_code == 200, original.text
    initial = original.json()
    assert initial["revision"] == 0
    files = initial["files"]
    files[0]["content"] += "\n# founder edit\n"
    edit = {"run_id": initial["run_id"], "expected_revision": 0, "files": files}
    revised = client.put(path, headers=company.founder, json=edit)
    assert revised.status_code == 200, revised.text
    current = revised.json()
    assert current["revision"] == 1
    assert current["original_sha256"] == initial["candidate_sha256"]
    assert client.put(path, headers=company.founder, json=edit).status_code == 409
    request = {key: current[key] for key in ("candidate_sha256", "revision", "run_id")}
    request["attempt_id"] = str(uuid4())
    company.docker.outcomes = [PASS]
    for _ in range(2):
        result = client.post(path+"/tests", headers=company.founder, json=request)
        assert result.status_code == 200, result.text
        assert result.json()["receipt"]["candidate_sha256"] == current["candidate_sha256"]
    history = client.get(path+"/tests", headers=company.founder).json()["attempts"]
    assert len(history) == 1 and history[0]["revision"] == 1
    assert history[0]["receipt"]["tests_passed"] is True
    with pytest.raises(Exception, match="immutable"):
        with company.db.transaction():
            company.db.execute("DELETE FROM ago_workspace_test_runs WHERE attempt_id=%s",
                               (request["attempt_id"],))


def test_live_workspace_terminal_uses_offline_container(company):
    from ago.company_engineering import test_runner_available as has_image

    if not has_image():
        pytest.skip("Requires locally preloaded python:3.11-slim and Docker")
    response, _ = steps_until(company, "implementation", "run")
    path = f"/v1/agents/projects/{company.id}/tasks/{response['task_id']}/workspace"
    current = company.client.get(path, headers=company.founder).json()
    files = current["files"]
    source = next(f for f in files if f["path"].startswith("src/"))
    source["content"] += "\nprint('workspace output', flush=True)\n"
    current = company.client.put(path, headers=company.founder, json={
        "run_id": current["run_id"], "expected_revision": current["revision"],
        "files": files}).json()
    request = {k: current[k] for k in ("run_id", "revision", "candidate_sha256")}
    request.update(entry=source["path"], attempt_id=str(uuid4()))
    response = company.client.post(path+"/terminal", headers=company.founder, json=request)
    assert response.status_code == 200, response.text
    assert response.json()["exit_code"] == 0
    assert "workspace output" in response.json()["output"]
