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
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import UUID

CONFIRM="EXECUTE_APPROVED_INTERNAL_TASKS"


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


def batch(records: list[dict], dispatch, *, limit: int, apply: bool,
          confirm: str | None) -> dict:
    if not 1<=limit<=10:
        raise ValueError("No more than ten approved tasks in a batch")
    if apply and confirm!=CONFIRM:
        raise PermissionError("Founder confirmation required")
    ids=[]
    for task in records:
        if task.get("action")!="internal:brief" or task.get("status")!="waiting_approval":
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


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-url",default="http://127.0.0.1:8000")
    parser.add_argument("--limit",type=int,default=3)
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--confirm")
    args=parser.parse_args(argv)
    try:
        base=local_url(args.local_url)
        if args.apply and args.confirm!=CONFIRM:
            raise PermissionError("Exact founder confirmation required")
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
        with urlopen(req,timeout=15) as response:
            result=json.load(response)
        return result

    try:
        records=request("GET","/v1/organization/company/activity")
        if not isinstance(records,list):
            raise TypeError("Authenticated task activity unavailable")
        result=batch(records,lambda task_id:request(
            "POST","/v1/agents/tasks/"+task_id+"/run"),
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
