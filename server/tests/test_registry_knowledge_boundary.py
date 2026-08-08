from __future__ import annotations

from pathlib import Path

import pytest

from registry.admin_operations_service import RegistryAdminOperationsService
from scripts.check_domain_import_boundaries import find_forbidden_imports


pytestmark = pytest.mark.no_db

WORKSPACE = Path(__file__).resolve().parents[2]


class _ExplodingSession:
    async def execute(self, _statement: object) -> object:
        raise AssertionError("Registry must not query local Knowledge persistence")


@pytest.mark.asyncio
async def test_registry_rejects_knowledge_audience_export_without_querying_local_tables() -> None:
    with pytest.raises(ValueError, match="unsupported export type"):
        await RegistryAdminOperationsService(_ExplodingSession()).export_csv(
            "knowledge_audience_rules"
        )


def test_registry_services_have_no_local_knowledge_dependency() -> None:
    violations = find_forbidden_imports(WORKSPACE)
    owned_paths = {
        WORKSPACE / "server" / "registry" / "service.py",
        WORKSPACE / "server" / "registry" / "admin_operations_service.py",
    }

    assert [violation.imported for violation in violations if violation.path in owned_paths] == []
