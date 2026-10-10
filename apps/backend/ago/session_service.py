"""Application sign-in orchestration; failures persist throttle evidence."""

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.identity import IdentityRepository
from ago.login_security import LoginThrottle
from ago.security import AuthenticationError, Principal


class SessionService:
    def __init__(
        self, connection: DatabaseConnection, *, repositories: RepositoryScope | None = None
    ):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

    def authenticate(self, tenant_id: str, email: str, password: str) -> Principal:
        throttle = self.repositories.resolve(LoginThrottle)
        if not throttle.begin(tenant_id, email):
            self.connection.commit()
            raise AuthenticationError("Invalid credentials")
        principal = self.repositories.resolve(IdentityRepository).authenticate(
            tenant_id, email, password
        )
        if principal is None:
            throttle.failure(tenant_id, email)
            self.connection.commit()
            raise AuthenticationError("Invalid credentials")
        throttle.success(tenant_id, email)
        return principal
