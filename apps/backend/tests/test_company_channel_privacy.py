"""Confidential company channels must not inherit broad organisation read rights."""
from uuid import uuid4
from test_m7_http_postgres import case as case, post
from test_enterprise_http_21_27 import department, employee

BASE="/v1/organization/company"


def test_private_employee_department_messages_and_notifications_are_scoped(case):
    client, headers, info=case
    founder, outsider=headers["founder"], headers["reviewer"]
    dep=department(client,founder)
    worker=employee(client,founder,dep)
    other=department(client,founder)
    # Grant broad API capabilities but NEVER employee/project membership.
    for perm in ("organization:read","task:read","messages:read",
                 "messages:write","brain:read","agent:read"):
        info["db"].execute("""
            INSERT INTO ago_role_permissions(tenant_id,role,permission)
            VALUES (%s,'reviewer',%s) ON CONFLICT DO NOTHING
        """,(info["tenant"],perm))
    target="employee:"+worker
    secret="Private product owner planning only; not for general staff"
    sent=post(client,BASE+"/chat",founder,{
        "channel":target,"body":secret,"operation_key":str(uuid4())})
    assert sent["body"]==secret
    for channel in (target,"department:"+dep,"department:"+other):
        assert client.get(BASE+"/chat",headers=outsider,
                          params={"channel":channel}).status_code==403
        post(client,BASE+"/chat",outsider,{
            "channel":channel,"body":"Cross-channel attempt",
            "operation_key":str(uuid4())},expected=403)
    timeline=client.get(BASE+"/chat",headers=outsider)
    assert timeline.status_code==200,timeline.text
    assert all(secret not in str(row) for row in timeline.json()["items"])
    post(client,BASE+"/chat",outsider,{
        "channel":"global","body":"Try to quote another employee's secret",
        "reply_to":sent["id"],"operation_key":str(uuid4())},expected=400)
    # Founder continues to see complete authorized company-wide internal feed.
    founder_messages=client.get(BASE+"/chat",headers=founder)
    assert founder_messages.status_code==200
    assert any(row["body"]==secret for row in founder_messages.json()["items"])
    own_events=client.get(BASE+"/notifications",headers=outsider)
    assert own_events.status_code==200,own_events.text
    assert all(x["employee_id"]==info["reviewer_id"]
               for x in own_events.json()["recent"])
    assert worker not in own_events.json()["by_employee"]
    # A reviewer with broad task-read permission must not see an unrelated
    # employee's unlinked task action via the global activity stream.
    task=post(client,"/v1/tasks",founder,{
        "assignee_id":worker,"action":"internal:brief"})
    outsider_activity=client.get(BASE+"/activity",headers=outsider)
    assert outsider_activity.status_code==200,outsider_activity.text
    assert all(str(row["id"])!=task["id"] for row in outsider_activity.json())
    founder_activity=client.get(BASE+"/activity",headers=founder)
    assert any(str(row["id"])==task["id"] for row in founder_activity.json())
    # Agent run packets may include founder brief excerpts; generic agent
    # visibility must not override founder confidentiality.
    assert client.get("/v1/agents/runs",headers=outsider).status_code==403
    assert client.get("/v1/agents/runs",headers=founder).status_code==200
