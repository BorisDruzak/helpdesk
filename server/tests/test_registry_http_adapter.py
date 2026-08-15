from __future__ import annotations

from aiohttp import web
from aiohttp.test_utils import TestServer
import pytest

from domain_ports import (
    ActorRef,
    DirectorySearchText,
    PersonRef,
    RegistryInvalidProjection,
    RegistryNotFound,
    RegistryObserverReadContext,
    RegistryReadActor,
    RegistryUnavailable,
    RequesterRef,
)
import domain_ports.registry_contracts as registry_contracts
from registry_adapter.http import ExternalRegistryHttpAdapter


pytestmark = pytest.mark.no_db


def _requester_actor() -> RegistryReadActor:
    return RegistryReadActor(
        actor=ActorRef(external_id="verified-ui-user"),
        role="user",
        requester=RequesterRef(external_id="creator-person"),
    )


@pytest.mark.asyncio
async def test_http_adapter_reads_exact_on_behalf_candidate_projection_and_context() -> None:
    received_query: dict[str, str] = {}

    async def candidates(request: web.Request) -> web.Response:
        received_query.update(request.query)
        return web.json_response(
            {
                "data": {
                    "items": [
                        {
                            "person": {"external_id": "affected-person"},
                            "display_name": "Affected Person",
                            "full_name": "Affected Person Full",
                            "email": "affected@example.test",
                            "department": {"external_id": "department-1"},
                            "department_label": "Support",
                            "location": {"external_id": "location-1"},
                            "location_label": "Office 1",
                        }
                    ]
                },
                "correlation_id": "registry-correlation-on-behalf-candidates",
            }
        )

    app = web.Application()
    app.router.add_get(
        "/v1/helpdesk/requesters/{creator_ref}/on-behalf/candidates",
        candidates,
    )
    server = TestServer(app)
    await server.start_server()
    try:
        result = await ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-on-behalf-candidates",
            allow_insecure_test_url=True,
        ).on_behalf_candidates(
            actor=_requester_actor(),
            creator=RequesterRef(external_id="creator-person"),
            policy=registry_contracts.OnBehalfPolicyProjection(
                allowed=True,
                scope="same_department",
                reason_required=True,
            ),
            query="Affected",
        )

        assert result.items[0].model_dump(mode="json") == {
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
        assert received_query == {
            "actor_ref": "verified-ui-user",
            "actor_role": "user",
            "requester_ref": "creator-person",
            "policy_allowed": "true",
            "policy_scope": "same_department",
            "policy_reason_required": "true",
            "q": "Affected",
        }
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http_adapter_rejects_on_behalf_candidate_source_before_injection() -> None:
    async def candidates(_request: web.Request) -> web.Response:
        return web.json_response(
            {
                "data": {
                    "items": [
                        {
                            "person": {"external_id": "affected-person"},
                            "display_name": "Affected Person",
                            "full_name": None,
                            "email": None,
                            "department": None,
                            "department_label": None,
                            "location": None,
                            "location_label": None,
                            "source": "external_authoritative",
                        }
                    ]
                },
                "correlation_id": "registry-correlation-on-behalf-extra",
            }
        )

    app = web.Application()
    app.router.add_get(
        "/v1/helpdesk/requesters/{creator_ref}/on-behalf/candidates",
        candidates,
    )
    server = TestServer(app)
    await server.start_server()
    try:
        result = await ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-on-behalf-extra",
            allow_insecure_test_url=True,
        ).on_behalf_candidates(
            actor=_requester_actor(),
            creator=RequesterRef(external_id="creator-person"),
            policy=registry_contracts.OnBehalfPolicyProjection(scope="any_employee"),
            query="Affected",
        )

        assert isinstance(result, RegistryInvalidProjection)
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http_adapter_reads_exact_observer_profile_completion_projection() -> None:
    received_headers: dict[str, str] = {}

    async def profile_completion(request: web.Request) -> web.Response:
        received_headers.update(request.headers)
        return web.json_response(
            {
                "data": {
                    "person": {"external_id": "person-1"},
                    "complete": False,
                    "blocks": True,
                    "status": "required",
                    "missing_field_keys": ["phone"],
                },
                "correlation_id": "registry-correlation-observer-profile-completion",
            }
        )

    app = web.Application()
    app.router.add_get(
        "/v1/helpdesk/observer/requesters/{person_ref}/profile-completion",
        profile_completion,
    )
    server = TestServer(app)
    await server.start_server()
    try:
        result = await ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-observer-profile-completion",
            allow_insecure_test_url=True,
        ).requester_profile_completion(
            RegistryObserverReadContext(source="observer.web_cabinet"),
            RequesterRef(external_id="person-1"),
        )

        assert result.model_dump(mode="json") == {
            "person": {"external_id": "person-1"},
            "complete": False,
            "blocks": True,
            "status": "required",
            "missing_field_keys": ["phone"],
            "source": "external_authoritative",
        }
        assert received_headers["X-Registry-Service-Scope"] == "registry.helpdesk.read.v1"
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http_adapter_rejects_incoherent_observer_profile_completion_projection() -> None:
    async def profile_completion(_request: web.Request) -> web.Response:
        return web.json_response(
            {
                "data": {
                    "person": {"external_id": "person-1"},
                    "complete": True,
                    "blocks": False,
                    "status": "complete",
                    "missing_field_keys": ["phone"],
                },
                "correlation_id": "registry-correlation-observer-profile-completion-invalid",
            }
        )

    app = web.Application()
    app.router.add_get(
        "/v1/helpdesk/observer/requesters/{person_ref}/profile-completion",
        profile_completion,
    )
    server = TestServer(app)
    await server.start_server()
    try:
        result = await ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-observer-profile-completion-invalid",
            allow_insecure_test_url=True,
        ).requester_profile_completion(
            RegistryObserverReadContext(source="observer.web_cabinet"),
            RequesterRef(external_id="person-1"),
        )

        assert isinstance(result, RegistryInvalidProjection)
    finally:
        await server.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("data", "correlation_id", "expected_type"),
    [
        (
            {"status": "not_found", "code": "registry_requester_not_found"},
            "registry-correlation-observer-profile-completion-not-found",
            RegistryNotFound,
        ),
        (
            {"status": "not_found", "code": "unexpected_not_found"},
            "registry-correlation-observer-profile-completion-not-found",
            RegistryInvalidProjection,
        ),
        (
            {"status": "not_found", "code": "registry_requester_not_found"},
            "wrong-registry-correlation",
            RegistryInvalidProjection,
        ),
    ],
    ids=("valid", "malformed", "wrong-correlation"),
)
async def test_http_adapter_validates_observer_profile_completion_not_found_envelope(
    data: dict[str, str],
    correlation_id: str,
    expected_type: type[RegistryNotFound] | type[RegistryInvalidProjection],
) -> None:
    async def profile_completion(_request: web.Request) -> web.Response:
        return web.json_response(
            {"data": data, "correlation_id": correlation_id},
            status=404,
        )

    app = web.Application()
    app.router.add_get(
        "/v1/helpdesk/observer/requesters/{person_ref}/profile-completion",
        profile_completion,
    )
    server = TestServer(app)
    await server.start_server()
    try:
        result = await ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-observer-profile-completion-not-found",
            allow_insecure_test_url=True,
        ).requester_profile_completion(
            RegistryObserverReadContext(source="observer.web_cabinet"),
            RequesterRef(external_id="person-1"),
        )

        assert isinstance(result, expected_type)
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http_adapter_authorize_on_behalf_sends_exact_lookup_and_parses_allowed() -> None:
    received_query: dict[str, str] = {}

    async def authorize(request: web.Request) -> web.Response:
        received_query.update(request.query)
        return web.json_response(
            {
                "data": {
                    "status": "allowed",
                    "code": "registry_on_behalf_allowed",
                    "affected": {"external_id": "affected-person"},
                },
                "correlation_id": "registry-correlation-on-behalf-authorize",
            }
        )

    app = web.Application()
    app.router.add_get(
        "/v1/helpdesk/requesters/{creator_ref}/on-behalf/{affected_ref}/authorize",
        authorize,
    )
    server = TestServer(app)
    await server.start_server()
    try:
        result = await ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-on-behalf-authorize",
            allow_insecure_test_url=True,
        ).authorize_on_behalf(
            actor=_requester_actor(),
            creator=RequesterRef(external_id="creator-person"),
            affected=RequesterRef(external_id="affected-person"),
            policy=registry_contracts.OnBehalfPolicyProjection(scope="exact_search_only"),
            lookup="Exact Search Person",
        )

        assert result.status == "allowed"
        assert result.affected.external_id == "affected-person"
        assert received_query["lookup"] == "Exact Search Person"
        assert received_query["actor_ref"] == "verified-ui-user"
        assert received_query["requester_ref"] == "creator-person"
        assert received_query["policy_scope"] == "exact_search_only"
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http_adapter_rejects_overlong_on_behalf_lookup_before_request() -> None:
    received = False

    async def authorize(_request: web.Request) -> web.Response:
        nonlocal received
        received = True
        return web.json_response({})

    app = web.Application()
    app.router.add_get(
        "/v1/helpdesk/requesters/{creator_ref}/on-behalf/{affected_ref}/authorize",
        authorize,
    )
    server = TestServer(app)
    await server.start_server()
    try:
        result = await ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            allow_insecure_test_url=True,
        ).authorize_on_behalf(
            actor=_requester_actor(),
            creator=RequesterRef(external_id="creator-person"),
            affected=RequesterRef(external_id="affected-person"),
            policy=registry_contracts.OnBehalfPolicyProjection(scope="exact_search_only"),
            lookup="x" * 241,
        )

        assert isinstance(result, RegistryInvalidProjection)
        assert received is False
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http_adapter_directory_search_denies_requester_before_request() -> None:
    received = False

    async def directory(_request: web.Request) -> web.Response:
        nonlocal received
        received = True
        return web.json_response({})

    app = web.Application()
    app.router.add_get("/v1/helpdesk/directory/people", directory)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            allow_insecure_test_url=True,
        ).search_people("requester", actor=_requester_actor())

        assert isinstance(result, RegistryUnavailable)
        assert result.code == "registry_actor_forbidden"
        assert received is False
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http_adapter_rejects_allowed_on_behalf_with_non_allowed_code() -> None:
    async def authorize(_request: web.Request) -> web.Response:
        return web.json_response(
            {
                "data": {
                    "status": "allowed",
                    "code": "registry_on_behalf_scope_denied",
                    "affected": {"external_id": "affected-person"},
                },
                "correlation_id": "registry-correlation-on-behalf-wrong-code",
            }
        )

    app = web.Application()
    app.router.add_get(
        "/v1/helpdesk/requesters/{creator_ref}/on-behalf/{affected_ref}/authorize",
        authorize,
    )
    server = TestServer(app)
    await server.start_server()
    try:
        result = await ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-on-behalf-wrong-code",
            allow_insecure_test_url=True,
        ).authorize_on_behalf(
            actor=_requester_actor(),
            creator=RequesterRef(external_id="creator-person"),
            affected=RequesterRef(external_id="affected-person"),
            policy=registry_contracts.OnBehalfPolicyProjection(scope="any_employee"),
        )

        assert isinstance(result, RegistryInvalidProjection)
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http_adapter_rejects_denied_on_behalf_with_unknown_code() -> None:
    async def authorize(_request: web.Request) -> web.Response:
        return web.json_response(
            {
                "data": {"status": "denied", "code": "registry_unknown_denial"},
                "correlation_id": "registry-correlation-on-behalf-unknown-denial",
            }
        )

    app = web.Application()
    app.router.add_get(
        "/v1/helpdesk/requesters/{creator_ref}/on-behalf/{affected_ref}/authorize",
        authorize,
    )
    server = TestServer(app)
    await server.start_server()
    try:
        result = await ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-on-behalf-unknown-denial",
            allow_insecure_test_url=True,
        ).authorize_on_behalf(
            actor=_requester_actor(),
            creator=RequesterRef(external_id="creator-person"),
            affected=RequesterRef(external_id="affected-person"),
            policy=registry_contracts.OnBehalfPolicyProjection(scope="any_employee"),
        )

        assert isinstance(result, RegistryInvalidProjection)
    finally:
        await server.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "not_found_code",
    [
        "registry_on_behalf_creator_not_found",
        "registry_on_behalf_affected_not_found",
    ],
)
async def test_http_adapter_preserves_correlated_on_behalf_not_found_code(
    not_found_code: str,
) -> None:
    async def authorize(_request: web.Request) -> web.Response:
        return web.json_response(
            {
                "data": {"status": "not_found", "code": not_found_code},
                "correlation_id": "registry-correlation-on-behalf-not-found",
            },
            status=404,
        )

    app = web.Application()
    app.router.add_get(
        "/v1/helpdesk/requesters/{creator_ref}/on-behalf/{affected_ref}/authorize",
        authorize,
    )
    server = TestServer(app)
    await server.start_server()
    try:
        result = await ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-on-behalf-not-found",
            allow_insecure_test_url=True,
        ).authorize_on_behalf(
            actor=_requester_actor(),
            creator=RequesterRef(external_id="creator-person"),
            affected=RequesterRef(external_id="affected-person"),
            policy=registry_contracts.OnBehalfPolicyProjection(scope="any_employee"),
        )

        assert isinstance(result, RegistryNotFound)
        assert result.code == not_found_code
    finally:
        await server.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "not_found_data",
    [
        {"status": "not_found", "code": "registry_unknown_not_found"},
        {
            "status": "not_found",
            "code": "registry_on_behalf_creator_not_found",
            "creator": {"external_id": "must-not-be-accepted"},
        },
    ],
)
async def test_http_adapter_rejects_malformed_on_behalf_not_found_envelope(
    not_found_data: dict[str, object],
) -> None:
    async def authorize(_request: web.Request) -> web.Response:
        return web.json_response(
            {
                "data": not_found_data,
                "correlation_id": "registry-correlation-on-behalf-bad-not-found",
            },
            status=404,
        )

    app = web.Application()
    app.router.add_get(
        "/v1/helpdesk/requesters/{creator_ref}/on-behalf/{affected_ref}/authorize",
        authorize,
    )
    server = TestServer(app)
    await server.start_server()
    try:
        result = await ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-on-behalf-bad-not-found",
            allow_insecure_test_url=True,
        ).authorize_on_behalf(
            actor=_requester_actor(),
            creator=RequesterRef(external_id="creator-person"),
            affected=RequesterRef(external_id="affected-person"),
            policy=registry_contracts.OnBehalfPolicyProjection(scope="any_employee"),
        )

        assert isinstance(result, RegistryInvalidProjection)
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http_adapter_rejects_non_json_on_behalf_not_found_envelope() -> None:
    async def authorize(_request: web.Request) -> web.Response:
        return web.Response(text="not-json", status=404, content_type="text/plain")

    app = web.Application()
    app.router.add_get(
        "/v1/helpdesk/requesters/{creator_ref}/on-behalf/{affected_ref}/authorize",
        authorize,
    )
    server = TestServer(app)
    await server.start_server()
    try:
        result = await ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-on-behalf-non-json",
            allow_insecure_test_url=True,
        ).authorize_on_behalf(
            actor=_requester_actor(),
            creator=RequesterRef(external_id="creator-person"),
            affected=RequesterRef(external_id="affected-person"),
            policy=registry_contracts.OnBehalfPolicyProjection(scope="any_employee"),
        )

        assert isinstance(result, RegistryInvalidProjection)
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http_adapter_returns_only_redacted_requester_snapshot() -> None:
    received_headers: dict[str, str] = {}

    async def snapshot(request: web.Request) -> web.Response:
        received_headers.update(request.headers)
        return web.json_response(
            {
                "data": {
                    "person": {"external_id": "registry-ref-opaque-1"},
                    "display_name": "Иван",
                },
                "correlation_id": "registry-correlation-1",
            }
        )

    app = web.Application()
    app.router.add_get("/v1/helpdesk/requesters/{person_ref}/snapshot", snapshot)
    server = TestServer(app)
    await server.start_server()
    try:
        adapter = ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-1",
            allow_insecure_test_url=True,
        )

        result = await adapter.requester_snapshot(PersonRef(external_id="registry-ref-opaque-1"))

        assert result.display_name == "Иван"
        assert result.model_dump(mode="json") == {
            "person": {"external_id": "registry-ref-opaque-1"},
            "display_name": "Иван",
        }
        assert received_headers["Authorization"] == "Bearer test-service-token"
        assert received_headers["X-Registry-Service-Scope"] == "registry.helpdesk.read.v1"
        assert received_headers["X-Correlation-ID"] == "registry-correlation-1"
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http_adapter_reads_exact_ticket_participant_projection() -> None:
    async def participant(_request: web.Request) -> web.Response:
        return web.json_response(
            {
                "data": {
                    "person": {"external_id": "registry-ref-opaque-1"},
                    "display_name": "Иван",
                    "full_name": "Иван Иванов",
                    "email": "ivan@example.test",
                    "department": {"external_id": "registry-ref-opaque-department-1"},
                    "location": {"external_id": "registry-ref-opaque-location-1"},
                },
                "correlation_id": "registry-correlation-ticket-participant",
            }
        )

    app = web.Application()
    app.router.add_get(
        "/v1/helpdesk/requesters/{person_ref}/ticket-participant",
        participant,
    )
    server = TestServer(app)
    await server.start_server()
    try:
        result = await ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-ticket-participant",
            allow_insecure_test_url=True,
        ).ticket_participant(PersonRef(external_id="registry-ref-opaque-1"))

        assert result.model_dump(mode="json") == {
            "person": {"external_id": "registry-ref-opaque-1"},
            "display_name": "Иван",
            "full_name": "Иван Иванов",
            "email": "ivan@example.test",
            "department": {"external_id": "registry-ref-opaque-department-1"},
            "location": {"external_id": "registry-ref-opaque-location-1"},
            "source": "external_authoritative",
        }
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http_adapter_rejects_ticket_participant_extra_keys_before_source_injection() -> None:
    async def participant(_request: web.Request) -> web.Response:
        return web.json_response(
            {
                "data": {
                    "person": {"external_id": "registry-ref-opaque-1"},
                    "display_name": "Иван",
                    "full_name": None,
                    "email": None,
                    "department": None,
                    "location": None,
                    "source": "external_authoritative",
                },
                "correlation_id": "registry-correlation-ticket-participant-extra",
            }
        )

    app = web.Application()
    app.router.add_get(
        "/v1/helpdesk/requesters/{person_ref}/ticket-participant",
        participant,
    )
    server = TestServer(app)
    await server.start_server()
    try:
        result = await ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-ticket-participant-extra",
            allow_insecure_test_url=True,
        ).ticket_participant(PersonRef(external_id="registry-ref-opaque-1"))

        assert isinstance(result, RegistryInvalidProjection)
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http_adapter_rejects_mismatched_ticket_participant_ref() -> None:
    async def participant(_request: web.Request) -> web.Response:
        return web.json_response(
            {
                "data": {
                    "person": {"external_id": "registry-ref-other-person"},
                    "display_name": "Иван",
                    "full_name": None,
                    "email": None,
                    "department": None,
                    "location": None,
                },
                "correlation_id": "registry-correlation-ticket-participant-mismatch",
            }
        )

    app = web.Application()
    app.router.add_get(
        "/v1/helpdesk/requesters/{person_ref}/ticket-participant",
        participant,
    )
    server = TestServer(app)
    await server.start_server()
    try:
        result = await ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-ticket-participant-mismatch",
            allow_insecure_test_url=True,
        ).ticket_participant(PersonRef(external_id="registry-ref-opaque-1"))

        assert isinstance(result, RegistryInvalidProjection)
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http_adapter_reads_redacted_inventory_quality_projection() -> None:
    async def inventory_quality(_request: web.Request) -> web.Response:
        return web.json_response(
            {
                "data": {"active_pc_without_location_count": 4},
                "correlation_id": "registry-correlation-inventory-quality",
            }
        )

    app = web.Application()
    app.router.add_get("/v1/helpdesk/inventory-quality", inventory_quality)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-inventory-quality",
            allow_insecure_test_url=True,
        ).inventory_quality()

        assert result.model_dump(mode="json") == {
            "active_pc_without_location_count": 4,
            "source": "external_authoritative",
        }
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http_adapter_rejects_invalid_inventory_quality_projection() -> None:
    async def inventory_quality(_request: web.Request) -> web.Response:
        return web.json_response(
            {
                "data": {"active_pc_without_location_count": "four"},
                "correlation_id": "registry-correlation-invalid-inventory-quality",
            }
        )

    app = web.Application()
    app.router.add_get("/v1/helpdesk/inventory-quality", inventory_quality)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-invalid-inventory-quality",
            allow_insecure_test_url=True,
        ).inventory_quality()

        assert isinstance(result, RegistryInvalidProjection)
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http_adapter_rejects_inventory_quality_source_before_local_source_injection() -> None:
    async def inventory_quality(_request: web.Request) -> web.Response:
        return web.json_response(
            {
                "data": {
                    "active_pc_without_location_count": 4,
                    "source": "external_authoritative",
                },
                "correlation_id": "registry-correlation-unexpected-source",
            }
        )

    app = web.Application()
    app.router.add_get("/v1/helpdesk/inventory-quality", inventory_quality)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-unexpected-source",
            allow_insecure_test_url=True,
        ).inventory_quality()

        assert isinstance(result, RegistryInvalidProjection)
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http_adapter_maps_timeout_to_typed_unavailable_without_diagnostics() -> None:
    async def slow_snapshot(_request: web.Request) -> web.Response:
        await __import__("asyncio").sleep(0.05)
        return web.json_response({"data": {}})

    app = web.Application()
    app.router.add_get("/v1/helpdesk/requesters/{person_ref}/snapshot", slow_snapshot)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=0.001,
            allow_insecure_test_url=True,
        ).requester_snapshot(PersonRef(external_id="registry-ref-opaque-1"))

        assert isinstance(result, RegistryUnavailable)
        assert result.code == "registry_unavailable"
    finally:
        await server.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("response_correlation_id", [None, "registry-correlation-other"])
async def test_http_adapter_rejects_success_envelope_without_matching_correlation_id(
    response_correlation_id: str | None,
) -> None:
    async def snapshot(_request: web.Request) -> web.Response:
        envelope: dict[str, object] = {
            "data": {
                "person": {"external_id": "registry-ref-opaque-1"},
                "display_name": "Requester One",
            }
        }
        if response_correlation_id is not None:
            envelope["correlation_id"] = response_correlation_id
        return web.json_response(envelope)

    app = web.Application()
    app.router.add_get("/v1/helpdesk/requesters/{person_ref}/snapshot", snapshot)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-expected",
            allow_insecure_test_url=True,
        ).requester_snapshot(PersonRef(external_id="registry-ref-opaque-1"))

        assert isinstance(result, RegistryInvalidProjection)
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http_adapter_never_sends_bearer_to_non_https_url() -> None:
    received_headers: dict[str, str] = {}

    async def snapshot(request: web.Request) -> web.Response:
        received_headers.update(request.headers)
        return web.json_response({"data": {}, "correlation_id": "unexpected"})

    app = web.Application()
    app.router.add_get("/v1/helpdesk/requesters/{person_ref}/snapshot", snapshot)
    server = TestServer(app)
    await server.start_server()
    try:
        adapter = ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
        )

        result = await adapter.requester_snapshot(PersonRef(external_id="registry-ref-opaque-1"))

        assert isinstance(result, RegistryUnavailable)
        assert result.code == "registry_external_unconfigured"
        assert received_headers == {}
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http_adapter_bounds_directory_limit_before_http_request() -> None:
    received_query: dict[str, str] = {}

    async def search(request: web.Request) -> web.Response:
        received_query.update(request.query)
        return web.json_response(
            {"data": {"items": []}, "correlation_id": "registry-correlation-limit"}
        )

    app = web.Application()
    app.router.add_get("/v1/helpdesk/directory/people", search)
    server = TestServer(app)
    await server.start_server()
    try:
        adapter = ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-limit",
            allow_insecure_test_url=True,
        )
        actor = RegistryReadActor(
            actor=ActorRef(external_id="registry-ref-opaque-actor-1"),
            role="support",
        )

        await adapter.search_people(DirectorySearchText("requester"), actor=actor, limit=999)

        assert received_query["limit"] == "50"
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http_adapter_bounds_history_limit_before_http_request() -> None:
    received_query: dict[str, str] = {}

    async def history(request: web.Request) -> web.Response:
        received_query.update(request.query)
        return web.json_response(
            {"data": {"items": []}, "correlation_id": "registry-correlation-history"}
        )

    app = web.Application()
    app.router.add_get("/v1/helpdesk/requesters/{person_ref}/history", history)
    server = TestServer(app)
    await server.start_server()
    try:
        adapter = ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-history",
            allow_insecure_test_url=True,
        )
        actor = RegistryReadActor(
            actor=ActorRef(external_id="registry-ref-opaque-actor-1"),
            role="support",
        )

        await adapter.requester_history(
            PersonRef(external_id="registry-ref-opaque-1"),
            actor=actor,
            limit=999,
        )

        assert received_query["limit"] == "100"
    finally:
        await server.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [0, True])
async def test_http_adapter_rejects_invalid_collection_limit_before_http_request(limit: int) -> None:
    received = False

    async def search(_request: web.Request) -> web.Response:
        nonlocal received
        received = True
        return web.json_response({"data": {"items": []}, "correlation_id": "unexpected"})

    app = web.Application()
    app.router.add_get("/v1/helpdesk/directory/people", search)
    server = TestServer(app)
    await server.start_server()
    try:
        adapter = ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            allow_insecure_test_url=True,
        )
        actor = RegistryReadActor(
            actor=ActorRef(external_id="registry-ref-opaque-actor-1"),
            role="support",
        )

        result = await adapter.search_people(DirectorySearchText("requester"), actor=actor, limit=limit)

        assert isinstance(result, RegistryInvalidProjection)
        assert received is False
    finally:
        await server.close()
