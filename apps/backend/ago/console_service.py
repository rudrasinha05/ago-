"""Application orchestration for one atomic approval/task submission."""

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.console_store import ConsoleStore
from ago.governance import ApprovalRepository
from ago.security import Principal
from ago.task_store import TaskStore


class ConsoleService:
    def __init__(
        self, connection: DatabaseConnection, *, repositories: RepositoryScope | None = None
    ):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

    def request_approval(self, task_id: str, actor: Principal) -> dict:
        with self.connection.transaction():
            task = self.repositories.resolve(ConsoleStore).lock_proposed_task(
                task_id, actor.tenant_id
            )
            proposal = self.repositories.resolve(ApprovalRepository).propose(
                tenant_id=actor.tenant_id, requester_id=actor.subject, action=task["action"]
            )
            self.repositories.resolve(TaskStore).request_approval(
                task_id=task_id, tenant_id=actor.tenant_id, approval_id=proposal.request_id
            )
        return {"approval_id": proposal.request_id, "status": "waiting_approval"}
