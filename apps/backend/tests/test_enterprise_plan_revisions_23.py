"""Section 23: review-first revisions cannot rewrite parent/child or task evidence."""
from datetime import datetime, timedelta, timezone

from test_m7_http_postgres import case as case, decide, post


def _create(client, founder, reviewer, *, parent=None, horizon="lifetime",
            start=None, end=None, budget="200"):
    now = datetime.now(timezone.utc)
    first = post(client, "/v1/operations/enterprise/plans/approval", founder)
    decide(client, reviewer, first["approval_id"])
    value = {
        "plan_id": first["plan_id"], "approval_id": first["approval_id"],
        "parent_id": parent, "horizon": horizon,
        "title": horizon + " reviewed plan",
        "starts_at": (start or now - timedelta(days=3)).isoformat(),
        "ends_at": (end or now + timedelta(days=500)).isoformat(),
        "budget_ceiling": budget, "evidence_ref": "strategy:human-reviewed",
    }
    return post(client, "/v1/operations/enterprise/plans", founder, value)


def _revision(client, founder, plan_id, *, base=1, title="Revised goal",
              start=None, end=None, budget="100"):
    now = datetime.now(timezone.utc)
    url = f"/v1/operations/enterprise/plans/{plan_id}/revisions"
    payload = {
        "base_revision": base, "title": title,
        "starts_at": (start or now - timedelta(days=2)).isoformat(),
        "ends_at": (end or now + timedelta(days=400)).isoformat(),
        "budget_ceiling": budget, "evidence_ref": "qa:reviewed-task-rollup",
        "rationale": "Reallocate after reviewed QA, preserving task approvals",
    }
    review = post(client, url + "/approval", founder, payload)
    return url, review, payload


def test_horizon_plan_revision_two_person_review_and_immutable_original(case):
    client, headers, context = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    original = _create(client, founder, reviewer)
    root_id = original["id"]
    path, pending, proposed = _revision(client, founder, root_id)
    apply_path = path + "/" + pending["intent_id"] + "/apply"
    token = {"approval_id": pending["approval_id"]}
    assert pending["review_payload"]["title"] == proposed["title"]
    post(client, apply_path, founder, token, expected=403)
    decide(client, reviewer, pending["approval_id"])
    done = post(client, apply_path, founder, token)
    assert done["revision"] == 2 and not done["automatically_authorizes_tasks"]
    assert post(client, apply_path, founder, token)["idempotent"]
    revisions = client.get(path, headers=founder).json()
    assert len(revisions) == 1
    assert revisions[0]["title"] == "Revised goal"
    live = client.get("/v1/operations/enterprise/plans", headers=founder).json()
    item = next(x for x in live if x["id"] == root_id)
    assert item["revision"] == 2 and item["title"] == "Revised goal"
    saved = context["db"].execute(
        "SELECT title,revision FROM ago_horizon_plans WHERE tenant_id=%s AND id=%s",
        (context["tenant"], root_id),
    ).fetchone()
    assert saved["revision"] == 1 and saved["title"] != "Revised goal"
    assert client.get(path).status_code == 401


def test_plan_revision_cannot_invalidate_approved_child_window(case):
    client, headers, _ = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    now = datetime.now(timezone.utc)
    start, end = now - timedelta(days=5), now + timedelta(days=500)
    parent = _create(client, founder, reviewer, start=start, end=end)
    _create(client, founder, reviewer, parent=parent["id"], horizon="five_year",
            start=now - timedelta(days=2), end=now + timedelta(days=350),
            budget="120")
    path, pending, _ = _revision(
        client, founder, parent["id"],
        start=now, end=now + timedelta(days=200), budget="100",
    )
    decide(client, reviewer, pending["approval_id"])
    post(client, path + "/" + pending["intent_id"] + "/apply",
         founder, {"approval_id": pending["approval_id"]}, expected=403)
    live = client.get("/v1/operations/enterprise/plans", headers=founder).json()
    assert next(x for x in live if x["id"] == parent["id"])["revision"] == 1


def test_plan_revision_rejects_stale_review_after_other_revision(case):
    client, headers, _ = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    plan_id = _create(client, founder, reviewer)["id"]
    path, first, _ = _revision(client, founder, plan_id, title="Revision One")
    _, stale, _ = _revision(client, founder, plan_id, title="Stale Proposal")
    decide(client, reviewer, first["approval_id"])
    post(client, path + "/" + first["intent_id"] + "/apply",
         founder, {"approval_id": first["approval_id"]})
    decide(client, reviewer, stale["approval_id"])
    post(client, path + "/" + stale["intent_id"] + "/apply",
         founder, {"approval_id": stale["approval_id"]}, expected=403)
