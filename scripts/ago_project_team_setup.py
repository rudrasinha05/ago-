"""Founder-controlled AGO seven-role workforce bootstrap (NOT task execution).

Read-only preview by default. At most two distinct AI identities are created,
using authenticated localhost AGO APIs. Existing occupied Board seats and old
founder projects/tasks are never changed. Executive manager remains Board CEO.
"""
from __future__ import annotations

import argparse
import getpass
import json
from uuid import UUID
from urllib.error import HTTPError, URLError

from local_approved_agent_batch import founder_login, local_url
from ago_company_setup import fetch

CONFIRM = "CREATE_SEPARATE_AGO_PROJECT_TEAM"
PM = ("AGO AI Project Manager", "AI Project Manager (PM)",
      "Own project-specific execution, deadlines, worker coordination, acceptance criteria and blocker escalation to AGO AI CEO.",
      "Must report to CEO. Never approve task dispatch, modify Founder scope, pay, release, or act as independent QA.")
WORKER = ("AGO AI Discovery Analyst", "AI Discovery Analyst",
          "Analyze Founder project brief, research factual requirements, document risks, proposed architecture and measurable acceptance.",
          "Must report to assigned AI Project Manager. No autonomous network/GitHub writes; all outputs require review.")


def uid(value):
    return str(UUID(str(value)))


def verified_roster(departments, gov):
    if not isinstance(departments, list) or not isinstance(gov, dict):
        raise PermissionError("Founder company records unavailable")
    people = {uid(e["id"]): e for e in gov.get("employees", [])}
    board = {b["seat"]:uid(b["employee_id"]) for b in gov.get("board", [])}
    if len(board) != 5 or len(set(board.values())) != 5:
        raise PermissionError("Five distinct Board appointments required before PM staffing")
    ceo_id=board.get("Strategy & Vision")
    ceo=people.get(ceo_id)
    if not ceo or ceo.get("kind") != "ai":
        raise PermissionError("Actual appointed AI CEO identity required")
    if not any(uid(d["id"])==uid(ceo["department_id"]) for d in departments):
        raise PermissionError("CEO department unavailable in authenticated roster")
    return people, board, ceo


def preview(departments, governance, *, create_missing=False):
    people,board,ceo=verified_roster(departments,governance)
    taken=set(board.values())
    roles=[]
    for name,title,core,extra in (PM,WORKER):
        matching=[e for e in people.values() if e.get("kind")=="ai" and e.get("name")==name]
        if len(matching)>1:
            raise PermissionError("Duplicate canonical workforce role; manual Founder resolution required")
        person=matching[0] if matching else None
        if person and uid(person["id"]) in taken:
            raise PermissionError("Project PM/worker must be distinct from all Board members")
        if person and str(person.get("role_title") or "").strip() not in ("",title,"Not assigned"):
            raise PermissionError("Canonical employee already has a different meaningful role")
        roles.append({
            "name":name,"title":title,"id":uid(person["id"]) if person else None,
            "kind":person.get("kind") if person else "ai",
            "action":"reuse" if person else ("create" if create_missing else "vacant"),
            "manager_before":uid(person["manager_id"]) if person and person.get("manager_id") else None,
            "department_id":uid(person["department_id"]) if person else uid(ceo["department_id"]),
            "responsibilities":core,"authority_limits":extra,
        })
    if roles[0]["id"] and roles[0]["id"]==roles[1]["id"]:
        raise PermissionError("Project PM and worker must be distinct real AI identities")
    pm_previous=roles[0]["manager_before"]
    if pm_previous and pm_previous!=uid(ceo["id"]):
        raise PermissionError("Existing PM reports to another manager; no automatic reassignment")
    # Existing employee under another manager is not automatically moved.
    worker_previous=roles[1]["manager_before"]
    if worker_previous and (roles[0]["id"] is None or worker_previous!=roles[0]["id"]):
        raise PermissionError("Existing analyst has a different manager; manual review required")
    return {
        "kind":"ago_founder_project_team_preview_v1","mode":"read_only",
        "ceo_id":uid(ceo["id"]),"ceo_name":ceo["name"],
        "ceo_department_id":uid(ceo["department_id"]),
        "roles":roles,
        "board_unchanged":True,"old_project_unchanged":True,
        "database_modified":False,"tasks_executed":0,
        "new_ai_employees":sum(r["action"]=="create" for r in roles),
        "vacant_roles":[r["name"] for r in roles if r["action"]=="vacant"],
    }


def apply(request, proposal):
    if proposal["vacant_roles"]:
        raise PermissionError("Use --create-missing for absent AI identity after review")
    departments=request("GET","/v1/organization/departments")
    gov=request("GET","/v1/organization/company/governance")
    fresh=preview(departments,gov,create_missing=proposal["new_ai_employees"]>0)
    if fresh!=proposal:
        raise PermissionError("Leadership/workforce changed since preview; no write")
    active_ceo=proposal["ceo_id"]
    output=[]
    assigned={}
    for i,row in enumerate(proposal["roles"]):
        boss=active_ceo if i==0 else assigned[PM[0]]
        emp_id=row["id"]
        if row["action"]=="create":
            hired=request("POST","/v1/organization/employees",{
                "department_id":proposal["ceo_department_id"],
                "name":row["name"],"kind":"ai","manager_id":boss,
            })
            emp_id=uid(hired["id"])
            output.append({"role":row["name"],"action":"created"})
        elif row["manager_before"] is None:
            request("PUT","/v1/organization/company/employees/"+emp_id+"/manager",{
                "manager_id":boss,
            })
            output.append({"role":row["name"],"action":"existing_manager_linked"})
        else:
            output.append({"role":row["name"],"action":"existing_identity_preserved"})
        assigned[row["name"]]=emp_id
        request("PUT","/v1/organization/company/employees/"+emp_id+"/role",{
            "role_title":row["title"],
            "core_responsibilities":row["responsibilities"],
            "extra_responsibilities":row["authority_limits"],
        })
    latest=request("GET","/v1/organization/company/governance")
    by_id={uid(e["id"]):e for e in latest.get("employees",[])}
    pm=by_id.get(assigned[PM[0]],{})
    worker=by_id.get(assigned[WORKER[0]],{})
    ok=(pm.get("kind")=="ai" and worker.get("kind")=="ai"
        and uid(pm.get("manager_id"))==active_ceo
        and uid(worker.get("manager_id"))==assigned[PM[0]]
        and len({*assigned.values(),active_ceo})==3)
    return {
        "kind":"ago_founder_project_team_result_v1",
        "verified":ok,"status":"verified" if ok else "verification_incomplete",
        "ceo_id":active_ceo,"project_pm_id":assigned[PM[0]],
        "worker_id":assigned[WORKER[0]],"actions":output,
        "existing_project_leads_modified":False,"tasks_executed":0,
        "old_task_replayed":False,
        "next_step":"Create a NEW Founder-reviewed project/task after verifying active CEO->PM->worker hierarchy",
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-url",default="http://127.0.0.1:8000")
    parser.add_argument("--create-missing",action="store_true")
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args(argv)
    stage="initialize"
    try:
        base=local_url(args.local_url)
        stage="founder_login"
        tenant=input("AGO organization ID: ").strip()
        email=input("Founder work email: ").strip()
        password=getpass.getpass("Founder password (hidden): ")
        token=founder_login(base,tenant,email,password)
        del password
        req=lambda method,path,body=None:fetch(base,token,method,path,body)
        stage="verify_founder"
        me=req("GET","/v1/console/me")
        if "founder" not in me.get("roles",[]) or "organization:manage" not in me.get("permissions",[]):
            raise PermissionError("Founder company manage authority required")
        stage="read_roster"
        ds=req("GET","/v1/organization/departments")
        gov=req("GET","/v1/organization/company/governance")
        stage="read_only_preview"
        p=preview(ds,gov,create_missing=args.create_missing)
        print(json.dumps(p,sort_keys=True,indent=2))
        if not args.apply:
            return 0
        if p["vacant_roles"]:
            raise PermissionError("Explicit --create-missing required")
        stage="founder_confirmation"
        if input("To create/assign these two distinct AI staff, type "+CONFIRM+": ").strip()!=CONFIRM:
            print(json.dumps({"status":"cancelled","database_modified":False}))
            return 2
        stage="apply_governed_staffing"
        result=apply(req,p)
        print(json.dumps(result,indent=2,sort_keys=True))
        return 0 if result["verified"] else 2
    except (PermissionError,HTTPError,ValueError,KeyError,TypeError,RuntimeError,
            OSError,URLError,EOFError,KeyboardInterrupt) as exc:
        print(json.dumps({
            "status":"stopped_no_automatic_retry",
            "stage":stage,
            "error_type":type(exc).__name__,
            "http_status":exc.code if isinstance(exc,HTTPError) else None,
            "database_modified_by_preview":False if stage!="apply_governed_staffing" else None,
            "write_may_have_been_attempted":stage=="apply_governed_staffing",
            "old_task_replayed":False,
            "next_step":"Inspect live role records before any repeat; do not reset the old project",
        },sort_keys=True))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
