"""Founder-reviewed localhost-only AGO AI leadership staffing and Board setup.

READ-ONLY preview by default. --apply requires typed consent. Uses authenticated
existing AGO company REST APIs, never direct DB, model execution or GitHub.
AI staff records are software identities, not qualified real-life executives.
"""
from __future__ import annotations

import argparse
import getpass
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID

from local_approved_agent_batch import founder_login, local_url

CONFIRM = "APPOINT_AGO_AI_LEADERSHIP"
DEPARTMENT = "AGO AI Leadership"
# code, full title, actual existing Board seat (if any), duties, hard limitations
ROLES = (
    ("CEO", "Chief Executive Officer (CEO)", "Strategy & Vision",
     "Own Founder-approved project delivery, enterprise priorities, project accountability, executive escalation and interdepartmental coordination.",
     "Founder retains final human authority. No scope changes, payment approvals, self-review or publishing without governance."),
    ("CTO", "Chief Technology Officer (CTO)", "Technology Oversight",
     "Own software architecture, engineering quality, Android/web/backend systems, technical plans, GitHub proposals and integration reliability.",
     "Demand real reproducible tests; no unapproved GitHub write, deployment or bypass of security review."),
    ("CFO", "Chief Financial Officer (CFO)", "Finance & Budget",
     "Own project cost estimates, virtual AI usage budgets, forecasting, financial analysis and operational resource proposals.",
     "No payments, bank access, purchasing or fabricated financial results."),
    ("CISO", "Chief Information Security Officer (CISO)", "Risk & Compliance",
     "Own cybersecurity, incident risk, secrets protection, data privacy, threat models and security release risk review.",
     "No independent privilege grants or silent waivers of security controls."),
    ("CQO", "Chief Quality Officer (CQO)", "Quality & Release",
     "Own quality assurance, automated test plans, defects, accessibility, release criteria and evidence-backed acceptance.",
     "Cannot impersonate independent human QA or call untested code release-ready."),
    ("COO", "Chief Operating Officer (COO)", None,
     "Manage daily execution, schedules, cross-team delivery dependencies and operating workload.",
     "Coordinate only projects within Founder-approved scope."),
    ("CAIO", "Chief AI Officer (CAIO)", None,
     "Manage AI agent design, local LLM evaluation, prompt quality, orchestration and model safety.",
     "No inference claim without an actual persisted inference receipt."),
    ("CPO", "Chief Product Officer (CPO)", None,
     "Own product requirements, user needs, roadmap, UX, prioritization and feature acceptance.",
     "Freeze approved scope; defer new features to explicit backlog review."),
    ("CMO", "Chief Marketing Officer (CMO)", None,
     "Own branding, market research, positioning, acquisition experiments and growth proposals.",
     "Do not invent customer, revenue or market evidence."),
    ("CHRO", "Chief Human Resources Officer (CHRO)", None,
     "Own role catalog, AI workforce allocation, skill gaps, manager hierarchy and onboarding plans.",
     "AI identities are not verified human staff; no RBAC grants by title."),
    ("CRO_RND", "Chief Research Officer (Research)", None,
     "Own research methods, literature, experiment design, ML benchmarks and reproducible innovation.",
     "Distinguish simulated, proposed, tested and peer-reviewed results."),
    ("CLO", "Chief Legal Officer (CLO)", None,
     "Organize legal/IP/privacy risk checklists, draft reviews and licensed-professional escalations.",
     "Never represent itself as a licensed legal professional."),
)
CODES = {r[0] for r in ROLES}
SEATS = {r[2]: r[0] for r in ROLES if r[2]}


def uid(value):
    return str(UUID(str(value)))


def fetch(base, token, method, endpoint, body=None, *, opener=urlopen):
    if not endpoint.startswith("/") or "//" in endpoint:
        raise ValueError("Invalid endpoint")
    data = None if body is None else json.dumps(body).encode("utf8")
    req = Request(base + endpoint, data=data, method=method, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/json",
        **({"Content-Type": "application/json"} if data is not None else {}),
    })
    with opener(req, timeout=20) as response:
        return json.load(response)


def read(request):
    departments = request("GET", "/v1/organization/departments")
    governance = request("GET", "/v1/organization/company/governance")
    if (not isinstance(departments, list) or not isinstance(governance, dict)
            or not isinstance(governance.get("employees"), list)
            or not isinstance(governance.get("board"), list)):
        raise TypeError("Current authenticated company data unavailable")
    return departments, governance


def manual_assignments(filename):
    if filename is None:
        return {}
    with open(filename, encoding="utf8") as file:
        data = json.load(file)
    if not isinstance(data, dict) or not set(data).issubset(CODES):
        raise ValueError("Assignments must map known role codes to existing AI UUIDs")
    return {key: uid(value) for key, value in data.items()}


def plan(departments, governance, *, scope="core", create_missing=False, mapping=None):
    """Pure/read-only deterministic selection. Never guess an unrelated AI officer."""
    if scope not in ("core", "full"):
        raise ValueError("Invalid leadership scope")
    mapping = mapping or {}
    if not set(mapping).issubset(CODES):
        raise ValueError("Unknown role in explicit mapping")
    roles = ROLES[:5] if scope == "core" else ROLES
    ai = [e for e in governance["employees"] if e.get("kind") == "ai"]
    people = {uid(e["id"]): e for e in governance["employees"]}
    seats = {b["seat"]: uid(b["employee_id"]) for b in governance["board"]}
    if len(seats) != len(governance["board"]):
        raise PermissionError("Duplicate Board seat rows require manual inspection")
    already = set()
    output = []
    for code, title, seat, duties, limits in roles:
        incumbent = seats.get(seat) if seat else None
        canonical = "AGO AI " + code
        if code in mapping:
            selected = [people.get(uid(mapping[code]))]
            if incumbent and incumbent != uid(mapping[code]):
                raise PermissionError("Occupied Board seat must not be overwritten")
        elif incumbent:
            selected = [people.get(incumbent)]
        else:
            selected = [e for e in ai if
                        e.get("name") == canonical or
                        str(e.get("role_title") or "").casefold() == title.casefold()]
        if len(selected) > 1:
            raise PermissionError("Ambiguous staff for " + code + "; use --assignments")
        person = selected[0] if selected else None
        if person:
            if person.get("kind") != "ai":
                raise PermissionError("Board/role candidate must be a recorded AI identity")
            person_id = uid(person["id"])
            if person_id in already:
                raise PermissionError("One AI employee cannot fill multiple officer roles")
            already.add(person_id)
            current_title = str(person.get("role_title") or "").strip().casefold()
            if current_title and current_title not in ("not assigned", title.casefold()):
                raise PermissionError("Existing staff title conflicts with " + code)
            state = "appointed" if incumbent else "reuse"
        else:
            if incumbent or code in mapping:
                raise PermissionError("Selected Board employee missing from this company")
            person_id = None
            state = "create" if create_missing else "vacant"
        output.append({
            "code": code, "title": title, "board_seat": seat,
            "employee_id": person_id, "name": person.get("name") if person else canonical,
            "action": state, "responsibilities": duties, "authority_limits": limits,
        })
    return {
        "kind": "ago_local_founder_leadership_preview",
        "mode": "read_only", "scope": scope, "roles": output,
        "new_ai_records": sum(x["action"] == "create" for x in output),
        "vacant": [x["code"] for x in output if x["action"] == "vacant"],
        "board_appointed_before": sum(s in seats for s in SEATS),
        "database_modified": False, "tasks_executed": 0,
    }


def apply(request, proposal):
    """Founder-confirmed changes. Stops on any uncertain POST; never auto-retries."""
    if proposal["vacant"]:
        raise PermissionError("Vacancies need explicit --create-missing or --assignments")
    departments, governance = read(request)
    # Fresh replan prevents using stale employee/Board records.
    fresh = plan(departments, governance, scope=proposal["scope"],
                 create_missing=proposal["new_ai_records"] > 0,
                 mapping={x["code"]:x["employee_id"] for x in proposal["roles"]
                          if x["employee_id"]})
    if [(x["code"],x["employee_id"],x["action"]) for x in fresh["roles"]] != [
            (x["code"],x["employee_id"],x["action"]) for x in proposal["roles"]]:
        raise PermissionError("Company changed since preview; inspect and replan")
    dept = next((d for d in departments if d.get("name") == DEPARTMENT), None)
    if proposal["new_ai_records"] and dept is None:
        dept = request("POST", "/v1/organization/departments", {"name":DEPARTMENT})
    dept_id = uid(dept["id"]) if dept else None
    indexed = {uid(e["id"]):e for e in governance["employees"]}
    board = {x["seat"]:uid(x["employee_id"]) for x in governance["board"]}
    assignments = {}
    changes = {"employees_created":[],"profiles_written":[],
               "board_appointed":[],"reporting_set":[],"profiles_preserved":[]}
    for row in proposal["roles"]:
        employee_id = row["employee_id"]
        if row["action"] == "create":
            new = request("POST", "/v1/organization/employees", {
                "department_id":dept_id,"name":row["name"],"kind":"ai",
                "manager_id":None,
            })
            employee_id = uid(new["id"])
            indexed[employee_id] = new
            changes["employees_created"].append(row["code"])
        assignments[row["code"]] = employee_id
        employee = indexed[employee_id]
        if (employee.get("role_title") == row["title"]
                and str(employee.get("core_responsibilities") or "").strip()):
            changes["profiles_preserved"].append(row["code"])
        else:
            request("PUT","/v1/organization/company/employees/" + employee_id + "/role", {
                "role_title":row["title"],
                "core_responsibilities":row["responsibilities"],
                "extra_responsibilities":row["authority_limits"],
            })
            changes["profiles_written"].append(row["code"])
    for row in proposal["roles"]:
        if row["board_seat"] and row["board_seat"] not in board:
            request("POST", "/v1/organization/company/board/appoint", {
                "seat":row["board_seat"],"employee_id":assignments[row["code"]],
            })
            changes["board_appointed"].append(row["code"])
    # No cross-project PM edits or forced reassignment of existing managers.
    for row in proposal["roles"][1:]:
        employee_id = assignments[row["code"]]
        if not indexed[employee_id].get("manager_id"):
            request("PUT", "/v1/organization/company/employees/" + employee_id
                    + "/manager", {"manager_id":assignments["CEO"]})
            changes["reporting_set"].append(row["code"])
    _, updated = read(request)
    seats_after = {s["seat"]:uid(s["employee_id"]) for s in updated["board"]}
    indexed_after = {uid(e["id"]):e for e in updated["employees"]}
    ok = all(seats_after.get(seat) == assignments[code]
             for seat,code in SEATS.items())
    ok = ok and len({seats_after.get(seat) for seat in SEATS}) == 5
    ok = ok and all(indexed_after.get(eid,{}).get("kind") == "ai"
                    for eid in assignments.values())
    return {
        "kind":"ago_founder_leadership_result",
        "status":"verified" if ok else "verification_failed",
        "board_verified":ok,"changes":changes,
        "officers_recorded":len(assignments),"tasks_executed":0,
        "original_task_unchanged":True,"github_modified":False,
        "project_pm_worker_verified":False,
        "next_step":"Read-only diagnose-approved-engineering; do not replay original task",
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-url",default="http://127.0.0.1:8000")
    parser.add_argument("--scope",choices=("core","full"),default="core")
    parser.add_argument("--create-missing",action="store_true",
                        help="Create unfilled software AI officer identities after Founder confirmation")
    parser.add_argument("--assignments",help="JSON mapping role code -> existing AI employee UUID")
    parser.add_argument("--apply",action="store_true",
                        help="Prompt for an exact Founder approval after printed preview")
    args=parser.parse_args(argv)
    try:
        base=local_url(args.local_url)
        mapping=manual_assignments(args.assignments)
        tenant=input("AGO organization ID: ").strip()
        email=input("Founder work email: ").strip()
        password=getpass.getpass("Founder password (hidden): ")
        token=founder_login(base,tenant,email,password)
        del password
        request=lambda method,path,body=None:fetch(base,token,method,path,body)
        principal=request("GET","/v1/console/me")
        if ("founder" not in principal.get("roles",[]) or
                "organization:manage" not in principal.get("permissions",[])):
            raise PermissionError("Founder organization:manage required")
        deps, gov=read(request)
        proposal=plan(deps,gov,scope=args.scope,create_missing=args.create_missing,
                      mapping=mapping)
        print(json.dumps(proposal,indent=2,sort_keys=True))
        if not args.apply:
            return 0
        if proposal["vacant"]:
            raise PermissionError("Vacant roles: choose --create-missing or explicit --assignments")
        typed=input("Review officers and duties. Type " + CONFIRM + " to write: ").strip()
        if typed!=CONFIRM:
            print(json.dumps({"status":"cancelled","database_modified":False}))
            return 2
        result=apply(request,proposal)
        print(json.dumps(result,indent=2,sort_keys=True))
        return 0 if result["board_verified"] else 2
    except HTTPError as exc:
        print(json.dumps({"status":"stopped_no_retry","error_type":"HTTPError",
                          "http_status":exc.code,
                          "next_step":"Read latest records; replan before any new write"}))
    except (OSError, ValueError, PermissionError, TypeError, RuntimeError,
            URLError, EOFError, KeyboardInterrupt) as exc:
        print(json.dumps({"status":"stopped_no_retry",
                          "error_type":type(exc).__name__,
                          "next_step":"Inspect Board and employee records; do not blindly retry"}))
    return 2


if __name__=="__main__":
    raise SystemExit(main())
