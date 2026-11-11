"""Founder-started, LOCAL-only Global Chat reply worker (P0).

This companion to ago_project_runner.py handles only AI acknowledgments in
CEO-owned Global Chat orders. It does NOT approve/execute governed tasks,
publish software, or certify QA. It is explicitly started by the Founder,
never at boot; no secret or session token is persisted to disk.

After a real signed session, it polls the persisted work-item queue and calls
POST /v1/organization/company/chat/orders/{message_id}/respond once per
eligible agent. The backend fences duplicate model calls and owns every
tenant, CEO, employee and Founder authorization check. It stops on revocation,
time/step limits, a missing CEO, model unavailability, or Ctrl+C.
"""
from __future__ import annotations

import argparse
import getpass
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID

from local_approved_agent_batch import founder_login, local_url

CONFIRM = "PROCESS_PENDING_GLOBAL_CHAT_AI_REPLIES"
RENEW_INTERVAL_SECONDS = 600   # 10m, comfortably before 15m bearer expiry
MAX_LOST_ANSWERS = 3


class SessionExpired(Exception):
    """Revoked, expired or unavailable Founder authorization."""


def next_pending(orders):
    """Only real pending AI work. Serve oldest orders first; CEO first."""
    if not isinstance(orders, list):
        raise ValueError("Expected an audited Founder order list")
    blocked = []
    for order in sorted(orders, key=lambda item: item.get("message_id", 0)
                        if isinstance(item, dict) else 0):
        if not isinstance(order, dict):
            raise ValueError("Invalid order receipt")
        if order.get("state") == "blocked_no_ceo":
            blocked.append(order.get("message_id"))
            continue
        if order.get("state") != "awaiting_ack":
            continue
        message_id = order.get("message_id")
        ceo = order.get("accountable_ceo_id")
        if type(message_id) is not int or message_id <= 0:
            raise ValueError("Invalid order ID")
        workers = order.get("work_items")
        if not isinstance(workers, list):
            raise ValueError("Work items unavailable")
        pending = [w for w in workers
                   if w.get("assignee_kind") == "ai"
                   and w.get("ack_message_id") is None]
        pending.sort(key=lambda w: (w.get("assignee_id") != ceo,
                                   w.get("assignee_name") or ""))
        for w in pending:
            employee_id = str(UUID(str(w.get("assignee_id"))))
            yield (message_id, employee_id)
    if blocked:
        # The caller decides how to inform the Founder. This generator never
        # fabricates an AI CEO to unblock the order.
        return


def run_session(request, *, apply=False, confirmation=None, hours=4,
                max_replies=100, interval=20, report=None, clock=None, pause=None):
    if (type(hours) is not int or not 1 <= hours <= 8
            or type(max_replies) is not int or not 1 <= max_replies <= 300
            or type(interval) is not int or not 5 <= interval <= 300):
        raise ValueError("Invalid bounded local worker settings")
    if apply and confirmation != CONFIRM:
        raise PermissionError("Explicit Founder authorization required")
    if not apply and confirmation is not None:
        raise PermissionError("Read-only mode may not request permission")
    clock, pause = clock or time.monotonic, pause or time.sleep
    report = report or (lambda _: None)
    me = request("GET", "/v1/console/me")
    if not isinstance(me, dict) or "founder" not in me.get("roles", []):
        raise PermissionError("A signed Founder session is required")
    url = "/v1/organization/company/chat/orders?limit=100"
    initial = request("GET", url)
    items = list(next_pending(initial))
    if not apply:
        return {"status":"read_only_preview","pending_ai_replies":len(items),
                "replies_recorded":0,"automatic_replay":False,
                "started_at_boot":False}
    stop_at = clock() + hours * 3600
    done, requests, lost, no_model = 0, 0, 0, 0
    last_result = None

    def summary(status, **fields):
        return {"status":status,"replies_recorded":done,"requests":requests,
                "automatic_replay":False,"started_at_boot":False,**fields}

    while clock() < stop_at and requests < max_replies:
        try:
            orders = request("GET",url)
            pending = list(next_pending(orders))
        except SessionExpired:
            return summary("session_expired")
        except HTTPError:
            raise  # Explicit refusal/server failure is not an uncertain transport answer.
        except (TimeoutError, URLError, OSError):
            lost += 1
            if lost >= MAX_LOST_ANSWERS:
                return summary("server_unavailable")
            pause(min(interval,max(0,stop_at-clock())))
            continue
        if not pending:
            missing=sum(o.get("state")=="blocked_no_ceo" for o in orders)
            return summary("founder_needed" if missing else
                           "queue_acknowledged_not_executed",
                           pending_ai_replies=0,blocked_without_ceo=missing)
        # A successful queue read does not prove the prior POST completed.
        # Preserve the lost-answer counter until a verified response arrives.
        message_id, employee_id = pending[0]
        requests += 1
        try:
            reply = request("POST",
                "/v1/organization/company/chat/orders/"+str(message_id)+"/respond",
                {"employee_id":employee_id})
        except SessionExpired:
            return summary("session_expired")
        except HTTPError:
            raise  # Never replay rejected requests, including 403 and 429.
        except (TimeoutError, URLError, OSError):
            # The HTTP answer may have been lost AFTER a successful model run.
            # Never infer success or repeat blindly: next iteration re-reads
            # the database. The backend fences an uncertain in-flight claim.
            lost += 1
            if lost >= MAX_LOST_ANSWERS:
                return summary("server_unavailable")
            pause(min(interval,max(0,stop_at-clock())))
            continue
        if not isinstance(reply,dict) or not isinstance(reply.get("status"),str):
            raise PermissionError("Unrecognized AI response; refusing continuation")
        state = reply["status"]
        report({"message_id":message_id,"employee_id":employee_id,
                "status":state})
        last_result = state
        if state == "responded":
            if reply.get("ai_acknowledged") is not True:
                raise PermissionError("False model acknowledgment rejected")
            done += 1
            lost, no_model = 0, 0
            continue
        if state == "already_replied":
            lost, no_model = 0, 0
            continue
        if state in ("local_model_disabled","retry_limit"):
            return summary("founder_needed",cause=state,
                           pending_ai_replies=len(pending))
        if state == "model_unavailable":
            no_model += 1
            if no_model >= 3:
                return summary("local_model_unavailable",
                               pending_ai_replies=len(pending))
        elif state == "already_processing":
            no_model = 0
        else:
            raise PermissionError("Unknown AI response state")
        pause(min(interval,max(0,stop_at-clock())))
    return summary("limit_reached",cause="count" if requests >= max_replies else "time",
                   last_response=last_result)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-url",default="http://127.0.0.1:8000")
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--confirm")
    parser.add_argument("--hours",type=int,default=4)
    parser.add_argument("--max-replies",type=int,default=100)
    parser.add_argument("--interval-seconds",type=int,default=20)
    args=parser.parse_args(argv)
    try:
        base=local_url(args.local_url)
        if args.apply and args.confirm != CONFIRM:
            raise PermissionError("Exact Founder confirmation required")
        tenant=input("AGO organization ID: ").strip()
        email=input("Founder email: ").strip()
        password=getpass.getpass("Founder password (hidden): ")
        token=founder_login(base,tenant,email,password)
        password=""  # Founder secret is not used again after login.
        session={"token":token,"last_renewed":time.monotonic()}

        def request(method,path,body=None):
            if not path.startswith("/") or path.startswith("//"):
                raise PermissionError("Invalid localhost API route")
            if time.monotonic()-session["last_renewed"] >= RENEW_INTERVAL_SECONDS:
                renew=Request(base+"/v1/sessions/renew",data=b"{}",
                    method="POST",headers={
                        "Authorization":"Bearer "+session["token"],
                        "Accept":"application/json","Content-Type":"application/json"})
                try:
                    with urlopen(renew,timeout=20) as response:
                        rotated=json.load(response)
                except HTTPError as exc:
                    if exc.code==401:
                        raise SessionExpired() from None
                    raise
                new_token=rotated.get("access_token") if isinstance(rotated,dict) else None
                if not isinstance(new_token,str) or not new_token:
                    raise PermissionError("Session renewal failed closed")
                session["token"]=new_token
                session["last_renewed"]=time.monotonic()
            req=Request(base+path,method=method,
                data=json.dumps(body).encode("utf-8") if method=="POST" else None,
                headers={"Authorization":"Bearer "+session["token"],
                         "Accept":"application/json",
                         "Content-Type":"application/json"})
            try:
                with urlopen(req,timeout=75 if method=="POST" else 15) as response:
                    return json.load(response)
            except HTTPError as exc:
                if exc.code==401:
                    raise SessionExpired() from None
                raise

        result=run_session(request,apply=args.apply,confirmation=args.confirm,
                           hours=args.hours,max_replies=args.max_replies,
                           interval=args.interval_seconds,
                           report=lambda x:print(json.dumps(x,sort_keys=True),flush=True))
    except KeyboardInterrupt:
        print(json.dumps({"status":"stopped_by_founder","automatic_replay":False}))
        return 130
    except SessionExpired:
        print(json.dumps({"status":"session_expired","automatic_replay":False}))
        return 2
    except HTTPError as exc:
        print(json.dumps({"status":"stopped","http_status":exc.code,
                          "automatic_replay":False}))
        return 2
    except (ValueError,PermissionError,OSError,EOFError,TypeError,RuntimeError) as exc:
        print(json.dumps({"status":"stopped","error_type":type(exc).__name__,
                          "automatic_replay":False}))
        return 2
    finally:
        # No credentials or bearer are printed or written to a file.
        password=""
        try:
            session["token"]=""
        except NameError:
            pass
    print(json.dumps(result,sort_keys=True))
    return 0 if result["status"] in ("read_only_preview",
                                     "queue_acknowledged_not_executed",
                                     "limit_reached","founder_needed") else 2


if __name__=="__main__":
    raise SystemExit(main())
