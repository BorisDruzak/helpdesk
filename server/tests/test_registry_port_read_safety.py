"""Regression tests for safe local RegistryPort read isolation."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import RegistryPerson
from app.repos.registry_repo import RegistryRepo
from domain_ports import PersonRef, RegistryUnavailable
from registry_adapter import LocalRegistryAdapter


pytestmark = pytest.mark.db_cleanup("registry_access")


@pytest.mark.asyncio
async def test_registry_directory_search_treats_sql_wildcards_as_literal_text(test_engine) -> None:
    """Directory input is text, never a SQL LIKE expression."""

    prefix = uuid.uuid4().hex
    rows = {
        "percent": (f"{prefix}%person", f"{prefix}Xperson"),
        "underscore": (f"{prefix}_person", f"{prefix}Aperson"),
        "escape": (f"{prefix}\\person", f"{prefix}person"),
    }
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        for matched_name, unmatched_name in rows.values():
            session.add_all(
                [
                    RegistryPerson(
                        person_id=str(uuid.uuid4()),
                        display_name=matched_name,
                        source="test",
                        status="active",
                        metadata_json={},
                    ),
                    RegistryPerson(
                        person_id=str(uuid.uuid4()),
                        display_name=unmatched_name,
                        source="test",
                        status="active",
                        metadata_json={},
                    ),
                ]
            )
        await session.commit()

    async with session_factory() as session:
        repo = RegistryRepo(session)
        for matched_name, _unmatched_name in rows.values():
            found = await repo.search_people(query=matched_name, limit=10)

            assert [person.display_name for person in found] == [matched_name]


@pytest.mark.asyncio
async def test_connection_bound_failed_read_preserves_caller_transaction(
    test_engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed port read must not abort a transaction bound by the caller."""

    async def fail_inside_registry_read(self, _person_id: str):
        await self.session.execute(text("SELECT 1 / 0"))
        raise AssertionError("database failure was expected")

    monkeypatch.setattr(RegistryRepo, "get_person", fail_inside_registry_read)

    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        caller_session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
        try:
            result = await LocalRegistryAdapter(caller_session).requester_snapshot(
                PersonRef(external_id="registry-ref-opaque-person-1")
            )

            assert isinstance(result, RegistryUnavailable)
            assert result.code == "registry_read_unavailable"
            assert (await caller_session.execute(text("SELECT 42"))).scalar_one() == 42
        finally:
            await caller_session.close()
            await transaction.rollback()
