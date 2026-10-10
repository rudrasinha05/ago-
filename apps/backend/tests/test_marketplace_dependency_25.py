"""Section 25: verified internal asset dependency graph and safe revocation."""
from uuid import uuid4

from test_enterprise_http_21_27 import department
from test_m7_http_postgres import case as case, decide, post


def _draft(client, founder, dept, name, digest, dependencies=None):
    return post(client, "/v1/operations/enterprise/marketplace", founder, {
        "department_id": dept, "name": name, "kind": "workflow",
        "version": "1.0.0", "license_id": "internal-only",
        "sha256_digest": digest, "manifest": {"dependencies": dependencies or []},
    })


def _publish(client, founder, reviewer, asset_id):
    path = "/v1/operations/enterprise/marketplace/" + asset_id
    approval = post(client, path + "/approval", founder)
    decide(client, reviewer, approval["approval_id"])
    return post(client, path + "/publish", founder)


def test_asset_dependencies_require_immutable_version_digest_and_active_status(case):
    client, headers, _ = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    dept = department(client, founder)
    parent = _draft(client, founder, dept, "Core Library " + uuid4().hex[:8], "a" * 64)
    assert _publish(client, founder, reviewer, parent["id"])["status"] == "published"
    dep = {"asset_id": parent["id"], "version": "1.0.0", "digest": "a" * 64}
    child = _draft(client, founder, dept, "Dependent Workflow " + uuid4().hex[:8],
                   "b" * 64, [dep])
    assert _publish(client, founder, reviewer, child["id"])["status"] == "published"
    child_path = "/v1/operations/enterprise/marketplace/" + child["id"]
    usage = post(client, child_path + "/consume/approval", founder)
    decide(client, reviewer, usage["approval_id"])
    assert post(client, child_path + "/consume", founder, {
        "approval_id": usage["approval_id"], "department_id": dept,
        "evidence_ref": "approved:internal-workflow"})["status"] == "recorded"
    parent_path = "/v1/operations/enterprise/marketplace/" + parent["id"]
    expiry = post(client, parent_path + "/lifecycle/approval", founder,
                  {"target_state": "revoked"})
    decide(client, reviewer, expiry["approval_id"])
    post(client, parent_path + "/lifecycle", founder, {
        "approval_id": expiry["approval_id"], "target_state": "revoked",
        "reason": "Provenance or permission no longer valid"})
    newer_use = post(client, child_path + "/consume/approval", founder)
    decide(client, reviewer, newer_use["approval_id"])
    post(client, child_path + "/consume", founder, {
        "approval_id": newer_use["approval_id"], "department_id": dept,
        "evidence_ref": "should-be-blocked"}, expected=403)


def test_marketplace_refuses_malformed_or_incompatible_dependency(case):
    client, headers, _ = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    dept = department(client, founder)
    base = {"asset_id": str(uuid4()), "version": "1.0.0", "digest": "c" * 64}
    post(client, "/v1/operations/enterprise/marketplace", founder, {
        "department_id": dept, "name": "Invalid Dependencies", "kind": "workflow",
        "version": "1.0.0", "license_id": "internal-only",
        "sha256_digest": "d" * 64,
        "manifest": {"dependencies": [base, base]}}, expected=400)
    item = _draft(client, founder, dept, "Missing Dependency", "e" * 64, [base])
    path = "/v1/operations/enterprise/marketplace/" + item["id"]
    approval = post(client, path + "/approval", founder)
    decide(client, reviewer, approval["approval_id"])
    post(client, path + "/publish", founder, expected=403)
