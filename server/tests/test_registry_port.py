from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import pytest

from domain_ports import (
    ActorRef,
    BindingRef,
    BindingRevocationRequest,
    DeviceRef,
    DomainPortContainer,
    PersonRef,
    RegistrationApprovalRequest,
    RegistrationRef,
    RegistrationRequest,
    RegistryNotFound,
    RegistryPort,
    RegistryReadActor,
    RegistryUnavailable,
    UnavailableRegistryPort,
)
from registry_adapter import LocalRegistryAdapter, ShadowReadRegistryPort


pytestmark = pytest.mark.no_db
WORKSPACE = Path(__file__).resolve().parents[2]


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


class _SequencedSession:
    def __init__(
        self,
        *results: _Result,
        get_rows: dict[str, object | None] | None = None,
    ) -> None:
        self._results = list(results)
        self._get_rows = dict(get_rows or {})

    async def execute(self, _statement: object) -> _Result:
        if not self._results:
            raise AssertionError("unexpected Registry query")
        return self._results.pop(0)

    async def get(self, _model: object, key: str) -> object | None:
        return self._get_rows.get(str(key))


def _person(*, person_id: str = "registry-ref-opaque-person-1") -> SimpleNamespace:
    return SimpleNamespace(
        person_id=person_id,
        display_name="Requester One",
        full_name="Requester One",
        email="requester@example.test",
        phone="+1-555-0100",
        status="active",
        department_id=None,
        location_id=None,
    )


def _binding() -> SimpleNamespace:
    return SimpleNamespace(
        binding_id="registry-ref-opaque-binding-1",
        device_id="registry-ref-opaque-device-1",
        asset_id="registry-ref-opaque-asset-1",
        person_id="registry-ref-opaque-person-1",
        relationship_type="primary_user",
        status="active",
        confirmed_at=None,
        confirmed_by_admin=None,
    )


def _support_actor() -> RegistryReadActor:
    return RegistryReadActor(
        actor=ActorRef(external_id="registry-ref-opaque-support-1"),
        role="support",
    )


def _assert_no_local_identifiers(payload: Any) -> None:
    if isinstance(payload, dict):
        assert not {
            "person_id",
            "device_id",
            "binding_id",
            "claim_id",
            "asset_id",
            "audience_group_id",
            "session_id",
        }.intersection(payload)
        for value in payload.values():
            _assert_no_local_identifiers(value)
    elif isinstance(payload, list):
        for value in payload:
            _assert_no_local_identifiers(value)


@pytest.mark.asyncio
async def test_local_adapter_returns_redacted_requester_snapshot() -> None:
    session = _SequencedSession(_Result(scalar=_person()))

    result = await LocalRegistryAdapter(session).requester_snapshot(
        PersonRef(external_id="registry-ref-opaque-person-1")
    )

    assert result.model_dump(mode="json") == {
        "person": {"external_id": "registry-ref-opaque-person-1"},
        "display_name": "Requester One",
    }
    assert "email" not in result.model_dump(mode="json")


@pytest.mark.asyncio
async def test_local_adapter_returns_opaque_binding_without_local_ids() -> None:
    session = _SequencedSession(
        _Result(scalar=_binding()),
        _Result(scalar=_person()),
    )

    result = await LocalRegistryAdapter(session).active_binding(
        DeviceRef(external_id="registry-ref-opaque-device-1")
    )
    payload = result.model_dump(mode="json")

    assert result.binding.external_id == "registry-ref-opaque-binding-1"
    assert result.requester.external_id == "registry-ref-opaque-person-1"
    assert result.source == "local_authoritative"
    _assert_no_local_identifiers(payload)


@pytest.mark.asyncio
async def test_local_adapter_account_status_is_redacted() -> None:
    binding = _binding()
    session = _SequencedSession(
        _Result(scalar=binding),
        _Result(rows=[binding]),
        _Result(rows=[]),
        _Result(scalar=_person()),
    )

    result = await LocalRegistryAdapter(session).account_status(
        DeviceRef(external_id="registry-ref-opaque-device-1")
    )
    payload = result.model_dump(mode="json")

    assert result.status == "admin_confirmed"
    assert result.active_binding is not None
    assert result.active_binding.binding.external_id == "registry-ref-opaque-binding-1"
    _assert_no_local_identifiers(payload)


@pytest.mark.asyncio
async def test_local_adapter_audience_projection_exposes_only_opaque_audience_refs() -> None:
    group = SimpleNamespace(
        audience_group_id="registry-ref-opaque-audience-1",
        code="support_requesters",
    )
    membership = SimpleNamespace(
        member_type="person",
        member_id="registry-ref-opaque-person-1",
        include_children=False,
    )
    session = _SequencedSession(
        _Result(rows=[]),
        _Result(rows=[(group, membership)]),
        get_rows={"registry-ref-opaque-person-1": _person()},
    )

    result = await LocalRegistryAdapter(session).audience_projection(
        PersonRef(external_id="registry-ref-opaque-person-1"),
        actor=_support_actor(),
    )
    payload = result.model_dump(mode="json")

    assert [ref.external_id for ref in result.audiences] == ["support_requesters"]
    assert result.source == "local_authoritative"
    _assert_no_local_identifiers(payload)


@pytest.mark.asyncio
async def test_local_adapter_returns_not_found_for_missing_requester() -> None:
    result = await LocalRegistryAdapter(_SequencedSession(_Result(scalar=None))).requester_snapshot(
        PersonRef(external_id="registry-ref-opaque-missing")
    )

    assert isinstance(result, RegistryNotFound)
    assert result.code == "registry_requester_not_found"


def _registration_request() -> RegistrationRequest:
    return RegistrationRequest(
        operation_id="registry-operation-request-1",
        device=DeviceRef(external_id="registry-ref-opaque-device-1"),
    )


@pytest.mark.asyncio
async def test_unavailable_registry_commands_fail_closed_with_caller_operation_id() -> None:
    port = UnavailableRegistryPort()
    registration = _registration_request()

    results = (
        await port.request_registration(registration),
        await port.approve_registration(
            RegistrationApprovalRequest(
                operation_id="registry-operation-approve-1",
                registration=RegistrationRef(external_id="registry-ref-opaque-registration-1"),
            )
        ),
        await port.revoke_binding(
            BindingRevocationRequest(
                operation_id="registry-operation-revoke-1",
                binding=BindingRef(external_id="registry-ref-opaque-binding-1"),
                reason_code="administrative_revoke",
            )
        ),
    )

    assert [result.operation_id for result in results] == [
        "registry-operation-request-1",
        "registry-operation-approve-1",
        "registry-operation-revoke-1",
    ]
    assert all(result.status == "unavailable" for result in results)
    assert all(result.code == "registry_unavailable" for result in results)


@pytest.mark.asyncio
async def test_local_registry_commands_are_explicitly_not_composed_and_repeatable() -> None:
    adapter = LocalRegistryAdapter(_SequencedSession())
    registration = _registration_request()
    approval = RegistrationApprovalRequest(
        operation_id="registry-operation-approve-1",
        registration=RegistrationRef(external_id="registry-ref-opaque-registration-1"),
    )
    revocation = BindingRevocationRequest(
        operation_id="registry-operation-revoke-1",
        binding=BindingRef(external_id="registry-ref-opaque-binding-1"),
        reason_code="administrative_revoke",
    )

    first = (
        await adapter.request_registration(registration),
        await adapter.approve_registration(approval),
        await adapter.revoke_binding(revocation),
    )
    second = (
        await adapter.request_registration(registration),
        await adapter.approve_registration(approval),
        await adapter.revoke_binding(revocation),
    )

    assert first == second
    assert [result.operation_id for result in first] == [
        "registry-operation-request-1",
        "registry-operation-approve-1",
        "registry-operation-revoke-1",
    ]
    assert all(result.status == "unavailable" for result in first)
    assert all(result.code == "registry_command_not_composed" for result in first)


def test_registration_command_requires_caller_operation_id() -> None:
    with pytest.raises(ValueError):
        RegistrationRequest(  # type: ignore[call-arg]
            device=DeviceRef(external_id="registry-ref-opaque-device-1")
        )


@pytest.mark.asyncio
async def test_unavailable_registry_port_fails_closed_for_every_read() -> None:
    port = UnavailableRegistryPort()

    results = (
        await port.requester_snapshot(PersonRef(external_id="registry-ref-opaque-person-1")),
        await port.active_binding(DeviceRef(external_id="registry-ref-opaque-device-1")),
        await port.account_status(DeviceRef(external_id="registry-ref-opaque-device-1")),
        await port.audience_projection(
            PersonRef(external_id="registry-ref-opaque-person-1"),
            actor=_support_actor(),
        ),
    )

    assert isinstance(port, RegistryPort)
    assert all(isinstance(result, RegistryUnavailable) for result in results)
    assert all(result.code == "registry_unavailable" for result in results)


@pytest.mark.asyncio
async def test_registry_container_composes_all_modes_without_external_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("config.REGISTRY_PORT_MODE", "local")
    local = DomainPortContainer.from_config(registry_session=_SequencedSession()).registry
    unavailable = DomainPortContainer.from_config(registry_mode="unavailable").registry
    external = DomainPortContainer.from_config(registry_mode="external").registry

    assert isinstance(local, LocalRegistryAdapter)
    assert isinstance(unavailable, UnavailableRegistryPort)
    external_status = await external.availability()
    assert external_status.status == "unavailable"
    assert external_status.code == "registry_external_unconfigured"


def test_registry_container_external_mode_always_keeps_local_reads_authoritative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("config.REGISTRY_EXTERNAL_BASE_URL", "https://registry.example.test")
    monkeypatch.setattr("config.REGISTRY_EXTERNAL_SERVICE_TOKEN", "test-service-token")
    registry = DomainPortContainer.from_config(
        registry_mode="external",
        registry_session=_SequencedSession(),
    ).registry

    assert isinstance(registry, ShadowReadRegistryPort)
    assert isinstance(registry._authoritative, LocalRegistryAdapter)


def test_registry_container_composes_from_repository_package_import() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from server.domain_ports import DomainPortContainer; "
                "print(type(DomainPortContainer.from_config()).__name__)"
            ),
        ],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "DomainPortContainer"
