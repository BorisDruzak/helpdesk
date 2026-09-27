from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import traceback

import pytest
from sqlalchemy.exc import IntegrityError

from app.repos import ui_users_repo


pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
async def test_create_user_conflict_does_not_log_sql_parameters(monkeypatch):
    # A synthetic marker proves the conflict path does not disclose DB values.
    marker = "private-fixture-value"
    conflict = IntegrityError(
        "INSERT INTO ui_users (user_login, password_hash) VALUES (?, ?)",
        {"user_login": "fixture-user", "password_hash": marker},
        RuntimeError("duplicate key"),
    )
    session = SimpleNamespace(
        add=Mock(), commit=AsyncMock(side_effect=conflict),
        rollback=AsyncMock(), refresh=AsyncMock(),
    )
    repo = ui_users_repo.UiUsersRepo(session)
    monkeypatch.setattr(repo, "get_by_login", AsyncMock(return_value=None))
    monkeypatch.setattr(repo, "_audit", AsyncMock())
    messages = []
    monkeypatch.setattr(ui_users_repo, "logger", SimpleNamespace(error=messages.append))

    with pytest.raises(ValueError, match="^User already exists$") as caught:
        await repo.create_user("fixture-user", marker)

    session.rollback.assert_awaited_once()
    session.refresh.assert_not_awaited()
    assert messages == ["[UiUsersRepo] create_user conflict"]
    assert marker not in str(caught.value)
    assert caught.value.__suppress_context__ is True
    reported = "".join(traceback.format_exception(caught.value))
    assert marker not in reported
    assert "INSERT INTO ui_users" not in reported
