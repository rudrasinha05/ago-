"""Provider contract verification without creating repositories or sending messages."""

import pytest
from ago import github_adapter as gh


@pytest.mark.parametrize(
    "name",
    ["../repo", "repo/name", "repo?token=secret", "repo.git", "", ".git", "https://evil.test"],
)
def test_repository_name_rejects_escape(name):
    with pytest.raises(ValueError):
        gh.repository_name(name)


@pytest.mark.parametrize(
    "operation,payload",
    [
        ("delete_repository", {}),
        ("transfer", {}),
        ("create_repository", {"private": False}),
        (
            "commit_files",
            {
                "expected_sha": "a" * 40,
                "message": "x",
                "files": [{"path": "../.env", "content": "secret"}],
            },
        ),
        (
            "commit_files",
            {
                "expected_sha": "a" * 40,
                "message": "x",
                "files": [{"path": ".env", "content": "secret"}],
            },
        ),
        (
            "commit_files",
            {
                "expected_sha": "a" * 40,
                "message": "x",
                "files": [{"path": "a", "content": "1"}, {"path": "a", "content": "2"}],
            },
        ),
        ("create_pull_request", {"expected_sha": "wrong", "title": "Release", "body": "Reviewed"}),
    ],
)
def test_unsafe_github_changes_rejected(operation, payload):
    with pytest.raises(ValueError):
        gh.validate_operation({"operation": operation, "payload": payload})


@pytest.mark.parametrize(
    "operation,payload",
    [
        ("create_repository", {}),
        ("link_repository", {"repository_id": 42, "private": True}),
        ("initialize_develop", {"expected_sha": "a" * 40}),
        ("create_issue", {"title": "Fix", "body": "Evidence"}),
        ("update_issue", {"number": 1, "title": "Fix", "body": "Evidence", "state": "closed"}),
        (
            "commit_files",
            {
                "expected_sha": "a" * 40,
                "message": "Code and docs",
                "files": [{"path": "README.md", "content": "Verified docs"}],
            },
        ),
        (
            "create_pull_request",
            {"expected_sha": "a" * 40, "title": "Release", "body": "Independent QA"},
        ),
    ],
)
def test_exact_private_owner_provider_requests(monkeypatch, operation, payload):
    calls = []

    def request(method, path, body=None):
        calls.append((method, path, body))
        if path == "/user":
            return {"login": gh.OWNER}
        if path == "/user/repos":
            return {
                "id": 42,
                "private": True,
                "html_url": "https://github.com/" + gh.OWNER + "/project",
            }
        if path.endswith("/project"):
            return {
                "id": 42,
                "private": True,
                "owner": {"login": gh.OWNER},
                "default_branch": "main",
                "html_url": "https://github.com/" + gh.OWNER + "/project",
            }
        if "/git/ref" in path:
            return {"object": {"sha": "a" * 40}}
        if path.endswith("/git/commits/" + "a" * 40):
            return {"tree": {"sha": "b" * 40}}
        if path.endswith("/git/trees"):
            return {"sha": "c" * 40}
        if path.endswith("/git/commits"):
            return {"sha": "d" * 40}
        return {"number": 1, "html_url": "https://github.com/" + gh.OWNER + "/project/pull/1"}

    monkeypatch.setattr(gh, "request", request)
    spec = {"operation": operation, "payload": payload}
    gh.validate_operation(spec)
    result = gh.execute(
        {"id": "project-id", "repository": "project", "repository_id": 42, "private": True},
        spec,
        "ago-operation:unique",
    )
    assert result
    assert all(method != "DELETE" for method, _, _ in calls)
    if operation == "create_repository":
        assert calls[-1][2]["private"] is True
    if operation == "commit_files":
        assert calls[-1][2] == {"sha": "d" * 40, "force": False}
    if operation == "create_pull_request":
        assert calls[-1][2]["draft"] is True and calls[-1][2]["head"] == "develop"


def test_connector_disabled_before_network(monkeypatch):
    monkeypatch.delenv("AGO_GITHUB_ENABLED", raising=False)
    with pytest.raises(PermissionError):
        gh.request("GET", "/user")


def test_ref_change_stops_commit_before_writes(monkeypatch):
    calls = []

    def request(method, path, body=None):
        calls.append(method)
        return (
            {"owner": {"login": gh.OWNER}, "private": True, "id": 42}
            if "/git/" not in path
            else {"object": {"sha": "b" * 40}}
        )

    monkeypatch.setattr(gh, "request", request)
    with pytest.raises(PermissionError):
        gh.execute(
            {"repository": "project", "repository_id": 42, "private": True},
            {"operation": "commit_files", "payload": {"expected_sha": "a" * 40}},
            "marker",
        )
    assert calls == ["GET", "GET"]


def test_existing_public_repository_reuse_is_explicit_and_identity_pinned(monkeypatch):
    def public(method, path, body=None):
        return {
            "owner": {"login": gh.OWNER},
            "private": False,
            "id": 42,
            "html_url": "https://github.com/" + gh.OWNER + "/existing",
        }

    monkeypatch.setattr(gh, "request", public)
    operation = {"operation": "link_repository", "payload": {"repository_id": 42, "private": False}}
    gh.validate_operation(operation)
    assert gh.execute({"repository": "existing"}, operation, "marker")["private"] is False
    operation["payload"]["private"] = True
    with pytest.raises(PermissionError):
        gh.execute({"repository": "existing"}, operation, "marker")
    with pytest.raises(PermissionError):
        gh.execute(
            {"repository": "existing", "repository_id": 43, "private": False},
            {"operation": "create_issue", "payload": {"title": "x", "body": "y"}},
            "marker",
        )



def test_required_ci_requires_every_named_pass_and_exact_develop_head(monkeypatch):
    calls = []
    def get(method, path, body=None):
        calls.append((method, path))
        assert method == "GET"
        if path.endswith("/project"):
            return {"owner": {"login": gh.OWNER}, "id": 42, "private": True}
        if path.endswith("/git/ref/heads/develop"):
            return {"object": {"sha": "a" * 40}}
        if "/check-runs" in path:
            return {"total_count": 2, "check_runs": [
                {"name": "Backend QA", "status": "completed", "conclusion": "success"},
                {"name": "Browser QA", "status": "completed", "conclusion": "success"},
            ]}
        if path.endswith("/status"):
            return {"statuses": []}
        raise AssertionError("Unexpected endpoint: " + path)
    monkeypatch.setattr(gh, "request", get)
    project = {"repository": "project", "repository_id": 42, "private": True}
    state = gh.inspect_required_ci(project, expected_sha="a" * 40,
                                   required_checks=("Backend QA", "Browser QA"))
    assert state["ci_verified"] is True
    assert state["release_authorized"] is False
    assert state["merge_authorized"] is False
    assert all(method == "GET" for method, path in calls)
    partial = gh.inspect_required_ci(project, expected_sha="a" * 40,
                                    required_checks=("Backend QA", "Missing security check"))
    assert partial["ci_verified"] is False
    assert partial["missing_checks"] == ["Missing security check"]


def test_ci_gate_denies_stale_sha_malformed_requirements_and_foreign_project(monkeypatch):
    calls = []
    def request(method, path, body=None):
        calls.append(path)
        if path.endswith("/project"):
            return {"owner": {"login": gh.OWNER}, "id": 42, "private": True}
        if path.endswith("/git/ref/heads/develop"):
            return {"object": {"sha": "b" * 40}}
        raise AssertionError("No CI reads allowed for an out-of-date commit")
    monkeypatch.setattr(gh, "request", request)
    p = {"repository": "project", "repository_id": 42, "private": True}
    for checks in ((), ("same", "same"), ("",), tuple(str(i) for i in range(25))):
        with pytest.raises(ValueError):
            gh.inspect_required_ci(p, expected_sha="a" * 40, required_checks=checks)
    with pytest.raises(PermissionError, match="develop HEAD"):
        gh.inspect_required_ci(p, expected_sha="a" * 40, required_checks=("Backend QA",))
    assert not any("/check-runs" in x for x in calls)
    with pytest.raises(PermissionError):
        gh.inspect_required_ci({**p, "repository_id": 99},
                                expected_sha="a" * 40, required_checks=("Backend QA",))


@pytest.mark.parametrize("check_runs,statuses,total,reason", [
    ([{"name": "Backend QA", "status": "in_progress", "conclusion": None}], [], 1, "pending"),
    ([{"name": "Backend QA", "status": "completed", "conclusion": "failure"}], [], 1, "failed"),
    ([{"name": "Backend QA", "status": "completed", "conclusion": "success"},
      {"name": "Backend QA", "status": "completed", "conclusion": "failure"}], [], 2, "duplicate"),
    ([{"name": "Backend QA", "status": "completed", "conclusion": "success"}],
     [{"context": "Backend QA", "state": "failure"}], 1, "conflicting"),
])
def test_ci_gate_blocks_failed_pending_duplicate_or_conflicting_checks(
        monkeypatch, check_runs, statuses, total, reason):
    def get(method, path, body=None):
        if path.endswith("/project"):
            return {"owner": {"login": gh.OWNER}, "id": 42, "private": True}
        if path.endswith("/git/ref/heads/develop"):
            return {"object": {"sha": "a" * 40}}
        if "/check-runs" in path:
            return {"check_runs": check_runs, "total_count": total}
        if path.endswith("/status"):
            return {"statuses": statuses}
        raise AssertionError("Unexpected path")
    monkeypatch.setattr(gh, "request", get)
    actual = gh.inspect_required_ci({"repository": "project", "repository_id": 42,
                                    "private": True}, expected_sha="a" * 40,
                                   required_checks=("Backend QA",))
    assert actual["ci_verified"] is False, reason
    assert actual["blocked_or_ambiguous_checks"] == ["Backend QA"]
    assert actual["release_authorized"] is False


def test_ci_gate_refuses_truncated_evidence(monkeypatch):
    def get(method, path, body=None):
        if path.endswith("/project"):
            return {"owner": {"login": gh.OWNER}, "id": 42, "private": True}
        if path.endswith("/git/ref/heads/develop"):
            return {"object": {"sha": "a" * 40}}
        return {"check_runs": [], "total_count": 101}
    monkeypatch.setattr(gh, "request", get)
    with pytest.raises(PermissionError, match="truncated"):
        gh.inspect_required_ci({"repository": "project", "repository_id": 42,
                                "private": True}, expected_sha="a" * 40,
                               required_checks=("Required QA",))
