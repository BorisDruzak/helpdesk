"""Audit privacy and PostgreSQL read-only transaction safety."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import sys

import pytest

pytestmark = pytest.mark.no_db
source = Path(__file__).resolve().parents[2] / "scripts/audit_legacy_device_inventory.py"
spec = importlib.util.spec_from_file_location("retirement_audit", source)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_private_export_redacts_possible_credentials_recursively():
    value = {"notes": "password=private", "tags": ["workplace", "Bearer sensitive"], "other": "Room 3"}
    result = audit.safe_metadata(value)
    assert result == {"notes": "[REDACTED: possible credential]", "tags": ["workplace", "[REDACTED: possible credential]"], "other": "Room 3"}
    assert "private" not in str(result) and "sensitive" not in str(result)


@pytest.mark.asyncio
async def test_audit_uses_readonly_repeatable_read_and_never_mutates_tables(monkeypatch):
    transactions = []
    class Transaction:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_):
            return False
    def transaction(**options):
        transactions.append(options)
        return Transaction()
    connection = SimpleNamespace(transaction=transaction, execute=AsyncMock(), fetch=AsyncMock(return_value=[]), close=AsyncMock())
    connect = AsyncMock(return_value=connection)
    monkeypatch.setitem(sys.modules, "asyncpg", SimpleNamespace(connect=connect))
    monkeypatch.setitem(sys.modules, "dotenv", SimpleNamespace(dotenv_values=lambda _: {"DATABASE_URL": "postgresql+asyncpg://local/test"}))
    result = await audit.remote_audit("private-env")
    assert transactions == [{"isolation": "repeatable_read", "readonly": True}]
    connection.execute.assert_awaited_once_with("SET LOCAL statement_timeout = '15000ms'")
    assert all(call.args[0].startswith("SELECT ") for call in connection.fetch.await_args_list)
    assert result["report"]["read_only"] is True
    assert result["report"]["migration"]["automatic_updates"] == 0
    assert result["private_export"] == []
    connection.close.assert_awaited_once()


def test_redaction_handles_api_keys_and_sensitive_dictionary_keys():
    assert audit.safe_metadata("api_key=synthetic") == "[REDACTED: possible credential]"
    assert audit.safe_metadata({"password": "synthetic", "cookie": "synthetic", "api-key": "synthetic"}) == {
        "password": "[REDACTED: possible credential]", "cookie": "[REDACTED: possible credential]", "api-key": "[REDACTED: possible credential]"}


def test_private_export_rejects_tracked_source_directory():
    root = source.parents[1]
    assert audit.validate_private_output(root / ".git/admin-cutover-retirement-audit").is_relative_to(root / ".git")
    with pytest.raises(ValueError, match="ignored"):
        audit.validate_private_output(root / "docs")
