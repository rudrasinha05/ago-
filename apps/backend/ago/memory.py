"""M2 organization memory boundary: tenant and visibility constrained records."""
from dataclasses import dataclass
from uuid import uuid4


@dataclass(frozen=True)
class MemoryRecord:
    id: str
    tenant_id: str
    owner_id: str
    content: str
    visibility: str

    @classmethod
    def create(cls, *, tenant_id: str, owner_id: str, content: str, visibility: str = "private"):
        if not all((tenant_id.strip(), owner_id.strip(), content.strip())):
            raise ValueError("Memory fields required")
        if visibility not in ("private", "tenant"):
            raise ValueError("Unsupported memory visibility")
        return cls(str(uuid4()), tenant_id, owner_id, content, visibility)

    def read(self, *, tenant_id: str, reader_id: str) -> str:
        if tenant_id != self.tenant_id:
            raise PermissionError("Cross-tenant memory access denied")
        if self.visibility == "private" and reader_id != self.owner_id:
            raise PermissionError("Private memory access denied")
        return self.content
