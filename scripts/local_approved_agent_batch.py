"""Founder-triggered, localhost-only, one-pass approved internal AI task batch.

Default is READ ONLY. No scheduling, startup registration, model calls, cloud,
GitHub writes, replay, recovery loop or automatic publication. The existing
authenticated AGO API independently checks signed identity, approved action,
calendar, strategy, prerequisite QA and per-task execution permissions.
"""
from __future__ import annotations

import argparse
import getpass
import json
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import UUID

CONFIRM="EXECUTE_APPROVED_INTERNAL_TASKS"
READ_TIMEOUT_SECONDS=15
RUN_TIMEOUT_SECONDS=270  # Four bounded Ollama passes can take up to 4 x 60s.
def request_timeout(method: str, endpoint: str) -> int:
    return RUN_TIMEOUT_SECONDS if (method=="POST"
        and endpoint.startswith("/v1/agents/tasks/")
        and endpoint.endswith("/run")) else READ_TIMEOUT_SECONDS



def local_url(base: str) -> str:
    try:
        url=urlsplit(base)
        if (url.scheme!="http" or url.hostname not in ("localhost","127.0.0.1","::1")
                or url.username or url.password or url.query or url.fragment
                or url.path not in ("","/") or url.port is None
                or not 1024<=url.port<=65535):
            raise ValueError("Only a founder-started localhost AGO HTTP endpoint is supported")
    except ValueError as exc:
        raise ValueError("Only a founder-started localhost AGO HTTP endpoint is supported") from exc
    return base.rstrip("/")


def batch(records: list[dict], approvals: list[dict], dispatch, *, limit: int, apply: bool,
          confirm: str | None) -> dict:
    if not 1<=limit<=10:
        raise ValueError("No more than ten approved tasks in a batch")
    if apply and confirm!=CONFIRM:
        raise PermissionError("Founder confirmation required")
    approved = {str(item.get('id')): item for item in approvals
                if item.get('status') == 'approved'}
    ids=[]
    for task in records:
        if task.get("action")!="internal:brief" or task.get("status")!="waiting_approval":
            continue
        receipt=approved.get(str(task.get("approval_id")))
        if not receipt or receipt.get("action")!=task.get("action"):
            continue
        try:
            task_id=str(UUID(str(task["id"])))
        except (ValueError,KeyError,TypeError):
            continue
        if task_id not in ids:
            ids.append(task_id)
        if len(ids)==limit:
            break
    completed=[]
    if apply:
        # No retries: HTTP 502/timeout may follow an external side effect.
        # The authenticated task endpoint holds the security decision.
        for task_id in ids:
            result=dispatch(task_id)
            if result.get("status")!="completed" or result.get("task_id")!=task_id:
                raise RuntimeError("AGO did not confirm an exact completed task")
            completed.append(task_id)
    return {"mode":"founder_approved_single_batch" if apply else "dry_run",
            "eligible_task_ids":ids,"completed_task_ids":completed,
            "external_actions_authorized":False,
            "task_count":len(completed),"next_step":"Independent human QA required"}



def watch(fetch, dispatch, *, minutes: int, max_tasks: int, interval: int,
          confirm: str, clock=None, pause=None) -> dict:
    """Single founder-controlled session: approved internal tasks, one at a time.

    Never replay attempted IDs in the same session even after a timeout or
    unconfirmed outcome. Backend remains the authoritative execution gate.
    """
    if confirm != CONFIRM:
        raise PermissionError("Founder confirmation required")
    if not 1 <= minutes <= 60 or not 1 <= max_tasks <= 10 or not 10 <= interval <= 120:
        raise ValueError("Bounded watch limits invalid")
    clock=clock or time.monotonic
    pause=pause or time.sleep
    started=clock()
    seen=set()
    completed=[]
    polls=0
    while clock()-started < minutes*60 and len(seen)<max_tasks:
        records,approvals=fetch()
        polls+=1
        if not isinstance(records,list) or not isinstance(approvals,list):
            raise TypeError("Authenticated task and approval records are required")
        preview=batch(records,approvals,lambda _:None,limit=10,apply=False,confirm=None)
        next_id=next((v for v in preview["eligible_task_ids"] if v not in seen),None)
        if next_id is not None:
            seen.add(next_id)  # Mark BEFORE I/O: no uncertain-outcome replay.
            result=dispatch(next_id)
            if result.get("status")!="completed" or result.get("task_id")!=next_id:
                raise RuntimeError("Unknown task execution result; reconcile manually")
            completed.append(next_id)
        else:
            remaining=minutes*60-(clock()-started)
            if remaining>0:
                pause(min(interval,remaining))
    return {"mode":"founder_bounded_local_watch","poll_count":polls,
            "attempted_task_count":len(seen),"completed_task_ids":completed,
            "task_count":len(completed),"external_actions_authorized":False,
            "next_step":"Independent human QA required", "scheduled_service":False}

def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-url",default="http://127.0.0.1:8000")
    parser.add_argument("--limit",type=int,default=3)
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--confirm")
    parser.add_argument("--watch-minutes",type=int,default=0,help="0: one pass; 1..60: founder-started bounded polling of approved work")
    parser.add_argument("--interval-seconds",type=int,default=15,help="Watch polling interval: 10..120 seconds")
    args=parser.parse_args(argv)
    try:
        base=local_url(args.local_url)
        if args.apply and args.confirm!=CONFIRM:
            raise PermissionError("Exact founder confirmation required")
        if args.watch_minutes and not args.apply:
            raise PermissionError("Watch mode requires explicit --apply and --confirm")
        if args.watch_minutes<0 or args.watch_minutes>60 or not 10<=args.interval_seconds<=120:
            raise ValueError("Invalid bounded watch limits")
    except (ValueError,PermissionError) as exc:
        parser.error(str(exc))
    # getpass avoids tokens in process args, PowerShell history, stdout or files.
    token=getpass.getpass("Founder AGO local access token (not echoed): ").strip()
    if not token or "\n" in token or "\r" in token or len(token)>4096:
        parser.error("Invalid local founder session token")

    def request(method: str, endpoint: str):
        req=Request(base+endpoint,method=method,
                    headers={"Authorization":"Bearer "+token,
                             "Accept":"application/json"})
        with urlopen(req,timeout=request_timeout(method,endpoint)) as response:
            result=json.load(response)
        return result

    try:
        def fetch():
            return (request("GET","/v1/organization/company/activity"),
                    request("GET","/v1/organization/company/approvals"))
        dispatch=lambda task_id:request("POST","/v1/agents/tasks/"+task_id+"/run")
        if args.watch_minutes:
            result=watch(fetch,dispatch,minutes=args.watch_minutes,
                         max_tasks=args.limit,interval=args.interval_seconds,
                         confirm=args.confirm)
        else:
            records,approvals=fetch()
            if not isinstance(records,list) or not isinstance(approvals,list):
                raise TypeError("Authenticated task/approval evidence unavailable")
            result=batch(records,approvals,dispatch,
                         limit=args.limit,apply=args.apply,confirm=args.confirm)
    except (OSError, ValueError, PermissionError, TypeError, RuntimeError) as exc:
        # Do not print tokens, endpoint messages, project content or traceback.
        print(json.dumps({"status":"stopped_without_retry",
                         "error_type":type(exc).__name__,
                         "automated_replay":False}))
        return 2
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
