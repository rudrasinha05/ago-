"""Actual local PostgreSQL ACL: document-specific access never follows project role alone."""
from uuid import uuid4

from test_m7_http_postgres import case as case, post

BASE="/v1/organization/company"
PROFILE="/v1/organization/company/employees/"


def new_project(client,founder,label):
    return post(client,BASE+"/projects/start",founder,{
        "brief":label+" — a confidential internal founder project with auditable deliverables",
        "operation_key":str(uuid4())})


def create(client,founder,project,title,classification="founder_only"):
    return post(client,BASE+"/projects/"+project["id"]+"/documents",founder,{
        "title":title,"body":"Private founder document details for "+title,
        "classification":classification})


def test_explicit_document_acl_revocation_and_revision(case):
    client,headers,info=case
    f,r=headers["founder"],headers["reviewer"]
    project=new_project(client,f,"Unshared internal research")
    private=create(client,f,project,"Founder-only strategic budget")
    restricted=create(client,f,project,"Restricted project scope","project_restricted")
    assert private["classification"]=="founder_only"
    assert client.get(BASE+"/documents/"+private["id"],headers=r).status_code==403
    assert client.get(BASE+"/documents/"+restricted["id"],headers=r).status_code==403
    assert client.get(BASE+"/projects/"+project["id"]+"/documents",headers=r).json()==[]
    denied=post(client,BASE+"/documents/"+restricted["id"]+"/permissions",f,{
        "grantee_id":info["reviewer_id"],"event":"grant",
        "rationale":"Proposed document access for reviewer"},expected=403)
    assert denied is not None
    # Approve the real human as a project manager BEFORE new intake is created.
    role=client.put(PROFILE+str(info["reviewer_id"])+"/role",headers=f,json={
        "role_title":"Project Manager",
        "core_responsibilities":"Independent project management and scoped project records",
        "extra_responsibilities":""})
    assert role.status_code==200,role.text
    assigned=new_project(client,f,"Need-to-know reviewed engineering")
    assert assigned["accountable_manager_id"]==str(info["reviewer_id"])
    doc=create(client,f,assigned,"Engineering design","project_restricted")
    other=create(client,f,assigned,"Other unrelated design","project_restricted")
    founders=create(client,f,assigned,"Founder trade secrets")
    assert client.get(BASE+"/documents/"+doc["id"],headers=r).status_code==403
    assert client.get(BASE+"/projects/"+assigned["id"]+"/documents",headers=r).json()==[]
    post(client,BASE+"/documents/"+founders["id"]+"/permissions",f,{
        "grantee_id":info["reviewer_id"],"event":"grant","rationale":"Must never share founder secrets"
    },expected=403)
    grant=post(client,BASE+"/documents/"+doc["id"]+"/permissions",f,{
        "grantee_id":info["reviewer_id"],"event":"grant",
        "rationale":"Authorized project manager needs this exact engineering design"})
    assert grant["effective"] is True
    visible=client.get(BASE+"/projects/"+assigned["id"]+"/documents",headers=r)
    assert visible.status_code==200,visible.text
    assert [x["id"] for x in visible.json()]==[doc["id"]]
    opened=client.get(BASE+"/documents/"+doc["id"],headers=r)
    assert opened.status_code==200,opened.text
    assert opened.json()["revision"]==1
    assert "Private founder" in opened.json()["body"]
    assert client.get(BASE+"/documents/"+other["id"],headers=r).status_code==403
    assert client.post(BASE+"/documents/"+doc["id"]+"/revisions",headers=r,
                       json={"body":"Forbidden nonfounder revision"}).status_code==403
    revised=post(client,BASE+"/documents/"+doc["id"]+"/revisions",f,{
        "body":"Updated founder approved engineering requirements"})
    assert revised["revision"]==2
    assert client.get(BASE+"/documents/"+doc["id"],headers=r).json()["body"]==(
        "Updated founder approved engineering requirements"
    )
    history=client.get(BASE+"/documents/"+doc["id"]+"/audit",headers=f)
    assert history.status_code==200
    assert any(row["action"]=="read" for row in history.json())
    assert all("body" not in row for row in history.json())
    assert client.get(BASE+"/documents/"+doc["id"]+"/audit",headers=r).status_code==403
    revoke=post(client,BASE+"/documents/"+doc["id"]+"/permissions",f,{
        "grantee_id":info["reviewer_id"],"event":"revoke",
        "rationale":"Project manager no longer requires this exact document"})
    assert revoke["effective"] is False
    assert client.get(BASE+"/documents/"+doc["id"],headers=r).status_code==403
    assert client.get(BASE+"/projects/"+assigned["id"]+"/documents",headers=r).json()==[]
    assert client.get(BASE+"/documents/"+doc["id"],headers=f).status_code==200
    assert info["db"].execute("""
        SELECT COUNT(*) AS n FROM ago_company_document_acl_events
        WHERE tenant_id=%s AND document_id=%s
    """,(info["tenant"],doc["id"])).fetchone()["n"]==2


def test_vault_rejects_bad_identity_cross_project_and_implicit_powers(case):
    client,headers,info=case
    f,r=headers["founder"],headers["reviewer"]
    project=new_project(client,f,"Founder unreleased confidential portfolio")
    doc=create(client,f,project,"Unreleased invention map","project_restricted")
    invalid=post(client,BASE+"/documents/"+doc["id"]+"/permissions",f,{
        "grantee_id":str(uuid4()),"event":"grant",
        "rationale":"Attempt to assign this document to an unknown employee"
    },expected=403)
    assert invalid is not None
    post(client,BASE+"/projects/"+project["id"]+"/documents",r,{
        "title":"Unauthorized","body":"Should not be recorded"},expected=403)
    assert client.get(BASE+"/documents/"+doc["id"]).status_code==401
    assert client.get(BASE+"/documents/"+str(uuid4()),headers=r).status_code==404
    assert all("body" not in item for item in client.get(
        BASE+"/projects/"+project["id"]+"/documents",headers=f).json())
    assert client.get(BASE+"/documents/"+doc["id"],headers=f).json()["classification"]==(
        "project_restricted"
    )
