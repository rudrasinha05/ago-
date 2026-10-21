"""AGO-local document permissions: founder controls every document grant.

No GitHub sync, cloud integration, implicit AI read permission, or global
company-role access to content. Signed local sessions and durable per-doc ACL.
"""
from uuid import UUID
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import Field

from ago.api_contracts import StrictInput
from ago.api_m2 import authenticated, allowed, repository_scope, translate_error
from ago.repository_ports import DocumentVaultPort

router=APIRouter(prefix="/v1/organization/company",tags=["AGO local documents"])


class DocumentInput(StrictInput):
    title: str=Field(min_length=1,max_length=180)
    body: str=Field(min_length=1,max_length=20000)
    classification: Literal["founder_only","project_restricted"]="founder_only"


class DocumentRevisionInput(StrictInput):
    body: str=Field(min_length=1,max_length=20000)


class DocumentPermissionInput(StrictInput):
    grantee_id: UUID
    event: Literal["grant","revoke"]
    rationale: str=Field(min_length=8,max_length=500)


@router.post("/projects/{project_id}/documents")
def create_document(project_id: UUID,data: DocumentInput,actor=Depends(authenticated),
                    repositories=Depends(repository_scope)):
    allowed(repositories,actor,"approval:founder")
    try:
        return repositories.resolve(DocumentVaultPort).create(
            actor.tenant_id,actor.subject,str(project_id),
            data.title,data.body,data.classification)
    except (ValueError,PermissionError,LookupError) as exc:
        translate_error(exc)


@router.get("/projects/{project_id}/documents")
def list_documents(project_id: UUID,actor=Depends(authenticated),
                   repositories=Depends(repository_scope)):
    try:
        return repositories.resolve(DocumentVaultPort).list(
            actor.tenant_id,actor.subject,str(project_id))
    except (ValueError,PermissionError,LookupError) as exc:
        translate_error(exc)


@router.get("/projects/{project_id}/documents/eligible")
def eligible_document_members(project_id: UUID,actor=Depends(authenticated),
                              repositories=Depends(repository_scope)):
    allowed(repositories,actor,"approval:founder")
    try:
        return repositories.resolve(DocumentVaultPort).eligible_members(
            actor.tenant_id,actor.subject,str(project_id))
    except (ValueError,PermissionError,LookupError) as exc:
        translate_error(exc)


@router.get("/documents/{document_id}")
def read_document(document_id: UUID,actor=Depends(authenticated),
                  repositories=Depends(repository_scope)):
    try:
        return repositories.resolve(DocumentVaultPort).read(
            actor.tenant_id,actor.subject,str(document_id))
    except (ValueError,PermissionError,LookupError) as exc:
        translate_error(exc)


@router.post("/documents/{document_id}/revisions")
def revise_document(document_id: UUID,data: DocumentRevisionInput,
                    actor=Depends(authenticated),repositories=Depends(repository_scope)):
    allowed(repositories,actor,"approval:founder")
    try:
        return repositories.resolve(DocumentVaultPort).revise(
            actor.tenant_id,actor.subject,str(document_id),data.body)
    except (ValueError,PermissionError,LookupError) as exc:
        translate_error(exc)


@router.post("/documents/{document_id}/permissions")
def document_permission(document_id: UUID,data: DocumentPermissionInput,
                        actor=Depends(authenticated),repositories=Depends(repository_scope)):
    allowed(repositories,actor,"approval:founder")
    try:
        return repositories.resolve(DocumentVaultPort).change_access(
            actor.tenant_id,actor.subject,str(document_id),str(data.grantee_id),
            data.event,data.rationale)
    except (ValueError,PermissionError,LookupError) as exc:
        translate_error(exc)


@router.get("/documents/{document_id}/audit")
def document_audit(document_id: UUID,actor=Depends(authenticated),
                   repositories=Depends(repository_scope)):
    allowed(repositories,actor,"approval:founder")
    try:
        return repositories.resolve(DocumentVaultPort).audit(
            actor.tenant_id,actor.subject,str(document_id))
    except (ValueError,PermissionError,LookupError) as exc:
        translate_error(exc)
