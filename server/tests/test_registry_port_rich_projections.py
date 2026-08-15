from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

import domain_ports.registry_contracts as registry_contracts
from domain_ports import (
    ActorRef,
    DeviceRef,
    DirectoryPersonProjection,
    DirectorySearchProjection,
    OnBehalfCandidateProjection,
    OnBehalfPolicyProjection,
    PersonRef,
    RegistryInvalidProjection,
    RegistryNotFound,
    RegistryReadActor,
    RegistryUnavailable,
    RequesterRef,
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


def _requester_actor(*, creator_id: str = "creator-person") -> RegistryReadActor:
    return RegistryReadActor(
        actor=ActorRef(external_id="verified-ui-user"),
        role="user",
        requester=RequesterRef(external_id=creator_id),
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
def test_on_behalf_candidate_contract_is_bounded_and_purpose_bound() -> None:
    item = registry_contracts.OnBehalfCandidateProjection(
        person={"external_id": "affected-person"},
        display_name="Affected Person",
        full_name="Affected Person Full",
        email="affected@example.test",
        department={"external_id": "department-1"},
        department_label="Support",
        location={"external_id": "location-1"},
        location_label="Office 1",
        source="external_authoritative",
    )

    assert item.model_dump(mode="json") == {
        "person": {"external_id": "affected-person"},
        "display_name": "Affected Person",
        "full_name": "Affected Person Full",
        "email": "affected@example.test",
        "department": {"external_id": "department-1"},
        "department_label": "Support",
        "location": {"external_id": "location-1"},
        "location_label": "Office 1",
        "source": "external_authoritative",
    }
    assert "phone" not in item.model_dump(mode="json")
    with pytest.raises(ValueError, match="on-behalf candidate projection exceeds"):
        registry_contracts.OnBehalfCandidatesProjection(
            items=tuple(item for _ in range(11)),
            source="external_authoritative",
        )


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_requester_on_behalf_candidates_are_scoped_to_verified_creator() -> None:
    creator = _person(person_id="creator-person")
    creator.department_id = "department-1"
    same_department = _person(person_id="same-department-person")
    same_department.display_name = "Иван Same"
    same_department.department_id = "department-1"
    same_department.location_id = "location-1"
    outside = _person(person_id="outside-person")
    outside.display_name = "Иван Outside"
    outside.department_id = "department-2"
    session = _Session(
        _Result(scalar=creator),
        _Result(
            rows=[
                (
                    same_department,
                    SimpleNamespace(department_id="department-1", name="Support"),
                    SimpleNamespace(location_id="location-1", display_name="Office 1"),
                ),
                (
                    outside,
                    SimpleNamespace(department_id="department-2", name="Outside"),
                    None,
                ),
            ]
        ),
    )

    result = await LocalRegistryAdapter(session).on_behalf_candidates(
        actor=_requester_actor(),
        creator=RequesterRef(external_id="creator-person"),
        policy=registry_contracts.OnBehalfPolicyProjection(scope="same_department"),
        query="Иван",
    )

    assert [item.person.external_id for item in result.items] == ["same-department-person"]
    assert result.items[0].department.external_id == "department-1"
    assert result.items[0].department_label == "Support"
    assert result.items[0].location.external_id == "location-1"
    assert result.items[0].location_label == "Office 1"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_requester_on_behalf_candidates_allow_only_direct_reports() -> None:
    creator = _person(person_id="creator-person")
    direct_report = _person(person_id="direct-report-person")
    direct_report.metadata_json = {"manager_person_id": "creator-person"}
    other = _person(person_id="other-person")
    other.metadata_json = {"manager_person_id": "different-manager"}
    session = _Session(
        _Result(scalar=creator),
        _Result(rows=[(direct_report, None, None), (other, None, None)]),
    )

    result = await LocalRegistryAdapter(session).on_behalf_candidates(
        actor=_requester_actor(),
        creator=RequesterRef(external_id="creator-person"),
        policy=registry_contracts.OnBehalfPolicyProjection(scope="direct_reports"),
        query="Иван",
    )

    assert [item.person.external_id for item in result.items] == ["direct-report-person"]


@pytest.mark.no_db
@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["archived", "deleted", "disabled", "inactive", "merged"])
async def test_requester_on_behalf_candidates_exclude_inactive_people(status: str) -> None:
    creator = _person(person_id="creator-person")
    affected = _person(person_id="inactive-person")
    affected.status = status

    result = await LocalRegistryAdapter(
        _Session(_Result(scalar=creator), _Result(rows=[(affected, None, None)]))
    ).on_behalf_candidates(
        actor=_requester_actor(),
        creator=RequesterRef(external_id="creator-person"),
        policy=registry_contracts.OnBehalfPolicyProjection(scope="any_employee"),
        query="Иван",
    )

    assert result.items == ()


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_requester_on_behalf_exact_search_uses_sql_equality_before_limit() -> None:
    creator = _person(person_id="creator-person")
    affected = _person(person_id="affected-person")
    affected.display_name = "Exact Search Person"
    session = _CaptureSession(
        _Result(scalar=creator),
        _Result(rows=[(affected, None, None)]),
    )

    result = await LocalRegistryAdapter(session).on_behalf_candidates(
        actor=_requester_actor(),
        creator=RequesterRef(external_id="creator-person"),
        policy=registry_contracts.OnBehalfPolicyProjection(scope="exact_search_only"),
        query="Exact Search Person",
    )

    assert [item.person.external_id for item in result.items] == ["affected-person"]
    statement = str(session.statements[-1]).lower()
    assert "lower(registry_people.display_name) =" in statement
    assert "like" not in statement
    assert statement.index("where") < statement.index("limit")


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_on_behalf_authorization_denies_spoofed_creator_without_query() -> None:
    outcome = await LocalRegistryAdapter(_Session()).authorize_on_behalf(
        actor=_requester_actor(creator_id="verified-creator"),
        creator=RequesterRef(external_id="spoofed-creator"),
        affected=RequesterRef(external_id="affected-person"),
        policy=registry_contracts.OnBehalfPolicyProjection(scope="any_employee"),
    )

    assert outcome.status == "denied"
    assert outcome.code == "registry_actor_forbidden"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_on_behalf_authorization_enforces_exact_lookup() -> None:
    creator = _person(person_id="creator-person")
    affected = _person(person_id="affected-person")
    affected.display_name = "Exact Search Person"
    adapter = LocalRegistryAdapter(_Session(_Result(scalar=creator), _Result(scalar=affected)))

    denied = await adapter.authorize_on_behalf(
        actor=_requester_actor(),
        creator=RequesterRef(external_id="creator-person"),
        affected=RequesterRef(external_id="affected-person"),
        policy=registry_contracts.OnBehalfPolicyProjection(scope="exact_search_only"),
        lookup="Exact",
    )

    assert denied.status == "denied"
    assert denied.code == "registry_on_behalf_scope_denied"

    allowed = await LocalRegistryAdapter(
        _Session(_Result(scalar=creator), _Result(scalar=affected))
    ).authorize_on_behalf(
        actor=_requester_actor(),
        creator=RequesterRef(external_id="creator-person"),
        affected=RequesterRef(external_id="affected-person"),
        policy=registry_contracts.OnBehalfPolicyProjection(scope="exact_search_only"),
        lookup="Exact Search Person",
    )

    assert allowed.status == "allowed"
    assert allowed.affected.external_id == "affected-person"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_on_behalf_authorization_distinguishes_missing_affected_person() -> None:
    creator = _person(person_id="creator-person")

    outcome = await LocalRegistryAdapter(
        _Session(_Result(scalar=creator), _Result(scalar=None))
    ).authorize_on_behalf(
        actor=_requester_actor(),
        creator=RequesterRef(external_id="creator-person"),
        affected=RequesterRef(external_id="missing-person"),
        policy=registry_contracts.OnBehalfPolicyProjection(scope="any_employee"),
    )

    assert isinstance(outcome, RegistryNotFound)
    assert outcome.code == "registry_on_behalf_affected_not_found"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_unavailable_on_behalf_operations_are_typed_and_fail_closed() -> None:
    port = UnavailableRegistryPort()
    policy = registry_contracts.OnBehalfPolicyProjection(scope="same_department")
    actor = _requester_actor()
    creator = RequesterRef(external_id="creator-person")

    candidates = await port.on_behalf_candidates(
        actor=actor,
        creator=creator,
        policy=policy,
        query="Иван",
    )
    authorization = await port.authorize_on_behalf(
        actor=actor,
        creator=creator,
        affected=RequesterRef(external_id="affected-person"),
        policy=policy,
    )

    assert isinstance(candidates, RegistryUnavailable)
    assert isinstance(authorization, RegistryUnavailable)


@pytest.mark.no_db
def test_ticket_participant_contract_is_immutable_and_purpose_bound() -> None:
    projection = registry_contracts.TicketParticipantProjection(
        person={"external_id": "registry-ref-opaque-person-1"},
        display_name="Иван",
        full_name="Иван Иванов",
        email="ivan@example.test",
        department={"external_id": "registry-ref-opaque-department-1"},
        location={"external_id": "registry-ref-opaque-location-1"},
        source="external_authoritative",
    )

    assert projection.model_dump(mode="json") == {
        "person": {"external_id": "registry-ref-opaque-person-1"},
        "display_name": "Иван",
        "full_name": "Иван Иванов",
        "email": "ivan@example.test",
        "department": {"external_id": "registry-ref-opaque-department-1"},
        "location": {"external_id": "registry-ref-opaque-location-1"},
        "source": "external_authoritative",
    }
    with pytest.raises(ValueError):
        projection.email = "changed@example.test"
    with pytest.raises(ValueError):
        registry_contracts.TicketParticipantProjection(
            person={"external_id": "registry-ref-opaque-person-1"},
            source="local_authoritative",
            identity_id=123,
        )

    existing_text = "x" * 5000
    assert registry_contracts.TicketParticipantProjection(
        person={"external_id": "registry-ref-opaque-person-1"},
        full_name=existing_text,
        source="local_authoritative",
    ).full_name == existing_text


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_local_ticket_participant_preserves_existing_ticket_context_fields() -> None:
    person = _person()
    person.department_id = "registry-ref-opaque-department-1"
    person.location_id = "registry-ref-opaque-location-1"

    result = await LocalRegistryAdapter(_Session(_Result(scalar=person))).ticket_participant(
        PersonRef(external_id="registry-ref-opaque-person-1")
    )

    assert result.model_dump(mode="json") == {
        "person": {"external_id": "registry-ref-opaque-person-1"},
        "display_name": "Иван",
        "full_name": "Иван Иванов",
        "email": "ivan@example.test",
        "department": {"external_id": "registry-ref-opaque-department-1"},
        "location": {"external_id": "registry-ref-opaque-location-1"},
        "source": "local_authoritative",
    }
    assert "phone" not in result.model_dump(mode="json")


@pytest.mark.no_db
@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["archived", "disabled", "inactive", "merged"])
async def test_local_ticket_participant_preserves_existing_inactive_person(status: str) -> None:
    person = _person()
    person.status = status

    result = await LocalRegistryAdapter(_Session(_Result(scalar=person))).ticket_participant(
        PersonRef(external_id="registry-ref-opaque-person-1")
    )

    assert isinstance(result, registry_contracts.TicketParticipantProjection)
    assert result.person.external_id == "registry-ref-opaque-person-1"
    assert result.display_name == "Иван"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_local_ticket_participant_distinguishes_absent_person() -> None:
    result = await LocalRegistryAdapter(_Session(_Result(scalar=None))).ticket_participant(
        PersonRef(external_id="registry-ref-opaque-person-1")
    )

    assert isinstance(result, RegistryNotFound)
    assert result.code == "registry_ticket_participant_not_found"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_local_ticket_participant_rejects_malformed_person_ref() -> None:
    result = await LocalRegistryAdapter(
        _Session(_Result(scalar=_person(person_id=" ")))
    ).ticket_participant(PersonRef(external_id="registry-ref-opaque-person-1"))

    assert isinstance(result, RegistryInvalidProjection)
    assert result.code == "registry_projection_invalid"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_local_ticket_participant_maps_read_failure_to_typed_unavailable() -> None:
    result = await LocalRegistryAdapter(_FailThenRecoverSession()).ticket_participant(
        PersonRef(external_id="registry-ref-opaque-person-1")
    )

    assert isinstance(result, RegistryUnavailable)
    assert result.code == "registry_read_unavailable"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_unavailable_ticket_participant_is_typed_and_fail_closed() -> None:
    result = await UnavailableRegistryPort().ticket_participant(
        PersonRef(external_id="registry-ref-opaque-person-1")
    )

    assert isinstance(result, RegistryUnavailable)


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
