"""Versioned, redacted HTTP reads for the external Registry Platform."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
import logging
from typing import Any, TypeVar
from urllib.parse import quote, urlsplit
from uuid import uuid4

import aiohttp
from pydantic import BaseModel, ValidationError

try:
    from domain_ports.registry import RegistryAvailability, RegistryPort
    from domain_ports.registry_contracts import (
        AccountStatusOutcome,
        AccountStatusProjection,
        ActiveBindingOutcome,
        ActiveBindingProjection,
        AudienceProjection,
        AudienceProjectionOutcome,
        BindingRevocationRequest,
        DeviceContextOutcome,
        DeviceContextProjection,
        DeviceRef,
        InventoryQualityOutcome,
        InventoryQualityProjection,
        DirectorySearchOutcome,
        DirectorySearchProjection,
        DirectorySearchText,
        MAX_DIRECTORY_RESULTS,
        MAX_REQUESTER_HISTORY_EVENTS,
        PersonRef,
        RegistrationApprovalRequest,
        RegistrationRequest,
        RegistryCommandResult,
        RegistryInvalidProjection,
        RegistryNotFound,
        RegistryReadActor,
        RegistryUnavailable,
        RequesterHistoryOutcome,
        RequesterHistoryProjection,
        RequesterProfileOutcome,
        RequesterProfileProjection,
        RequesterSnapshot,
        RequesterSnapshotOutcome,
    )
except ModuleNotFoundError as exc:
    if exc.name not in {"domain_ports", "domain_ports.registry"}:
        raise
    from server.domain_ports.registry import RegistryAvailability, RegistryPort
    from server.domain_ports.registry_contracts import (
        AccountStatusOutcome,
        AccountStatusProjection,
        ActiveBindingOutcome,
        ActiveBindingProjection,
        AudienceProjection,
        AudienceProjectionOutcome,
        BindingRevocationRequest,
        DeviceContextOutcome,
        DeviceContextProjection,
        DeviceRef,
        InventoryQualityOutcome,
        InventoryQualityProjection,
        DirectorySearchOutcome,
        DirectorySearchProjection,
        DirectorySearchText,
        MAX_DIRECTORY_RESULTS,
        MAX_REQUESTER_HISTORY_EVENTS,
        PersonRef,
        RegistrationApprovalRequest,
        RegistrationRequest,
        RegistryCommandResult,
        RegistryInvalidProjection,
        RegistryNotFound,
        RegistryReadActor,
        RegistryUnavailable,
        RequesterHistoryOutcome,
        RequesterHistoryProjection,
        RequesterProfileOutcome,
        RequesterProfileProjection,
        RequesterSnapshot,
        RequesterSnapshotOutcome,
    )


logger = logging.getLogger(__name__)
_T = TypeVar("_T", bound=BaseModel)
_SERVICE_SCOPE = "registry.helpdesk.read.v1"
_UNAVAILABLE = RegistryUnavailable()


def _new_correlation_id() -> str:
    return str(uuid4())


def _path_ref(value: str) -> str:
    return quote(value, safe="")


def _external_source(payload: Mapping[str, object], *, nested: tuple[str, ...] = ()) -> dict[str, object]:
    """Copy an API payload and set only locally-owned source labels."""

    result = dict(payload)
    result["source"] = "external_authoritative"
    for key in nested:
        value = result.get(key)
        if isinstance(value, Mapping):
            result[key] = _external_source(value)
        elif isinstance(value, list):
            result[key] = [
                _external_source(item) if isinstance(item, Mapping) else item for item in value
            ]
    return result


class ExternalRegistryHttpAdapter:
    """Read-only Registry Platform v1 client.

    The adapter never logs payloads, URLs or headers.  The Registry platform
    owns authorization; Helpdesk supplies only the fixed service scope and a
    fresh correlation id for each request.  Commands remain delegated to the
    supplied local compatibility port until Task 7 explicitly cuts them over.
    """

    def __init__(
        self,
        *,
        base_url: str,
        service_token: str,
        timeout_seconds: float,
        command_port: RegistryPort | None = None,
        correlation_id_factory: Callable[[], str] = _new_correlation_id,
        allow_insecure_test_url: bool = False,
    ) -> None:
        self._base_url = str(base_url or "").rstrip("/")
        self._service_token = str(service_token or "")
        self._timeout_seconds = max(0.05, min(float(timeout_seconds), 10.0))
        self._command_port = command_port
        self._correlation_id_factory = correlation_id_factory
        self._allow_insecure_test_url = bool(allow_insecure_test_url)

    @property
    def configured(self) -> bool:
        return bool(self._service_token and self._is_allowed_base_url())

    def _is_allowed_base_url(self) -> bool:
        parsed = urlsplit(self._base_url)
        if not parsed.netloc:
            return False
        if parsed.scheme == "https":
            return True
        # aiohttp's in-process TestServer is HTTP-only.  This escape hatch is
        # constructor-only, deliberately absent from environment configuration.
        return self._allow_insecure_test_url and parsed.scheme == "http"

    @staticmethod
    def _bounded_limit(limit: int, *, maximum: int) -> int | None:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            return None
        return min(limit, maximum)

    def _headers(self, correlation_id: str) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._service_token}",
            "X-Registry-Service-Scope": _SERVICE_SCOPE,
            "X-Correlation-ID": correlation_id,
        }

    async def _get(
        self,
        path: str,
        *,
        params: Mapping[str, str | int] | None = None,
        not_found_code: str | None = None,
    ) -> Mapping[str, object] | RegistryUnavailable | RegistryNotFound | RegistryInvalidProjection:
        if not self.configured:
            return RegistryUnavailable(code="registry_external_unconfigured")
        correlation_id = self._correlation_id_factory()
        try:
            timeout = aiohttp.ClientTimeout(total=self._timeout_seconds)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"{self._base_url}{path}",
                    params=params,
                    headers=self._headers(correlation_id),
                ) as response:
                    if response.status == 404 and not_found_code is not None:
                        return RegistryNotFound(code=not_found_code)
                    if response.status != 200:
                        return _UNAVAILABLE
                    envelope = await response.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            return _UNAVAILABLE
        if (
            not isinstance(envelope, Mapping)
            or set(envelope) != {"data", "correlation_id"}
            or not isinstance(envelope.get("correlation_id"), str)
            or envelope["correlation_id"] != correlation_id
        ):
            return RegistryInvalidProjection()
        data = envelope.get("data")
        return dict(data) if isinstance(data, Mapping) else RegistryInvalidProjection()

    @staticmethod
    def _parse(
        payload: Mapping[str, object] | RegistryUnavailable | RegistryNotFound | RegistryInvalidProjection,
        model: type[_T],
        *,
        nested_sources: tuple[str, ...] = (),
    ) -> _T | RegistryUnavailable | RegistryNotFound | RegistryInvalidProjection:
        if not isinstance(payload, Mapping):
            return payload
        try:
            prepared: Mapping[str, object]
            if model is RequesterSnapshot:
                prepared = payload
            else:
                prepared = _external_source(payload, nested=nested_sources)
            return model.model_validate(prepared)
        except ValidationError:
            return RegistryInvalidProjection()

    @staticmethod
    def _actor_params(actor: RegistryReadActor) -> dict[str, str]:
        params = {
            "actor_ref": actor.actor.external_id,
            "actor_role": actor.role,
        }
        if actor.requester is not None:
            params["requester_ref"] = actor.requester.external_id
        return params

    async def availability(self) -> RegistryAvailability:
        result = await self._get("/v1/helpdesk/availability")
        return RegistryAvailability(
            status="available" if isinstance(result, Mapping) else "unavailable",
            code="registry_external" if isinstance(result, Mapping) else "registry_unavailable",
        )

    async def requester_snapshot(self, person: PersonRef) -> RequesterSnapshotOutcome:
        return self._parse(
            await self._get(
                f"/v1/helpdesk/requesters/{_path_ref(person.external_id)}/snapshot",
                not_found_code="registry_requester_not_found",
            ),
            RequesterSnapshot,
        )

    async def active_binding(self, device: DeviceRef) -> ActiveBindingOutcome:
        return self._parse(
            await self._get(
                f"/v1/helpdesk/devices/{_path_ref(device.external_id)}/active-binding",
                not_found_code="registry_active_binding_not_found",
            ),
            ActiveBindingProjection,
        )

    async def account_status(self, device: DeviceRef) -> AccountStatusOutcome:
        return self._parse(
            await self._get(f"/v1/helpdesk/devices/{_path_ref(device.external_id)}/account-status"),
            AccountStatusProjection,
            nested_sources=("active_binding",),
        )

    async def audience_projection(
        self, person: PersonRef, *, actor: RegistryReadActor
    ) -> AudienceProjectionOutcome:
        return self._parse(
            await self._get(
                f"/v1/helpdesk/requesters/{_path_ref(person.external_id)}/audience",
                params=self._actor_params(actor),
                not_found_code="registry_requester_not_found",
            ),
            AudienceProjection,
        )

    async def requester_profile(
        self, person: PersonRef, *, actor: RegistryReadActor
    ) -> RequesterProfileOutcome:
        return self._parse(
            await self._get(
                f"/v1/helpdesk/requesters/{_path_ref(person.external_id)}/profile",
                params=self._actor_params(actor),
                not_found_code="registry_requester_not_found",
            ),
            RequesterProfileProjection,
        )

    async def search_people(
        self, query: DirectorySearchText, *, actor: RegistryReadActor, limit: int = 20
    ) -> DirectorySearchOutcome:
        bounded_limit = self._bounded_limit(limit, maximum=MAX_DIRECTORY_RESULTS)
        if bounded_limit is None:
            return RegistryInvalidProjection()
        params: dict[str, str | int] = {"q": query, "limit": bounded_limit}
        params.update(self._actor_params(actor))
        return self._parse(
            await self._get("/v1/helpdesk/directory/people", params=params),
            DirectorySearchProjection,
            nested_sources=("items",),
        )

    async def device_context(self, device: DeviceRef) -> DeviceContextOutcome:
        return self._parse(
            await self._get(
                f"/v1/helpdesk/devices/{_path_ref(device.external_id)}/context",
                not_found_code="registry_device_not_found",
            ),
            DeviceContextProjection,
        )

    async def inventory_quality(self) -> InventoryQualityOutcome:
        payload = await self._get("/v1/helpdesk/inventory-quality")
        if isinstance(payload, Mapping) and set(payload) != {"active_pc_without_location_count"}:
            return RegistryInvalidProjection()
        return self._parse(
            payload,
            InventoryQualityProjection,
        )

    async def requester_history(
        self, person: PersonRef, *, actor: RegistryReadActor, limit: int = 50
    ) -> RequesterHistoryOutcome:
        bounded_limit = self._bounded_limit(limit, maximum=MAX_REQUESTER_HISTORY_EVENTS)
        if bounded_limit is None:
            return RegistryInvalidProjection()
        params: dict[str, str | int] = {"limit": bounded_limit}
        params.update(self._actor_params(actor))
        return self._parse(
            await self._get(
                f"/v1/helpdesk/requesters/{_path_ref(person.external_id)}/history",
                params=params,
                not_found_code="registry_requester_not_found",
            ),
            RequesterHistoryProjection,
            nested_sources=("items",),
        )

    async def request_registration(self, request: RegistrationRequest) -> RegistryCommandResult:
        return await self._command("request_registration", request)

    async def approve_registration(self, request: RegistrationApprovalRequest) -> RegistryCommandResult:
        return await self._command("approve_registration", request)

    async def revoke_binding(self, request: BindingRevocationRequest) -> RegistryCommandResult:
        return await self._command("revoke_binding", request)

    async def _command(self, method: str, request: Any) -> RegistryCommandResult:
        if self._command_port is not None:
            return await getattr(self._command_port, method)(request)
        return RegistryCommandResult(
            operation_id=request.operation_id,
            status="unavailable",
            code="registry_command_not_composed",
            idempotency_status="not_evaluated",
        )


class ShadowReadRegistryPort:
    """Return local reads immediately while observing redacted external parity."""

    def __init__(
        self,
        *,
        authoritative: RegistryPort,
        shadow: RegistryPort,
        mismatch_reporter: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self._authoritative = authoritative
        self._shadow = shadow
        self._mismatch_reporter = mismatch_reporter or self._log_mismatch
        self._tasks: set[asyncio.Task[None]] = set()

    @staticmethod
    def _log_mismatch(evidence: dict[str, object]) -> None:
        logger.warning(
            "registry_port_shadow_mismatch operation=%s outcome=%s fields=%s",
            evidence["operation"],
            evidence["outcome"],
            evidence["fields"],
        )

    @staticmethod
    def _projection_payload(value: object) -> tuple[str, dict[str, object]]:
        if not isinstance(value, BaseModel):
            return type(value).__name__, {}
        payload = value.model_dump(mode="json")

        def remove_sources(item: object) -> object:
            if isinstance(item, dict):
                return {key: remove_sources(value) for key, value in item.items() if key != "source"}
            if isinstance(item, list):
                return [remove_sources(entry) for entry in item]
            return item

        redacted = remove_sources(payload)
        return type(value).__name__, redacted if isinstance(redacted, dict) else {}

    @classmethod
    def _different_fields(cls, local: object, external: object) -> tuple[str, ...]:
        local_kind, local_payload = cls._projection_payload(local)
        external_kind, external_payload = cls._projection_payload(external)
        if local_kind != external_kind:
            return ("outcome",)
        return tuple(
            key
            for key in sorted(set(local_payload) | set(external_payload))
            if local_payload.get(key) != external_payload.get(key)
        )

    def _schedule(self, operation: str, local: object, external: Awaitable[object]) -> None:
        async def compare() -> None:
            try:
                external_result = await external
                fields = self._different_fields(local, external_result)
                if fields:
                    self._mismatch_reporter(
                        {
                            "operation": operation,
                            "outcome": "mismatch",
                            "fields": fields,
                        }
                    )
            except Exception:
                logger.warning(
                    "registry_port_shadow_compare_failed operation=%s",
                    operation,
                )

        task = asyncio.create_task(compare())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def availability(self) -> RegistryAvailability:
        return await self._authoritative.availability()

    async def requester_snapshot(self, person: PersonRef) -> RequesterSnapshotOutcome:
        local = await self._authoritative.requester_snapshot(person)
        self._schedule("requester_snapshot", local, self._shadow.requester_snapshot(person))
        return local

    async def active_binding(self, device: DeviceRef) -> ActiveBindingOutcome:
        local = await self._authoritative.active_binding(device)
        self._schedule("active_binding", local, self._shadow.active_binding(device))
        return local

    async def account_status(self, device: DeviceRef) -> AccountStatusOutcome:
        local = await self._authoritative.account_status(device)
        self._schedule("account_status", local, self._shadow.account_status(device))
        return local

    async def audience_projection(
        self, person: PersonRef, *, actor: RegistryReadActor
    ) -> AudienceProjectionOutcome:
        local = await self._authoritative.audience_projection(person, actor=actor)
        self._schedule("audience_projection", local, self._shadow.audience_projection(person, actor=actor))
        return local

    async def requester_profile(
        self, person: PersonRef, *, actor: RegistryReadActor
    ) -> RequesterProfileOutcome:
        local = await self._authoritative.requester_profile(person, actor=actor)
        self._schedule("requester_profile", local, self._shadow.requester_profile(person, actor=actor))
        return local

    async def search_people(
        self, query: DirectorySearchText, *, actor: RegistryReadActor, limit: int = 20
    ) -> DirectorySearchOutcome:
        local = await self._authoritative.search_people(query, actor=actor, limit=limit)
        self._schedule("search_people", local, self._shadow.search_people(query, actor=actor, limit=limit))
        return local

    async def device_context(self, device: DeviceRef) -> DeviceContextOutcome:
        local = await self._authoritative.device_context(device)
        self._schedule("device_context", local, self._shadow.device_context(device))
        return local

    async def inventory_quality(self) -> InventoryQualityOutcome:
        local = await self._authoritative.inventory_quality()
        self._schedule("inventory_quality", local, self._shadow.inventory_quality())
        return local

    async def requester_history(
        self, person: PersonRef, *, actor: RegistryReadActor, limit: int = 50
    ) -> RequesterHistoryOutcome:
        local = await self._authoritative.requester_history(person, actor=actor, limit=limit)
        self._schedule("requester_history", local, self._shadow.requester_history(person, actor=actor, limit=limit))
        return local

    async def request_registration(self, request: RegistrationRequest) -> RegistryCommandResult:
        return await self._authoritative.request_registration(request)

    async def approve_registration(self, request: RegistrationApprovalRequest) -> RegistryCommandResult:
        return await self._authoritative.approve_registration(request)

    async def revoke_binding(self, request: BindingRevocationRequest) -> RegistryCommandResult:
        return await self._authoritative.revoke_binding(request)
