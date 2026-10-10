"""Section 25 actual reusable payload storage with immutable digest, no cloud.

Publisher can inspect their draft. Third parties cannot read bytes without
consumption approval. None of these operations executes uploaded content.
"""
import base64
from hashlib import sha256

import pytest

from test_enterprise_http_21_27 import department
from test_m7_http_postgres import case as case, decide, post


def test_verified_asset_payload_upload_publish_and_access(case):
    client, headers, context = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    dept = department(client, founder)
    raw = b'{"template":"reviewed internal planning checklist","version":1}'
    digest = sha256(raw).hexdigest()
    item = post(client, "/v1/operations/enterprise/marketplace", founder, {
        "department_id": dept,
        "name": "Local immutable work template",
        "kind": "template", "version": "1.0.0",
        "license_id": "internal-only", "sha256_digest": digest,
        "manifest": {"payload_required": True, "dependencies": []},
    })
    path = "/v1/operations/enterprise/marketplace/" + item["id"]
    data = {"content_type": "application/json",
            "content_base64": base64.b64encode(raw).decode("ascii")}
    assert client.get(path + "/payload", headers=founder).status_code == 404
    post(client, path + "/payload", founder,
         {**data, "content_base64": base64.b64encode(b"tampered").decode()}, expected=403)
    result = post(client, path + "/payload", founder, data)
    assert result["digest"] == digest and not result["execution_granted"]
    assert result["bytes"] == len(raw)
    assert post(client, path + "/payload", founder, data)["idempotent"] is True
    delivered = client.get(path + "/payload", headers=founder)
    assert delivered.status_code == 200
    assert base64.b64decode(delivered.json()["content_base64"]) == raw
    assert client.get(path + "/payload", headers=reviewer).status_code == 403
    with pytest.raises(Exception, match="append-only"):
        with context["db"].transaction():
            context["db"].execute(
                """UPDATE ago_marketplace_payloads SET payload=%s
                   WHERE tenant_id=%s AND asset_id=%s""",
                (b"forged", context["tenant"], item["id"]),
            )
    review = post(client, path + "/approval", founder)
    decide(client, reviewer, review["approval_id"])
    assert post(client, path + "/publish", founder)["status"] == "published"
    post(client, path + "/payload", founder, data, expected=403)
    assert client.get(path + "/payload").status_code == 401


def test_asset_payload_bad_base64_refused_before_persistence(case):
    client, headers, _ = case
    founder = headers["founder"]
    dept = department(client, founder)
    raw = b"safe reusable template"
    item = post(client, "/v1/operations/enterprise/marketplace", founder, {
        "department_id": dept, "name": "Bounded internal evidence asset",
        "kind": "library", "version": "1.0.0", "license_id": "internal-only",
        "sha256_digest": sha256(raw).hexdigest(),
        "manifest": {"payload_required": True},
    })
    url = "/v1/operations/enterprise/marketplace/" + item["id"] + "/payload"
    post(client, url, founder,
         {"content_type": "text/plain", "content_base64": "%%%bad%"}, expected=400)
    assert client.get(url, headers=founder).status_code == 404
