"""Authenticated company map and shared conversation endpoints."""
from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Depends, Query
from pydantic import Field
from ago.api_contracts import StrictInput
from ago.api_m2 import allowed, authenticated, repository_scope, translate_error
from ago.repository_ports import CompanyChatPort

router = APIRouter(prefix='/v1/organization/company', tags=['Company map'])


class ChatInput(StrictInput):
    channel: str = Field(default='global', max_length=80)
    body: str = Field(min_length=1, max_length=20000)
    reply_to: int | None = Field(default=None, gt=0)
    operation_key: UUID


@router.get('/chat')
def timeline(channel: str = 'global', before: int | None = Query(default=None, gt=0),
             limit: int = Query(default=60, ge=1, le=200),
             actor=Depends(authenticated), repositories=Depends(repository_scope)):
    allowed(repositories, actor, 'organization:read')
    allowed(repositories, actor, 'task:read')
    allowed(repositories, actor, 'messages:read')
    try:
        return repositories.resolve(CompanyChatPort).list(actor.tenant_id, channel, before, limit, reader_id=actor.subject)
    except (ValueError, PermissionError) as exc:
        translate_error(exc)


@router.post('/chat')
def send(data: ChatInput, actor=Depends(authenticated), repositories=Depends(repository_scope)):
    allowed(repositories, actor, 'organization:read')
    allowed(repositories, actor, 'task:read')
    allowed(repositories, actor, 'messages:write')
    try:
        return repositories.resolve(CompanyChatPort).send(
            actor, data.channel, data.body, data.reply_to, str(data.operation_key))
    except ValueError as exc:
        translate_error(exc)


@router.get('/activity')
def activity(actor=Depends(authenticated), repositories=Depends(repository_scope)):
    allowed(repositories, actor, 'brain:read')
    allowed(repositories, actor, 'organization:read')
    allowed(repositories, actor, 'task:read')
    return repositories.resolve(CompanyChatPort).activity(actor.tenant_id, reader_id=actor.subject)

    
@router.get('/notifications')
def notifications(after_id: int | None = Query(default=None,ge=0),
                  actor=Depends(authenticated), repositories=Depends(repository_scope)):
    allowed(repositories, actor, 'organization:read')
    allowed(repositories, actor, 'task:read')
    return repositories.resolve(CompanyChatPort).notifications(
        actor.tenant_id, reader_id=actor.subject, after_id=after_id)


class StaffingInput(StrictInput):
    department_id: UUID
    manager_id: UUID | None = None
    name: str = Field(min_length=1, max_length=150)
    requirement: str = Field(min_length=10, max_length=3000)
    operation_key: UUID


@router.post('/staffing')
def staff(data: StaffingInput, actor=Depends(authenticated), repositories=Depends(repository_scope)):
    allowed(repositories, actor, 'organization:manage')
    allowed(repositories, actor, 'task:read')
    allowed(repositories, actor, 'messages:write')
    try:
        return repositories.resolve(CompanyChatPort).staff(
            actor, str(data.department_id), str(data.manager_id) if data.manager_id else None,
            data.name, data.requirement, str(data.operation_key))
    except (ValueError, PermissionError) as exc:
        translate_error(exc)

class ReportingManagerInput(StrictInput):
    manager_id: UUID | None = None


@router.put('/employees/{employee_id}/manager')
def employee_manager(employee_id: UUID, data: ReportingManagerInput,
                     actor=Depends(authenticated),
                     repositories=Depends(repository_scope)):
    allowed(repositories,actor,'organization:manage')
    try:
        return repositories.resolve(CompanyChatPort).set_reporting_manager(
            actor,str(employee_id),str(data.manager_id) if data.manager_id else None)
    except (ValueError,PermissionError,LookupError) as exc:
        translate_error(exc)


class RoleProfileInput(StrictInput):
    role_title: str = Field(min_length=1, max_length=150)
    core_responsibilities: str = Field(min_length=1, max_length=3000)
    extra_responsibilities: str = Field(default='', max_length=3000)


@router.get('/governance')
def governance(actor=Depends(authenticated), repositories=Depends(repository_scope)):
    allowed(repositories, actor, 'organization:read')
    return repositories.resolve(CompanyChatPort).governance(actor.tenant_id)


@router.put('/employees/{employee_id}/role')
def employee_role(employee_id: UUID, data: RoleProfileInput,
                  actor=Depends(authenticated), repositories=Depends(repository_scope)):
    allowed(repositories, actor, 'organization:manage')
    try:
        return repositories.resolve(CompanyChatPort).profile(
            actor, str(employee_id), data.role_title,
            data.core_responsibilities, data.extra_responsibilities)
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


class BoardAppointmentInput(StrictInput):
    seat: Literal['Strategy & Vision','Technology Oversight','Finance & Budget',
                  'Risk & Compliance','Quality & Release']
    employee_id: UUID


@router.post('/board/appoint')
def board_appoint(data: BoardAppointmentInput, actor=Depends(authenticated),
                  repositories=Depends(repository_scope)):
    allowed(repositories, actor, 'organization:manage')
    try:
        return repositories.resolve(CompanyChatPort).appoint(
            actor, data.seat, str(data.employee_id))
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


class ReportInput(StrictInput):
    kind: Literal['doubt','blocker','module_complete','phase_complete']
    body: str = Field(min_length=1, max_length=6000)
    task_id: UUID | None = None
    operation_key: UUID


@router.post('/reports')
def submit_report(data: ReportInput, actor=Depends(authenticated),
                  repositories=Depends(repository_scope)):
    allowed(repositories, actor, 'messages:write')
    try:
        return repositories.resolve(CompanyChatPort).report(
            actor, data.kind, data.body, str(data.operation_key),
            str(data.task_id) if data.task_id else None)
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.get('/reports')
def list_reports(limit: int = Query(default=100,ge=1,le=100),
                 actor=Depends(authenticated), repositories=Depends(repository_scope)):
    allowed(repositories, actor, 'messages:read')
    return repositories.resolve(CompanyChatPort).reports(actor,limit)

class FounderProjectInput(StrictInput):
    brief: str = Field(min_length=20,max_length=12000)
    operation_key: UUID


@router.post('/projects/start')
def founder_project(data: FounderProjectInput, actor=Depends(authenticated),
                    repositories=Depends(repository_scope)):
    allowed(repositories,actor,'organization:manage')
    allowed(repositories,actor,'brain:manage')
    try:
        return repositories.resolve(CompanyChatPort).start_project(
            actor,data.brief,str(data.operation_key))
    except (ValueError,PermissionError) as exc:
        translate_error(exc)


@router.get('/projects')
def founder_projects(limit: int = Query(default=50,ge=1,le=100),
                     offset: int = Query(default=0,ge=0,le=100000),
                     actor=Depends(authenticated),
                     repositories=Depends(repository_scope)):
    allowed(repositories,actor,'organization:read')
    allowed(repositories,actor,'brain:read')
    return repositories.resolve(CompanyChatPort).projects(
        actor.tenant_id,limit,offset,reader_id=actor.subject)


def delivery_overview_record(project: dict, detail: dict, pending: list[dict]) -> dict:
    """Presentation-only record from verified scoped data; no inferred approvals."""
    if str(project.get('id')) != str(detail.get('id')):
        raise ValueError('Project summary and private project evidence differ')
    stages = detail.get('stages')
    if not isinstance(stages, list) or len(stages) > 20:
        raise ValueError('Project stage evidence is incomplete or unbounded')
    result_stages = []
    for stage in stages:
        if not isinstance(stage, dict):
            raise ValueError('Invalid stage evidence')
        status = stage.get('task_status')
        verdict = stage.get('qa_verdict')
        if verdict not in (None, 'pass', 'fail'):
            raise ValueError('Unrecognized QA outcome')
        result_stages.append({
            'stage': stage.get('stage'),
            'position': stage.get('position'),
            'employee': stage.get('executing_employee')
                or stage.get('approved_assignee_name')
                or stage.get('suggested_assignee_name'),
            'task_status': status,
            'agent_run_status': stage.get('agent_run_status'),
            'agent_failure_code': stage.get('agent_failure_code'),
            'qa_verdict': verdict,
            'awaiting_independent_qa': status == 'completed' and verdict is None,
        })
    waiting_qa = any(s['awaiting_independent_qa'] for s in result_stages)
    blocked = detail.get('plan_status') == 'rejected' or any(
        s['task_status'] == 'failed' or s['agent_run_status'] == 'failed'
        or s['qa_verdict'] == 'fail'
        for s in result_stages
    )
    reviewed = bool(result_stages) and all(
        s['task_status'] == 'completed' and s['qa_verdict'] == 'pass'
        for s in result_stages
    )
    return {
        'project_id': project['id'],
        'title': detail.get('title'),
        'manager': detail.get('accountable_manager_name'),
        'plan_status': detail.get('plan_status'),
        'delivery_state': (
            'blocked' if blocked else
            'waiting_for_independent_qa' if waiting_qa else
            'working' if any(s['task_status'] == 'running' for s in result_stages) else
            'awaiting_project_plan_approval' if detail.get('plan_status') != 'active' else
            'internally_reviewed' if reviewed else
            'awaiting_governed_execution'
        ),
        'stages': result_stages,
        'pending_approvals': [
            {
                'approval_id': a.get('id'),
                'type': a.get('approval_type'),
                'action': a.get('action'),
                'requires_founder_decision': a.get('requires_founder_decision') is True,
                'review_routing': a.get('review_routing'),
            } for a in pending
        ],
        'docker_qa_verified': False,
        'github_commit_verified': False,
        'draft_pr_verified': False,
        'release_ready': False,
        'next_view': (
            'project_review' if blocked or detail.get('plan_status') != 'active' else
            'independent_qa' if waiting_qa else
            'project_work'
        ),
    }


@router.get('/projects/delivery-overview')
def founder_delivery_overview(
    limit: int = Query(default=20, ge=1, le=20),
    offset: int = Query(default=0, ge=0, le=100000),
    actor=Depends(authenticated),
    repositories=Depends(repository_scope),
):
    """Read-only Founder journey. Every displayed status originates in signed data."""
    allowed(repositories, actor, 'organization:read')
    allowed(repositories, actor, 'brain:read')
    allowed(repositories, actor, 'approval:founder')
    allowed(repositories, actor, 'approval:read')
    store = repositories.resolve(CompanyChatPort)
    try:
        projects = store.projects(actor.tenant_id, limit, offset,
                                  reader_id=actor.subject)
        if not isinstance(projects, list):
            raise ValueError('Incomplete project registry')
        # Approval inbox returns signed tenant records. Expose only approvals
        # linked to one of these individually readable project IDs/tasks.
        approvals = store.approval_inbox(actor.tenant_id, 100,
                                        reader_id=actor.subject)
        if not isinstance(approvals, list):
            raise ValueError('Incomplete approval inbox')
        results = []
        for project in projects:
            if not isinstance(project, dict) or not project.get('id'):
                raise ValueError('Incomplete project registry entry')
            detail = store.project_details(actor.tenant_id, str(project['id']),
                                           reader_id=actor.subject)
            if not isinstance(detail, dict):
                raise ValueError('Incomplete project details')
            # Validate the exact scoped record before traversing its stages or
            # linking approvals. Missing evidence must not become an empty plan.
            delivery_overview_record(project, detail, [])
            ids = {str(s['task_id']) for s in detail['stages'] if s.get('task_id')}
            linked = [
                a for a in approvals
                if isinstance(a, dict) and a.get('status') == 'pending'
                and (
                    str(a.get('founder_intake_id')) == str(project['id'])
                    or a.get('task_id') is not None
                    and str(a['task_id']) in ids
                )
            ]
            results.append(delivery_overview_record(project, detail, linked))
        return {
            'kind': 'ago_founder_delivery_overview_v1',
            'projects': results,
            'more_projects_possible': len(projects) == limit,
            'source': 'tenant_scoped_persisted_project_and_approval_records',
            'read_only': True,
            'owner_local_docker_or_github_verified': False,
            'human_approvals_automatically_executed': False,
        }
    except (KeyError, ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.post('/projects/{project_id}/ceo/reconcile')
def ceo_reconcile(project_id: UUID, actor=Depends(authenticated),
                  repositories=Depends(repository_scope)):
    allowed(repositories,actor,'organization:manage')
    allowed(repositories,actor,'brain:manage')
    try:
        return repositories.resolve(CompanyChatPort).ceo_reconcile(
            actor,str(project_id))
    except (ValueError,PermissionError,LookupError) as exc:
        translate_error(exc)


@router.get('/projects/{project_id}/staffing-proposals')
def founder_project_staffing_proposals(
    project_id: UUID, actor=Depends(authenticated),
    repositories=Depends(repository_scope),
):
    allowed(repositories,actor,'organization:read')
    allowed(repositories,actor,'approval:founder')
    try:
        return repositories.resolve(CompanyChatPort).staffing_proposals(
            actor,str(project_id))
    except (ValueError,PermissionError,LookupError) as exc:
        translate_error(exc)


@router.get('/projects/{project_id}')
def founder_project_details(project_id: UUID,actor=Depends(authenticated),
                            repositories=Depends(repository_scope)):
    allowed(repositories,actor,'organization:read')
    allowed(repositories,actor,'brain:read')
    try:
        return repositories.resolve(CompanyChatPort).project_details(
            actor.tenant_id,str(project_id),reader_id=actor.subject)
    except (ValueError,LookupError) as exc:
        translate_error(exc)

class StageDelegationInput(StrictInput):
    stage: Literal['discovery','architecture','implementation','quality','release']
    assignee_id: UUID


@router.post('/projects/{project_id}/delegations')
def propose_project_delegation(project_id: UUID, data: StageDelegationInput,
                               actor=Depends(authenticated),
                               repositories=Depends(repository_scope)):
    allowed(repositories,actor,'organization:manage')
    allowed(repositories,actor,'brain:manage')
    try:
        return repositories.resolve(CompanyChatPort).propose_stage_delegation(
            actor,str(project_id),data.stage,str(data.assignee_id))
    except (ValueError,PermissionError,LookupError) as exc:
        translate_error(exc)


@router.get('/projects/{project_id}/delegations')
def list_project_delegations(project_id: UUID, actor=Depends(authenticated),
                             repositories=Depends(repository_scope)):
    allowed(repositories,actor,'organization:read')
    allowed(repositories,actor,'brain:read')
    try:
        return repositories.resolve(CompanyChatPort).project_delegations(
            actor.tenant_id,str(project_id),reader_id=actor.subject)
    except (ValueError,PermissionError,LookupError) as exc:
        translate_error(exc)


@router.post('/projects/{project_id}/delegations/{proposal_id}/activate')
def activate_project_delegation(project_id: UUID,proposal_id: UUID,
                                actor=Depends(authenticated),
                                repositories=Depends(repository_scope)):
    allowed(repositories,actor,'organization:manage')
    allowed(repositories,actor,'brain:manage')
    try:
        return repositories.resolve(CompanyChatPort).activate_stage_delegation(
            actor,str(project_id),str(proposal_id))
    except (ValueError,PermissionError,LookupError) as exc:
        translate_error(exc)


@router.get('/approvals')
def approval_inbox(limit: int = Query(default=100,ge=1,le=100),
                   actor=Depends(authenticated), repositories=Depends(repository_scope)):
    allowed(repositories, actor, 'approval:read')
    return repositories.resolve(CompanyChatPort).approval_inbox(
        actor.tenant_id,limit,reader_id=actor.subject)

@router.get('/management/workload')
def management_workload(actor=Depends(authenticated), repositories=Depends(repository_scope)):
    allowed(repositories,actor,'organization:read')
    allowed(repositories,actor,'task:read')
    allowed(repositories,actor,'approval:founder')
    return repositories.resolve(CompanyChatPort).management_workload(actor.tenant_id)

@router.get('/opportunities')
def opportunity_radar(limit: int = Query(default=30,ge=1,le=100),
                      actor=Depends(authenticated), repositories=Depends(repository_scope)):
    allowed(repositories,actor,'organization:read')
    allowed(repositories,actor,'brain:read')
    allowed(repositories,actor,'approval:founder')
    return repositories.resolve(CompanyChatPort).opportunity_radar(actor.tenant_id,limit)


@router.post('/opportunities/scan')
def scan_opportunities(actor=Depends(authenticated), repositories=Depends(repository_scope)):
    allowed(repositories,actor,'organization:manage')
    allowed(repositories,actor,'brain:manage')
    if 'founder' not in actor.roles:
        translate_error(PermissionError('Only founder can initiate this manual company scan'))
    return repositories.resolve(CompanyChatPort).scan_opportunities(actor.tenant_id)

@router.get('/market-intelligence')
def market_intelligence(limit: int = Query(default=100,ge=1,le=200),
                        actor=Depends(authenticated),
                        repositories=Depends(repository_scope)):
    allowed(repositories,actor,'organization:read')
    allowed(repositories,actor,'brain:read')
    allowed(repositories,actor,'approval:founder')
    try:
        return repositories.resolve(CompanyChatPort).market_intelligence(actor.tenant_id,limit)
    except (ValueError,PermissionError) as exc:
        translate_error(exc)


@router.post('/market-intelligence/{signal_id}/project')
def create_approved_market_project(signal_id: UUID,actor=Depends(authenticated),
                                   repositories=Depends(repository_scope)):
    allowed(repositories,actor,'organization:manage')
    allowed(repositories,actor,'brain:manage')
    if 'founder' not in actor.roles:
        translate_error(PermissionError('Only founder may promote a research signal'))
    try:
        return repositories.resolve(CompanyChatPort).approved_signal_project(
            actor,str(signal_id))
    except (ValueError,PermissionError,LookupError) as exc:
        translate_error(exc)
