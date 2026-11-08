"""Founder-started, localhost-only, bounded runner for approved AGO offline queue.

Never starts at boot or as a hidden web background job. Supports only the
existing signed and independently approved internal:brief queue, using the
server's owner-scoped offline-claim and exact-lease /run API. It never grants
new permissions, creates approvals, hires staff, releases software, sends paid
API calls or retries a task after an unknown outcome.
"""
from __future__ import annotations

import argparse
import getpass
import json
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID

from local_approved_agent_batch import (
    CONFIRM, DurableAttemptJournal, founder_login, local_url,
)

QUEUE="/v1/operations/enterprise/work-queue"
OFFLINE=QUEUE+"/offline-claim"


def uid(raw):
    if type(raw) is not str or str(UUID(raw))!=raw:
        raise ValueError("Canonical queue/task/lease UUID required")
    return raw


def inspection(request):
    rows=request("GET",QUEUE)
    if not isinstance(rows,list) or len(rows)>100:
        raise PermissionError("Invalid or truncated-looking queue")
    seen=set()
    for r in rows:
        if not isinstance(r,dict):
            raise PermissionError("Untrusted queue row")
        ident=uid(r.get("id"))
        uid(r.get("task_id"))
        if ident in seen or type(r.get("requires_reconciliation")) is not bool:
            raise PermissionError("Duplicate or unverifiable queue state")
        seen.add(ident)
        if r.get("lease_state") not in (None,"leased","released","reconciled"):
            raise PermissionError("Unrecognized lease state")
    return rows


def candidates(rows):
    return [r for r in rows if r.get("task_action")=="internal:brief"
            and r.get("task_status")=="waiting_approval"
            and r.get("lease_state") in (None,"released")
            and r.get("requires_reconciliation") is False]


def verify_claim(reply,rows):
    if not isinstance(reply,dict) or reply.get("executed") is not False:
        raise PermissionError("Untrusted server lease")
    if reply.get("queue_id") is None:
        if reply.get("reason")!="no_safe_approved_task":
            raise PermissionError("Unexpected empty lease")
        return None
    if (reply.get("manual_authorized_execution_required") is not True
            or reply.get("replay_of_side_effects") is not False):
        raise PermissionError("Missing no-replay lease guarantees")
    q,t,l=(uid(reply.get(n)) for n in ("queue_id","task_id","lease_id"))
    if len([r for r in candidates(rows) if r["id"]==q and r["task_id"]==t])!=1:
        raise PermissionError("Lease mismatches fresh approved offline queue")
    return q,t,l


def verify_run(reply,q,t):
    if not isinstance(reply,dict):
        return False
    run=reply.get("run")
    try:
        return (
            reply.get("queue_id")==q
            and reply.get("executed") is True
            and reply.get("external_effects") is False
            and reply.get("independent_qa_required") is True
            and isinstance(run,dict)
            and run.get("task_id")==t
            and run.get("status")=="completed"
            and run.get("delivery_status")=="completed"
            and bool(uid(run.get("id")))
        )
    except (ValueError,TypeError):
        return False


def run_session(request, *, apply=False, confirmation=None, journal=None,
                minutes=5, max_tasks=3, interval=15, lease_seconds=600,
                clock=None, pause=None):
    """One bounded founder-approved session; no background scheduling or replay.

    The journal fsync must succeed BEFORE the single network execution POST.
    On any error the caller must stop; the server retains uncertain leases
    until explicitly reconciled by the original authorized claimant.
    """
    if (type(minutes) is not int or not 1<=minutes<=60
            or type(max_tasks) is not int or not 1<=max_tasks<=10
            or type(interval) is not int or not 10<=interval<=120
            or type(lease_seconds) is not int or not 300<=lease_seconds<=1800):
        raise ValueError("Owner session bounds invalid")
    if apply and (confirmation!=CONFIRM or journal is None):
        raise PermissionError("Founder confirmation and durable journal required")
    if not apply and confirmation is not None:
        raise PermissionError("Read-only preview cannot grant execution permission")

    principal=request("GET","/v1/console/me")
    if (not isinstance(principal,dict) or
            "founder" not in principal.get("roles",[])):
        raise PermissionError("Current Founder login required")
    rows=inspection(request)
    if not apply:
        return {"status":"read_only_preview","queue_count":len(rows),
                "candidate_ids":[x["id"] for x in candidates(rows)],
                "reconciliation_ids":[x["id"] for x in rows
                                      if x["requires_reconciliation"]],
                "tasks_executed":0,"service_started":False,
                "automatic_replay":False}
    clock=clock or time.monotonic
    pause=pause or time.sleep
    end=clock()+minutes*60
    completed=[]
    polls=0
    while clock()<end and len(completed)<max_tasks:
        rows=inspection(request)
        ready=candidates(rows)
        polls+=1
        earlier=[r["task_id"] for r in ready if journal.has_claim(r["task_id"])]
        if earlier:
            return {"status":"reconciliation_required",
                    "previous_attempt_task_ids":earlier,
                    "completed_task_ids":completed,
                    "automatic_replay":False}
        if ready:
            claim=request("POST",OFFLINE,{"lease_seconds":lease_seconds})
            lease=verify_claim(claim,rows)
            if lease is not None:
                q,task,lease_id=lease
                # Exclusive durable receipt is committed BEFORE task POST.
                if not journal.claim(task):
                    return {"status":"reconciliation_required",
                            "previous_attempt_task_ids":[task],
                            "completed_task_ids":completed,
                            "automatic_replay":False}
                result=request("POST",QUEUE+"/"+q+"/run",{"lease_id":lease_id})
                if not verify_run(result,q,task):
                    raise RuntimeError("Unconfirmed or blocked task; manual review required")
                completed.append(task)
                continue
        remaining=end-clock()
        if remaining>0:
            pause(min(interval,remaining))
    return {"status":"bounded_session_completed",
            "completed_task_ids":completed,
            "tasks_executed":len(completed),
            "poll_count":polls,"automatic_replay":False,
            "independent_qa_required":True,
            "external_actions_authorized":False,
            "service_started_at_boot":False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-url",default="http://127.0.0.1:8000")
    parser.add_argument("--login",action="store_true")
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--confirm")
    parser.add_argument("--minutes",type=int,default=5)
    parser.add_argument("--max-tasks",type=int,default=3)
    parser.add_argument("--interval-seconds",type=int,default=15)
    parser.add_argument("--lease-seconds",type=int,default=600)
    parser.add_argument("--attempt-journal")
    args=parser.parse_args(argv)
    try:
        base=local_url(args.local_url)
        if args.apply and args.confirm!=CONFIRM:
            raise PermissionError("Explicit Founder confirmation required")
        if not args.apply and args.confirm is not None:
            raise PermissionError("Preview must remain read-only")
        if args.login:
            tenant=input("AGO organization ID: ").strip()
            email=input("Founder email: ").strip()
            password=getpass.getpass("Founder password (hidden): ")
            token=founder_login(base,tenant,email,password)
            del password
        else:
            token=getpass.getpass("Founder AGO token (hidden): ").strip()
        if not 1<=len(token)<=4096 or any(x in token for x in "\r\n"):
            raise PermissionError("Invalid authenticated session")
        def request(method,path,body=None):
            data=json.dumps(body).encode("utf-8") if method=="POST" else None
            req=Request(base+path,data=data,method=method,headers={
                "Authorization":"Bearer "+token,
                "Accept":"application/json","Content-Type":"application/json",
            })
            timeout=120 if method=="POST" and path.endswith("/run") else 15
            with urlopen(req,timeout=timeout) as response:
                return json.load(response)
        journal=(DurableAttemptJournal(
            args.attempt_journal or Path.home()/".ago"/"approved_attempts"
        ) if args.apply else None)
        report=run_session(request,apply=args.apply,confirmation=args.confirm,
            journal=journal,minutes=args.minutes,max_tasks=args.max_tasks,
            interval=args.interval_seconds,lease_seconds=args.lease_seconds)
    except KeyboardInterrupt:
        print(json.dumps({"status":"stopped_by_founder","automatic_replay":False}))
        return 130
    except HTTPError as exc:
        # Never print the private HTTP body, authorization header or founder brief.
        print(json.dumps({"status":"stopped_without_retry",
                          "http_status":exc.code,"automatic_replay":False}))
        return 2
    except (ValueError,PermissionError,OSError,EOFError,TypeError,RuntimeError) as exc:
        print(json.dumps({"status":"stopped_without_retry",
                          "error_type":type(exc).__name__,"automatic_replay":False}))
        return 2
    print(json.dumps(report,sort_keys=True))
    return 0 if report["status"] in ("read_only_preview","bounded_session_completed") else 2


if __name__=="__main__":
    raise SystemExit(main())
