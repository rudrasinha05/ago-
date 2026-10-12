"""Strict transport for reviewed enterprise intelligence and scoped integration clients."""

from __future__ import annotations

import asyncio
from typing import Literal
from urllib.parse import parse_qs
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import Field

from ago.api_contracts import StrictInput
from ago.api_m2 import authenticated, repository_scope, translate_error
from ago.backend_contracts import RepositoryScope
from ago.repository_ports import (
    EnterpriseGraphPort,
    BehaviorStorePort,
    AnalyticsStorePort,
    IntegrationStorePort,
    ReviewedChangesPort,
)
from ago.reviewed_changes import canonical
from ago.security import Principal, AuthenticationError

router = APIRouter(prefix="/v1/enterprise", tags=["Enterprise intelligence"])
integration_router = APIRouter(prefix="/v1/platform", tags=["Company API platform"])
DOMAINS = {
    "graph": EnterpriseGraphPort,
    "behavior": BehaviorStorePort,
    "analytics": AnalyticsStorePort,
    "integration": IntegrationStorePort,
}
Domain = Literal["graph", "behavior", "analytics", "integration"]


class ProposalInput(StrictInput):
    command: str = Field(min_length=1, max_length=40)
    specification: dict
    operation_key: str = Field(min_length=1, max_length=160)
    base_revision: int = Field(ge=0)
    rationale: str = Field(min_length=1, max_length=6000)


class ApplyInput(StrictInput):
    proposal_id: UUID


class ReasonInput(StrictInput):
    reason: str = Field(min_length=1, max_length=3000)


class SnapshotInput(StrictInput):
    operation_key: str = Field(min_length=1, max_length=160)


@router.get("/reviews/{domain}")
def reviews(
    domain: Domain,
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        ledger = repositories.resolve(ReviewedChangesPort)
        return {
            "revision": ledger.revision(tenant_id=actor.tenant_id, domain=domain),
            "proposals": ledger.pending(actor=actor, domain=domain),
        }
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.post("/reviews/{domain}/propose")
def propose(
    domain: Domain,
    data: ProposalInput,
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(DOMAINS[domain]).propose(actor=actor, **data.model_dump())
    except (TypeError, KeyError, AttributeError) as exc:
        raise HTTPException(400, "Invalid typed proposal fields") from exc
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.post("/reviews/{domain}/apply")
def apply(
    domain: Domain,
    data: ApplyInput,
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(DOMAINS[domain]).apply(
            actor=actor, proposal_id=str(data.proposal_id)
        )
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.get("/graph")
def graph(
    root_id: UUID | None = None,
    relation: str | None = None,
    kind: str | None = None,
    direction: str = "both",
    depth: int = 2,
    limit: int = 100,
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(EnterpriseGraphPort).query(
            actor=actor,
            root_id=str(root_id) if root_id else None,
            relation=relation,
            kind=kind,
            direction=direction,
            depth=depth,
            limit=limit,
        )
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.get("/graph/quality")
def graph_quality(
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(EnterpriseGraphPort).quality(actor=actor)
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.post("/graph/synchronize")
def graph_sync(
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(EnterpriseGraphPort).synchronize(actor=actor)
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.get("/behavior/{employee_id}")
def behavior(
    employee_id: UUID,
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(BehaviorStorePort).profile(
            actor=actor, employee_id=str(employee_id)
        )
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.post("/behavior/{employee_id}/appeals")
def appeal(
    employee_id: UUID,
    data: ReasonInput,
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(BehaviorStorePort).appeal(
            actor=actor, employee_id=str(employee_id), reason=data.reason
        )
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.get("/analytics/catalog")
def catalog(
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(AnalyticsStorePort).catalog(actor=actor)
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.get("/analytics/dashboard")
def dashboard(
    dashboard: str = "executive",
    department_id: UUID | None = None,
    employee_id: UUID | None = None,
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(AnalyticsStorePort).dashboard(
            actor=actor,
            dashboard=dashboard,
            department_id=str(department_id) if department_id else None,
            employee_id=str(employee_id) if employee_id else None,
        )
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.get("/analytics/history/{metric}")
def history(
    metric: str,
    horizon_days: int = 7,
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(AnalyticsStorePort).history(
            actor=actor, metric=metric, horizon_days=horizon_days
        )
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.post("/analytics/snapshots")
def capture(
    data: SnapshotInput,
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(AnalyticsStorePort).capture(
            actor=actor, operation_key=data.operation_key
        )
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.get("/analytics/reports")
def reports(
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(AnalyticsStorePort).reports(actor=actor)
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.post("/analytics/tick")
def tick(
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(AnalyticsStorePort).tick(actor=actor)
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@integration_router.get("/catalog")
def integration_catalog(
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(IntegrationStorePort).catalog(actor=actor)
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


class CredentialInput(StrictInput):
    kind: Literal["api_key", "client_secret"]


@integration_router.post("/clients/{client_id}/credentials")
def credentials(
    client_id: UUID,
    data: CredentialInput,
    response: Response,
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    response.headers["Cache-Control"] = "no-store"
    try:
        return repositories.resolve(IntegrationStorePort).issue(
            actor=actor, client_id=str(client_id), kind=data.kind
        )
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


class ConsentInput(StrictInput):
    client_id: UUID
    redirect_uri: str = Field(max_length=1000)
    code_challenge: str = Field(min_length=43, max_length=43)
    code_challenge_method: Literal["S256"]
    scopes: list[str] = Field(min_length=1, max_length=4)
    state: str = Field(min_length=16, max_length=256)


@integration_router.post("/oauth/authorize")
def consent(
    data: ConsentInput,
    response: Response,
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    response.headers["Cache-Control"] = "no-store"
    try:
        return repositories.resolve(IntegrationStorePort).authorize(
            actor=actor,
            client_id=str(data.client_id),
            redirect=data.redirect_uri,
            challenge=data.code_challenge,
            scopes=data.scopes,
            state=data.state,
        )
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@integration_router.post("/oauth/token")
async def token(
    request: Request, response: Response, repositories: RepositoryScope = Depends(repository_scope)
):
    body = await request.body()
    if len(body) > 8192:
        raise HTTPException(413, "Token request too large")
    if request.headers.get("content-type", "").split(";")[0] != "application/x-www-form-urlencoded":
        raise HTTPException(400, "OAuth form body required")
    try:
        form = parse_qs(body.decode(), keep_blank_values=True, strict_parsing=True)
        if any(len(v) != 1 for v in form.values()) or set(form) - {
            "grant_type",
            "client_id",
            "client_secret",
            "code",
            "redirect_uri",
            "code_verifier",
            "scope",
        }:
            raise ValueError("Invalid token fields")
        values = {k: v[0] for k, v in form.items()}
        response.headers["Cache-Control"] = "no-store"
        return repositories.resolve(IntegrationStorePort).token(
            grant_type=values.get("grant_type", ""),
            client_id=values.get("client_id", ""),
            client_secret=values.get("client_secret", ""),
            code=values.get("code", ""),
            redirect=values.get("redirect_uri", ""),
            verifier=values.get("code_verifier", ""),
            scopes=values.get("scope", "").split() or None,
            peer=request.client.host if request.client else "unknown",
        )
    except OverflowError as exc:
        raise HTTPException(429, "OAuth quota exceeded", headers={"Retry-After": "60"}) from exc
    except AuthenticationError as exc:
        raise HTTPException(401, "Invalid OAuth grant") from exc
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


def integration_token(request: Request):
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Integration bearer required")
    return auth[7:]


def gateway_error(exc):
    if isinstance(exc, AuthenticationError):
        raise HTTPException(401, "Invalid integration credential") from exc
    if isinstance(exc, OverflowError):
        raise HTTPException(
            429, "Integration quota exceeded", headers={"Retry-After": "60"}
        ) from exc
    translate_error(exc)


@integration_router.get("/events")
def events(
    request: Request,
    after: int = 0,
    limit: int = 100,
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(IntegrationStorePort).events(
            token=integration_token(request), after=after, limit=limit
        )
    except (AuthenticationError, ValueError, PermissionError, LookupError, OverflowError) as exc:
        gateway_error(exc)


@integration_router.get("/stream")
async def stream(
    request: Request, after: int = 0, repositories: RepositoryScope = Depends(repository_scope)
):
    store = repositories.resolve(IntegrationStorePort)
    secret = integration_token(request)
    try:
        first = store.events(token=secret, after=after, limit=100)
    except (AuthenticationError, ValueError, PermissionError, LookupError, OverflowError) as exc:
        gateway_error(exc)

    async def chunks():
        result = first
        for _ in range(12):
            if await request.is_disconnected():
                break
            for event in result["events"]:
                yield (
                    "id: "
                    + str(event["sequence"])
                    + "\nevent: "
                    + event["event_type"]
                    + "\ndata: "
                    + canonical(event["payload"])
                    + "\n\n"
                )
            yield ": heartbeat\n\n"
            await asyncio.sleep(1)
            try:
                result = store.events(token=secret, after=result["next_cursor"], limit=100)
            except (AuthenticationError, PermissionError, OverflowError):
                break

    return StreamingResponse(
        chunks(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


class ExternalTaskInput(StrictInput):
    action: str = Field(min_length=1, max_length=500)
    assignee_id: UUID


@integration_router.post("/tasks", dependencies=[Depends(integration_token)])
def external_task(
    request: Request,
    data: ExternalTaskInput,
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(IntegrationStorePort).propose_task(
            token=integration_token(request),
            action=data.action,
            assignee_id=str(data.assignee_id),
            operation_key=request.headers.get("idempotency-key", ""),
        )
    except (AuthenticationError, ValueError, PermissionError, LookupError, OverflowError) as exc:
        gateway_error(exc)


@integration_router.post("/publish")
def publish(
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(IntegrationStorePort).publish(actor=actor)
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@integration_router.post("/webhooks/{subscription_id}/rotate")
def rotate(
    subscription_id: UUID,
    response: Response,
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    response.headers["Cache-Control"] = "no-store"
    try:
        return repositories.resolve(IntegrationStorePort).rotate_webhook(
            actor=actor, subscription_id=str(subscription_id)
        )
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@integration_router.post("/webhooks/deliver")
def deliver(
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(IntegrationStorePort).deliver(actor=actor)
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@integration_router.post("/webhooks/deliveries/{delivery_id}/replay")
def replay(
    delivery_id: UUID,
    data: ReasonInput,
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(IntegrationStorePort).replay(
            actor=actor, delivery_id=str(delivery_id), reason=data.reason
        )
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@integration_router.get("/tasks")
def external_tasks(
    request: Request,
    after: UUID | None = None,
    limit: int = 50,
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(IntegrationStorePort).tasks(
            token=integration_token(request), after=str(after) if after else None, limit=limit
        )
    except (AuthenticationError, ValueError, PermissionError, LookupError, OverflowError) as exc:
        gateway_error(exc)


@router.get("/reviews/source/{approval_id}")
def source_package(
    approval_id: UUID,
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(ReviewedChangesPort).inspect(
            actor=actor, approval_id=str(approval_id)
        )
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


class PlatformBodyLimit:
    """Bound platform request bodies before parsing; no trust in Content-Length."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope.get("path", "").startswith(
            ("/v1/platform/", "/v1/enterprise/")
        ):
            return await self.app(scope, receive, send)
        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body = message.get("body", b"")
            size += len(body)
            if size > 65536:
                await send(
                    {
                        "type": "http.response.start",
                        "status": 413,
                        "headers": [(b"content-type", b"application/json")],
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": b'{"detail":"Enterprise request exceeds64KiB"}',
                    }
                )
                return
            chunks.append(body)
            if not message.get("more_body", False):
                break
        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


@integration_router.post("/github/operations/{operation_id}/execute")
def github_execute(
    operation_id: UUID,
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(IntegrationStorePort).github_execute(
            actor=actor, operation_id=str(operation_id)
        )
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@integration_router.get("/github/projects/{project_id}/status")
def github_status(
    project_id: UUID,
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(IntegrationStorePort).github_status(
            actor=actor, project_id=str(project_id)
        )
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@integration_router.get("/analytics")
def external_analytics(
    request: Request,
    dashboard: str = "executive",
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(IntegrationStorePort).analytics(
            token=integration_token(request), dashboard=dashboard
        )
    except (AuthenticationError, ValueError, PermissionError, LookupError, OverflowError) as exc:
        gateway_error(exc)


@router.get("/graph/sources/{kind}/{identifier}")
def graph_source(
    kind: str,
    identifier: UUID,
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(EnterpriseGraphPort).source(
            actor=actor, kind=kind, identifier=str(identifier)
        )
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


class PluginDispatchInput(StrictInput):
    manifest: dict
    operation: Literal["tasks", "events", "propose_task", "analytics"]
    arguments: dict


@integration_router.post("/plugins/{plugin_id}/dispatch", dependencies=[Depends(integration_token)])
def plugin_dispatch(
    plugin_id: UUID,
    data: PluginDispatchInput,
    request: Request,
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(IntegrationStorePort).plugin_dispatch(
            token=integration_token(request), plugin_id=str(plugin_id), **data.model_dump()
        )
    except (AuthenticationError, ValueError, PermissionError, LookupError, OverflowError) as exc:
        gateway_error(exc)
