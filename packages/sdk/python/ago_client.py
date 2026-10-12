"""Typed standard-library AGO v1 integration SDK and durable webhook replay guard."""

from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import time
from collections.abc import Iterator
from typing import TypedDict
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID, uuid4


class TaskSummary(TypedDict):
    id: str
    status: str
    assignee_id: str


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Integration redirects are not followed")


class CompanyAPI:
    def __init__(self, origin: str, token: str, retries: int = 2):
        p = urlsplit(origin)
        if (
            not p.hostname
            or p.username
            or p.password
            or p.query
            or p.fragment
            or p.path not in ("", "/")
            or (
                p.scheme != "https"
                and not (p.scheme == "http" and p.hostname in ("127.0.0.1", "::1"))
            )
        ):
            raise ValueError("HTTPS or loopback origin required")
        self.origin = origin.rstrip("/")
        self.token = token
        self.retries = min(3, max(0, retries))
        self.opener = build_opener(NoRedirect)

    def request(
        self, path: str, *, body: dict | None = None, idempotency_key: str | None = None
    ) -> dict:
        if (
            not path.startswith("/v1/platform/")
            or ".." in path
            or "://" in path
            or any(c in path.split("?")[0] for c in ("%", "\\", "#"))
            or any(ord(c) <= 32 for c in path)
        ):
            raise ValueError("Scoped v1 platform path required")
        headers = {
            "Authorization": "Bearer " + self.token,
            "X-Request-ID": str(uuid4()),
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        req = Request(
            self.origin + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers,
        )
        for attempt in range(self.retries + 1):
            try:
                with self.opener.open(req, timeout=10) as response:
                    content = response.read(1048577)
                    if len(content) > 1048576:
                        raise ValueError("Response exceeds1MiB")
                    return json.loads(content)
            except HTTPError as exc:
                if (
                    attempt >= self.retries
                    or exc.code not in (429, 502, 503, 504)
                    or body is not None
                    and not idempotency_key
                ):
                    raise
                try:
                    delay = float(exc.headers.get("Retry-After", 2**attempt))
                except ValueError:
                    delay = 2**attempt
                time.sleep(min(5, max(0, delay)))
        raise RuntimeError("Retry exhausted")

    def events(self, after: int = 0, limit: int = 100) -> dict:
        return self.request(
            "/v1/platform/events?" + urlencode({"after": after, "limit": limit})
        )

    def tasks(self, after: str | None = None, limit: int = 50) -> dict:
        return self.request(
            "/v1/platform/tasks?"
            + urlencode({"limit": limit, **({"after": after} if after else {})})
        )

    def propose_task(
        self, action: str, assignee_id: str, idempotency_key: str
    ) -> TaskSummary:
        if not idempotency_key:
            raise ValueError("Stable idempotency key required")
        return self.request(
            "/v1/platform/tasks",
            body={"action": action, "assignee_id": assignee_id},
            idempotency_key=idempotency_key,
        )

    def stream(self, after: int = 0) -> Iterator[dict]:
        req = Request(
            self.origin + "/v1/platform/stream?" + urlencode({"after": after}),
            headers={"Authorization": "Bearer " + self.token},
        )
        with self.opener.open(req, timeout=20) as response:
            frame = {}
            size = 0
            for raw in response:
                size += len(raw)
                if size > 262144:
                    raise ValueError("Stream frame too large")
                line = raw.decode().strip()
                if not line:
                    if "data" in frame:
                        yield {
                            "id": int(frame["id"]),
                            "event": frame["event"],
                            "data": json.loads(frame["data"]),
                        }
                    frame = {}
                    size = 0
                elif ":" in line:
                    k, v = line.split(":", 1)
                    frame[k] = v.strip()


class WebhookReceiver:
    """Durable inbox: accept persists bytes; pending survives crashes until acknowledge."""

    def __init__(self, database_path: str):
        self.db = sqlite3.connect(database_path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS received(delivery_id TEXT PRIMARY KEY,received_at INTEGER NOT NULL)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS inbox(delivery_id TEXT PRIMARY KEY, body TEXT NOT NULL, processed INTEGER NOT NULL DEFAULT 0)"
        )
        self.db.commit()

    def pending(self) -> list[dict]:
        return [
            {"delivery_id": row[0], "data": json.loads(row[1])}
            for row in self.db.execute(
                "SELECT delivery_id,body FROM inbox WHERE processed=0 ORDER BY rowid"
            )
        ]

    def acknowledge(self, delivery_id: str) -> None:
        with self.db:
            self.db.execute(
                "UPDATE inbox SET processed=1 WHERE delivery_id=?", (delivery_id,)
            )

    def accept(
        self,
        secret: str,
        timestamp: int,
        delivery_id: str,
        body: bytes,
        signature: str,
        *,
        now: int | None = None,
    ) -> dict:
        current = int(time.time()) if now is None else now
        UUID(delivery_id)
        if (
            type(timestamp) is not int
            or abs(current - timestamp) > 300
            or len(body) > 65536
        ):
            raise ValueError("Expired or oversized webhook")
        expected = hmac.new(
            secret.encode(),
            str(timestamp).encode() + b"." + delivery_id.encode() + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise ValueError("Invalid webhook signature")
        value = json.loads(body)
        with self.db:
            try:
                self.db.execute(
                    "INSERT INTO received VALUES(?,?)", (delivery_id, current)
                )
                self.db.execute(
                    "INSERT INTO inbox(delivery_id,body) VALUES(?,?)",
                    (delivery_id, json.dumps(value)),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("Webhook replay rejected") from exc
        return value
