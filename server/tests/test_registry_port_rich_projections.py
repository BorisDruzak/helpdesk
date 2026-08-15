from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

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
from app.db.models import RegistryPerson


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
    def __init__(self, *results: _Result, get_rows: dict[str, object | None] | None = None) -> None:
        self._results = list(results)
        self._get_rows = dict(get_rows or {})
        self.savepoints = 0

    @asynccontextmanager
    async def begin_nested(self):
        self.savepoints += 1
        yield self

    async def execute(self, _statement: object) -> _Result:
        if not self._results:
            raise AssertionError("unexpected Registry query")
        return self._results.pop(0)

    async def scalar(self, _statement: object) -> object | None:
        if not self._results:
            raise AssertionError("unexpected Registry query")
        return self._results.pop(0)._scalar

    async def get(self, _model: object, key: str) -> object | None:
        return self._get_rows.get(str(key))


class _CaptureSession(_Session):
    def __init__(self, *results: _Result) -> None:
        super().__init__(*results)
        self.statements: list[object] = []

    async def execute(self, statement: object) -> _Result:
        self.statements.append(statement)
        return await super().execute(statement)


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


@pytest.mark.no_db
def test_directory_contract_rejects_an_unbounded_collection() -> None:
    item = DirectoryPersonProjection(
        requester={"external_id": "registry-ref-opaque-person-1"},
        display_name="Иван",
        status="active",
        source="external_authoritative",
    )

    with pytest.raises(ValueError, match="directory projection exceeds"):
        DirectorySearchProjection(items=tuple(item for _ in range(51)), source="external_authoritative")


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_local_port_directory_search_returns_only_safe_person_projection() -> None:
    result = await LocalRegistryAdapter(_Session(_Result(rows=[_person()]))).search_people(
        "Иван",
        actor=_actor(),
    )

    assert result.items[0].display_name == "Иван"
    assert "email" not in result.items[0].model_dump(mode="json")
    assert "phone" not in result.items[0].model_dump(mode="json")


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_directory_search_requires_trusted_support_or_admin_actor() -> None:
    result = await LocalRegistryAdapter(_Session()).search_people(
        "Иван",
        actor=_actor(role="user"),
    )

    assert isinstance(result, RegistryUnavailable)
    assert result.code == "registry_actor_forbidden"


@pytest.mark.no_db
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


@pytest.mark.no_db
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


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_local_read_failure_returns_safe_unavailable_without_a_savepoint() -> None:
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
    assert session.savepoints == 0
    assert recovered.status == "not_found"


@pytest.mark.asyncio
async def test_local_read_uses_an_independent_session_without_flushing_caller_pending_rows(
    test_engine,
) -> None:
    """Registry reads must not flush or invalidate a caller-owned unit of work."""

    person_id = str(uuid.uuid4())
    pending_id = str(uuid.uuid4())
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as setup_session:
        setup_session.add(
            RegistryPerson(
                person_id=person_id,
                display_name="Committed requester",
                source="test",
                status="active",
                metadata_json={},
            )
        )
        await setup_session.commit()

    async with session_factory() as caller_session:
        pending = RegistryPerson(person_id=pending_id, metadata_json={})
        caller_session.add(pending)

        result = await LocalRegistryAdapter(caller_session).requester_snapshot(
            PersonRef(external_id=person_id)
        )

        assert result.person.external_id == person_id
        assert pending in caller_session.new
        assert caller_session.is_active is True


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_audience_projection_overflow_returns_typed_invalid_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _AudienceResolution:
        def to_dict(self) -> dict[str, object]:
            return {
                "audience_groups": [
                    {"code": f"group-{index}"} for index in range(101)
                ],
                "warnings": [{"code": f"warning-{index}"} for index in range(101)],
            }

    async def resolve_person_audience(*_args: object, **_kwargs: object) -> _AudienceResolution:
        return _AudienceResolution()

    monkeypatch.setattr(
        "registry.effective_identity_service.EffectiveIdentityService.resolve_person_audience",
        resolve_person_audience,
    )
    result = await LocalRegistryAdapter(
        _Session(get_rows={"registry-ref-opaque-person-1": _person()})
    ).audience_projection(
        PersonRef(external_id="registry-ref-opaque-person-1"),
        actor=_actor(),
    )

    assert isinstance(result, RegistryInvalidProjection)


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_directory_search_filters_case_insensitively_in_sql_before_limit() -> None:
    session = _CaptureSession(_Result(rows=[_person()]))

    result = await LocalRegistryAdapter(session).search_people(
        "Иван",
        actor=_actor(),
        limit=1,
    )

    assert result.items[0].display_name == "Иван"
    statement = str(session.statements[0]).lower()
    assert "lower(registry_people.display_name) like" in statement
    assert statement.index("where") < statement.index("limit")


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_missing_account_status_is_typed_invalid_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def get_device_registration_status(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {"requires_user_action": False}

    monkeypatch.setattr(
        "registry.registration_service.RegistrationService.get_device_registration_status",
        get_device_registration_status,
    )
    result = await LocalRegistryAdapter(_Session()).account_status(
        DeviceRef(external_id="registry-ref-opaque-device-1")
    )

    assert isinstance(result, RegistryInvalidProjection)


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_missing_person_status_is_typed_invalid_projection() -> None:
    person = _person()
    del person.status

    result = await LocalRegistryAdapter(_Session(_Result(scalar=person))).requester_profile(
        PersonRef(external_id="registry-ref-opaque-person-1"),
        actor=_actor(),
    )

    assert isinstance(result, RegistryInvalidProjection)


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_directory_person_without_status_is_typed_invalid_projection() -> None:
    person = _person()
    del person.status

    result = await LocalRegistryAdapter(_Session(_Result(rows=[person]))).search_people(
        "Иван",
        actor=_actor(),
    )

    assert isinstance(result, RegistryInvalidProjection)


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_device_context_is_typed_unavailable_without_local_fallback() -> None:
    result = await UnavailableRegistryPort().device_context(
        DeviceRef(external_id="registry-ref-opaque-device-1")
    )

    assert result.code == "registry_unavailable"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_inventory_quality_invalid_count_is_typed_invalid_projection() -> None:
    result = await LocalRegistryAdapter(_Session(_Result(scalar="not-a-count"))).inventory_quality()

    assert isinstance(result, RegistryInvalidProjection)
