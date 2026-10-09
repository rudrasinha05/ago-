"""M1 operational feature flags with tenant overrides and default-off behavior."""
from __future__ import annotations


class FeatureFlags:
    def __init__(self):
        self._defaults: dict[str, bool] = {}
        self._overrides: dict[tuple[str, str], bool] = {}

    def set_default(self, name: str, enabled: bool) -> None:
        if not name:
            raise ValueError("Flag name required")
        self._defaults[name] = enabled

    def set_tenant(self, name: str, tenant_id: str, enabled: bool) -> None:
        if not name or not tenant_id:
            raise ValueError("Flag and tenant required")
        self._overrides[(name, tenant_id)] = enabled

    def enabled(self, name: str, tenant_id: str | None = None) -> bool:
        if tenant_id is not None and (name, tenant_id) in self._overrides:
            return self._overrides[(name, tenant_id)]
        return self._defaults.get(name, False)
