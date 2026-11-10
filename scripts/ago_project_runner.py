"""Founder-started local runner: keeps ONE approved AGO project moving without a browser.

PROJ-006 / ACC-152. The Founder starts this process on his own PC, signs in,
and it repeatedly asks the local AGO server to do the next governed step of
one project (POST /v1/agents/projects/<id>/advance). The SERVER chooses and
performs every step under the Founder's real signed session - approvals by the
AI hierarchy, self-check, run, independent AI QA, next stage, recovery - so
every existing check (revoked session, company rules, emergency stop, work
calendar, credits) still applies to every single step.

It stops by itself when the project is done, when the server says the Founder
is needed, when its time or step limit is reached, or on Ctrl+C. It never
starts at boot, never talks to anything but localhost, never stores the
password or token on disk, and never replays a run: a step whose answer was
lost is not repeated blindly - the next request reads the recorded state.
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

CONFIRM = "ADVANCE_PROJECT_UNTIL_FOUNDER_NEEDED"
KIND = "ago_project_advance_v1"
MAX_LOST_ANSWERS = 3      # consecutive requests without a readable answer
MAX_UNCLEAR_QA = 3        # consecutive QA attempts without a recorded verdict


class SessionExpired(Exception):
    """The server no longer accepts the session token."""


def checked(reply) -> dict:
    """Accept only the exact, typed answer of the advance operation."""
    if (not isinstance(reply, dict) or reply.get("kind") != KIND
            or type(reply.get("progressed")) is not bool
            or type(reply.get("needs_founder")) is not bool
            or type(reply.get("done")) is not bool
            or not isinstance(reply.get("step"), str)
            or not isinstance(reply.get("message"), str)):
        raise PermissionError("Unrecognized advance answer; stopping")
    return reply


def run_session(request, *, project_id: str, apply: bool = False, confirmation=None,
                hours: int = 2, max_steps: int = 60, interval: int = 20,
                relogin=None, report=None, clock=None, pause=None) -> dict:
    """One bounded Founder-authorized session for one project."""
    if str(UUID(project_id)) != project_id:
        raise ValueError("Canonical project UUID required")
    if (type(hours) is not int or not 1 <= hours <= 24
            or type(max_steps) is not int or not 1 <= max_steps <= 500
            or type(interval) is not int or not 5 <= interval <= 300):
        raise ValueError("Session bounds invalid")
    if apply and confirmation != CONFIRM:
        raise PermissionError("Explicit Founder confirmation required")
    if not apply and confirmation is not None:
        raise PermissionError("Read-only preview cannot grant execution permission")
    me = request("GET", "/v1/console/me")
    if not isinstance(me, dict) or "founder" not in me.get("roles", []):
        raise PermissionError("Current Founder login required")
    project = request("GET", "/v1/organization/company/projects/" + project_id)
    if (not isinstance(project, dict) or project.get("id") != project_id
            or project.get("plan_status") != "active"):
        raise PermissionError("A signed, active Founder project is required")
    summary = {"qa_passed_stages": project.get("qa_passed_stages"),
               "stage_count": project.get("stage_count"),
               "project_health": project.get("project_health")}
    if not apply:
        return {"status": "read_only_preview", **summary, "steps_done": 0,
                "service_started_at_boot": False}
    clock, pause = clock or time.monotonic, pause or time.sleep
    report = report or (lambda line: None)
    path = "/v1/agents/projects/" + project_id + "/advance"
    end = clock() + hours * 3600
    steps, requests, lost, unclear, renewed = 0, 0, 0, 0, False

    def result(status, **extra):
        return {"status": status, "steps_done": steps, "requests": requests,
                "automatic_replay": False, "service_started_at_boot": False, **extra}

    while clock() < end and steps < max_steps:
        requests += 1
        try:
            answer = request("POST", path, {})
        except SessionExpired:
            # One renewal per expiry; a second refusal in a row stops the session.
            if relogin is None or renewed:
                return result("session_expired")
            relogin()
            renewed = True
            continue
        except (HTTPError, PermissionError):
            raise  # the server refused or failed: stop, never treat it as a lost answer
        except (TimeoutError, URLError, OSError):
            # The answer was lost, not necessarily the step. Nothing is repeated
            # blindly: the next request makes the server read its recorded state.
            lost += 1
            if lost >= MAX_LOST_ANSWERS:
                return result("server_not_answering")
            pause(min(interval, max(0, end - clock())))
            continue
        reply = checked(answer)
        lost, renewed = 0, False
        report({"step": reply["step"], "stage": reply.get("stage"),
                "progressed": reply["progressed"], "message": reply["message"]})
        if reply["done"]:
            return result("project_done", message=reply["message"])
        if reply["needs_founder"]:
            return result("founder_needed", step=reply["step"], stage=reply.get("stage"),
                          message=reply["message"])
        if reply["progressed"]:
            steps += 1
            unclear = 0
            continue
        if reply["step"] == "qa" and not reply.get("scheduled"):
            unclear += 1
            if unclear >= MAX_UNCLEAR_QA:
                return result("founder_needed", step="qa", stage=reply.get("stage"),
                              message="AI QA gave no usable verdict "
                                      + str(MAX_UNCLEAR_QA) + " times in a row.")
        pause(min(interval, max(0, end - clock())))
    return result("limit_reached", limit="steps" if steps >= max_steps else "time")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-url", default="http://127.0.0.1:8000")
    parser.add_argument("--project-id", required=True, help="Exact Founder project UUID")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm")
    parser.add_argument("--hours", type=int, default=2)
    parser.add_argument("--max-steps", type=int, default=60)
    parser.add_argument("--interval-seconds", type=int, default=20)
    args = parser.parse_args(argv)
    try:
        base = local_url(args.local_url)
        if args.apply and args.confirm != CONFIRM:
            raise PermissionError("Explicit Founder confirmation required")
        tenant = input("AGO organization ID: ").strip()
        email = input("Founder email: ").strip()
        secret = {"password": getpass.getpass("Founder password (hidden): ")}
        session = {"token": founder_login(base, tenant, email, secret["password"])}

        def relogin():
            session["token"] = founder_login(base, tenant, email, secret["password"])

        def request(method, path, body=None):
            data = json.dumps(body).encode("utf-8") if method == "POST" else None
            req = Request(base + path, data=data, method=method, headers={
                "Authorization": "Bearer " + session["token"],
                "Accept": "application/json", "Content-Type": "application/json"})
            try:
                # One advance may contain a full seven-role local model run.
                with urlopen(req, timeout=600 if method == "POST" else 15) as response:
                    return json.load(response)
            except HTTPError as exc:
                if exc.code == 401:
                    raise SessionExpired() from None
                raise

        report = run_session(
            request, project_id=args.project_id, apply=args.apply, confirmation=args.confirm,
            hours=args.hours, max_steps=args.max_steps, interval=args.interval_seconds,
            relogin=relogin if args.apply else None,
            report=lambda line: print(json.dumps(line, sort_keys=True), flush=True))
    except KeyboardInterrupt:
        print(json.dumps({"status": "stopped_by_founder", "automatic_replay": False}))
        return 130
    except SessionExpired:
        print(json.dumps({"status": "session_expired", "automatic_replay": False}))
        return 2
    except HTTPError as exc:
        # Never print the private HTTP body, authorization header or founder brief.
        print(json.dumps({"status": "stopped", "http_status": exc.code,
                          "automatic_replay": False}))
        return 2
    except (ValueError, PermissionError, OSError, EOFError, TypeError, RuntimeError) as exc:
        print(json.dumps({"status": "stopped", "error_type": type(exc).__name__,
                          "automatic_replay": False}))
        return 2
    finally:
        try:
            secret["password"] = ""
        except NameError:
            pass
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] in ("read_only_preview", "project_done", "founder_needed",
                                     "limit_reached") else 2


if __name__ == "__main__":
    raise SystemExit(main())
