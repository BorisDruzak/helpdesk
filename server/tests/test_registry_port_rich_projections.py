from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from domain_ports import (
    ActorRef,
    DeviceRef,
    DirectoryPersonProjection,
    DirectorySearchProjection,
    PersonRef,
    RegistryInvalidProjection,
    RegistryReadActor,
    RegistryUnavailable,
    UnavailableRegistryPort,
)
from registry_adapter import LocalRegistryAdapter


pytestmark = pytest.mark.no_db


class _Result:
    def __init__(self, *, scalar: object | None = None, rows: list[object] | None = None) -> None:
        self._scalar = scalar
        self._rows = list(rows or [])

    def scalar_one_or_none(self) -> object | None:
        return self._scalar

    def scalars(self) -> "_Result":
        return self

    def all(self) -> list[object]:
        return list(self._rows)


class _Session:
    def __init__(self, *results: _Result) -> None:
        self._results = list(results)
        self.savepoints = 0

    @asynccontextmanager
    async def begin_nested(self):
        self.savepoints += 1
        yield self

    async def execute(self, _statement: object) -> _Result:
        if not self._results:
            raise AssertionError("unexpected Registry query")
        return self._results.pop(0)


class _FailThenRecoverSession(_Session):
    def __init__(self) -> None:
        super().__init__(_Result(scalar=None))
        self._failed = False

    async def execute(self, statement: object) -> _Result:
        if not self._failed:
            self._failed = True
            raise RuntimeError("database details must not escape")
        return await super().execute(statement)


def _actor(*, role: str = "support") -> RegistryReadActor:
    return RegistryReadActor(
        actor=ActorRef(external_id="verified-actor-support-1"),
        role=role,
    )


def _person(*, person_id: str = "registry-ref-opaque-person-1") -> SimpleNamespace:
    return SimpleNamespace(
        person_id=person_id,
        display_name="Иван",
        full_name="Иван Иванов",
        email="ivan@example.test",
        phone="+7-000-000-0000",
        department_id=None,
        location_id=None,
        status="active",
    )


def test_directory_contract_rejects_an_unbounded_collection() -> None:
    item = DirectoryPersonProjection(
        requester={"external_id": "registry-ref-opaque-person-1"},
        display_name="Иван",
        status="active",
        source="external_authoritative",
    )

    with pytest.raises(ValueError, match="directory projection exceeds"):
        DirectorySearchProjection(items=tuple(item for _ in range(51)), source="external_authoritative")


@pytest.mark.asyncio
async def test_local_port_directory_search_returns_only_safe_person_projection() -> None:
    result = await LocalRegistryAdapter(_Session(_Result(rows=[_person()]))).search_people(
        "Иван",
        actor=_actor(),
    )

    assert result.items[0].display_name == "Иван"
    assert "email" not in result.items[0].model_dump(mode="json")
    assert "phone" not in result.items[0].model_dump(mode="json")


@pytest.mark.asyncio
async def test_directory_search_requires_trusted_support_or_admin_actor() -> None:
    result = await LocalRegistryAdapter(_Session()).search_people(
        "Иван",
        actor=_actor(role="user"),
    )

    assert isinstance(result, RegistryUnavailable)
    assert result.code == "registry_actor_forbidden"


@pytest.mark.asyncio
async def test_invalid_requester_profile_is_distinct_from_not_found() -> None:
    invalid_person = _person()
    invalid_person.display_name = ""

    result = await LocalRegistryAdapter(_Session(_Result(scalar=invalid_person))).requester_profile(
        PersonRef(external_id="registry-ref-opaque-person-1"),
        actor=_actor(),
    )

    assert isinstance(result, RegistryInvalidProjection)
    assert result.code == "registry_projection_invalid"


@pytest.mark.asyncio
async def test_invalid_device_context_code_is_not_coerced_to_unknown() -> None:
    asset = SimpleNamespace(
        device_id="registry-ref-opaque-device-1",
        name="Рабочая станция",
        asset_type="desktop pc",
        status="active",
        assigned_person_id=None,
        department_id=None,
        location_id=None,
        asset_id="local-asset-id-must-not-leak",
    )

    result = await LocalRegistryAdapter(_Session(_Result(scalar=asset))).device_context(
        DeviceRef(external_id="registry-ref-opaque-device-1")
    )

    assert isinstance(result, RegistryInvalidProjection)


@pytest.mark.asyncio
async def test_local_read_failure_is_savepoint_isolated_and_safe() -> None:
    session = _FailThenRecoverSession()
    adapter = LocalRegistryAdapter(session)

    failed = await adapter.requester_profile(
        PersonRef(external_id="registry-ref-opaque-person-1"),
        actor=_actor(),
    )
    recovered = await adapter.requester_snapshot(
        PersonRef(external_id="registry-ref-opaque-person-1")
    )

    assert isinstance(failed, RegistryUnavailable)
    assert failed.code == "registry_read_unavailable"
    assert session.savepoints == 2
    assert recovered.status == "not_found"


@pytest.mark.asyncio
async def test_device_context_is_typed_unavailable_without_local_fallback() -> None:
    result = await UnavailableRegistryPort().device_context(
        DeviceRef(external_id="registry-ref-opaque-device-1")
    )

    assert result.code == "registry_unavailable"
