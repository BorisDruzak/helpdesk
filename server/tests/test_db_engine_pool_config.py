from __future__ import annotations

import pytest

from app.db import engine as db_engine


pytestmark = pytest.mark.no_db


def test_load_engine_pool_options_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PC_CLIENT_DB_POOL_SIZE", raising=False)
    monkeypatch.delenv("PC_CLIENT_DB_MAX_OVERFLOW", raising=False)
    monkeypatch.delenv("PC_CLIENT_DB_POOL_TIMEOUT_SEC", raising=False)
    monkeypatch.delenv("PC_CLIENT_DB_POOL_RECYCLE_SEC", raising=False)

    options = db_engine._load_engine_pool_options()

    assert options == {
        "pool_size": db_engine.DEFAULT_DB_POOL_SIZE,
        "max_overflow": db_engine.DEFAULT_DB_MAX_OVERFLOW,
        "pool_timeout": db_engine.DEFAULT_DB_POOL_TIMEOUT_SEC,
        "pool_recycle": db_engine.DEFAULT_DB_POOL_RECYCLE_SEC,
        "pool_use_lifo": True,
    }


def test_load_engine_pool_options_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PC_CLIENT_DB_POOL_SIZE", "14")
    monkeypatch.setenv("PC_CLIENT_DB_MAX_OVERFLOW", "9")
    monkeypatch.setenv("PC_CLIENT_DB_POOL_TIMEOUT_SEC", "45")
    monkeypatch.setenv("PC_CLIENT_DB_POOL_RECYCLE_SEC", "600")

    options = db_engine._load_engine_pool_options()

    assert options["pool_size"] == 14
    assert options["max_overflow"] == 9
    assert options["pool_timeout"] == 45
    assert options["pool_recycle"] == 600
    assert options["pool_use_lifo"] is True


def test_load_engine_pool_options_invalid_values_fall_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PC_CLIENT_DB_POOL_SIZE", "0")
    monkeypatch.setenv("PC_CLIENT_DB_MAX_OVERFLOW", "-2")
    monkeypatch.setenv("PC_CLIENT_DB_POOL_TIMEOUT_SEC", "oops")
    monkeypatch.setenv("PC_CLIENT_DB_POOL_RECYCLE_SEC", "-1")

    options = db_engine._load_engine_pool_options()

    assert options["pool_size"] == db_engine.DEFAULT_DB_POOL_SIZE
    assert options["max_overflow"] == db_engine.DEFAULT_DB_MAX_OVERFLOW
    assert options["pool_timeout"] == db_engine.DEFAULT_DB_POOL_TIMEOUT_SEC
    assert options["pool_recycle"] == db_engine.DEFAULT_DB_POOL_RECYCLE_SEC
