from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
import uuid

from aiohttp import web
from sqlalchemy import select

from app.db import get_session
from app.db.engine import get_session_maker
from access_control.service import resolve_effective_access
from app.db.models import (
    AgentRecipeVersion,
    DiagnosticCapability,
    DiagnosticCapabilityVersion,
    DiagnosticProvider,
    Device,
    DeviceDesiredModule,
    DeviceModule,
    DiagnosticEvidence,
    DiagnosticFinding,
    Ticket,
)
from app.repos.remote_access_repo import RemoteAccessRepo
from app.repos.diagnostics_repo import DiagnosticRepo
from app.services.endpoint_device_reference_service import EndpointDeviceReferenceService
from app.services.endpoint_diagnostic_operation_service import (
    EndpointDiagnosticOperationService,
    SqlAlchemyEndpointDiagnosticOperationStore,
)
from auth.middleware import require_auth
import config
from diagnostics.capability_registry import CapabilityRegistry
from diagnostics.agent_recipes import (
    COMPOSITE_RECIPE_PRESENTATION_SCHEMA,
    DEFAULT_AGENT_RECIPE_PRIMITIVES,
    PRIMITIVE_PRESENTATION_SCHEMAS,
    AgentRecipeValidationError,
    normalize_recipe_platforms,
)
from diagnostics.agent_recipes_repo import AgentRecipeRepo
from diagnostics.bundle import DiagnosticBundleService
from diagnostics.execution_router import CapabilityExecutionRouter
from diagnostics.observability import RuntimeAuditCapabilityExecutionObserver
from diagnostics.findings import DiagnosticFindingService
from diagnostics.passport_bridge import DiagnosticPassportBridgeService
from diagnostics.presentation_overrides import PresentationSchemaValidationError, ToolPresentationOverrideService
from diagnostics.provider_config import DiagnosticProviderConfigService
from diagnostics.providers.manual_provider import ManualCapabilityProvider
from diagnostics.providers.endpoint_platform import (
    ENDPOINT_DIAGNOSTIC_CAPABILITY_ID,
    EndpointPlatformDiagnosticProvider,
)
from diagnostics.profiles import list_profiles, resolve_ticket_profile
from diagnostics.profile_runner import DiagnosticProfileRunnerService
from diagnostics.projection import DiagnosticProjectionService
from diagnostics.readiness import CapabilityReadinessService, ReadinessContext
from diagnostics.runner_rollout import RunnerRolloutError, RunnerRolloutService, RunnerRolloutStateError
from diagnostics.serialization import bundle_to_dict, evidence_to_dict, finding_to_dict, session_to_dict, ticket_evidence_to_dict
from diagnostics.service import DiagnosticOverviewService
from remote_assist.policy import is_remote_assist_mode_enabled
from diagnostics.sessions import DiagnosticSessionService
from tools.service import ToolExecutionService
from domain_ports.container import DomainPortContainer


class _HandlerVerifiedEndpointAccess:
    """Preserve the handler's verified ticket/auth boundary for the facade."""

    def __init__(self, *, ticket_id: str) -> None:
        self._ticket_id = ticket_id

    async def require_ticket_operation_access(self, *, actor: object, ticket_id: str) -> None:
        if actor is None or ticket_id != self._ticket_id:
            raise PermissionError("verified ticket operation access is required")


@dataclass(frozen=True)
class _DiagnosticRuntime:
    registry: CapabilityRegistry
    tool_service: object | None
    endpoint_port: object | None
    endpoint_platform_provider: object | None


def _build_endpoint_platform_provider(ticket_id: str) -> tuple[object, EndpointPlatformDiagnosticProvider]:
    """Compose the local facade from typed endpoint dependencies only."""

    endpoint_port = DomainPortContainer.from_config().endpoint
    session_factory = get_session_maker
    operation_service = EndpointDiagnosticOperationService(
        access_service=_HandlerVerifiedEndpointAccess(ticket_id=ticket_id),
        device_resolver=EndpointDeviceReferenceService(endpoint_port, session_factory),
        store=SqlAlchemyEndpointDiagnosticOperationStore(session_factory),
    )
    return endpoint_port, EndpointPlatformDiagnosticProvider(operation_service=operation_service)


def _build_diagnostic_runtime(*, state: object, ticket_id: str) -> _DiagnosticRuntime:
    mode = str(config.ENDPOINT_DIAGNOSTIC_EXECUTION_MODE or "legacy").strip().lower()
    if mode == "endpoint":
        endpoint_port, endpoint_platform_provider = _build_endpoint_platform_provider(ticket_id)
        return _DiagnosticRuntime(
            registry=CapabilityRegistry(
                tool_service=None,
                state=state,
                endpoint_diagnostic_execution_mode="endpoint",
                endpoint_cutover_only=True,
            ),
            tool_service=None,
            endpoint_port=endpoint_port,
            endpoint_platform_provider=endpoint_platform_provider,
        )
    tool_service = ToolExecutionService(state)
    return _DiagnosticRuntime(
        registry=CapabilityRegistry(tool_service=tool_service, state=state),
        tool_service=tool_service,
        endpoint_port=None,
        endpoint_platform_provider=None,
    )


def _stored_endpoint_device_ref(ticket: Ticket) -> str | None:
    """Return only the validated Endpoint mapping, never the legacy device id."""

    value = getattr(ticket, "endpoint_device_ref", None)
    return value if isinstance(value, str) and value else None


async def _endpoint_device_ref_for_readiness(*, ticket_id: str, endpoint_port: object | None) -> str | None:
    """Verify the stored server-owned mapping before Endpoint capability readiness."""

    if endpoint_port is None:
        return None
    resolution = await EndpointDeviceReferenceService(endpoint_port, get_session_maker).resolve_ticket(ticket_id)
    return resolution.device_ref if resolution.status == "resolved" else None


def _capability_payload(capability):
    return capability.to_dict()


def _state_mapping(state, *names: str) -> dict:
    if state is None:
        return {}
    for name in names:
        value = getattr(state, name, None)
        if isinstance(value, dict):
            return value
        if hasattr(state, "get"):
            try:
                value = state.get(name)
            except Exception:
                value = None
            if isinstance(value, dict):
                return value
    return {}


def _merge_maps(*maps: dict) -> dict:
    result = {}
    for item in maps:
        if isinstance(item, dict):
            result.update(item)
    return result


def _remote_assist_policy_flags() -> dict:
    return {
        "remote_assist.enabled": bool(config.REMOTE_ASSIST_ENABLED),
        "remote_assist.interactive_control.enabled": is_remote_assist_mode_enabled("interactive_control"),
        "remote_assist.file_transfer.enabled": is_remote_assist_mode_enabled("file_transfer"),
        "remote_assist.elevated_admin.enabled": is_remote_assist_mode_enabled("elevated_admin"),
    }


def _remote_assist_context(active_session) -> dict:
    if active_session is None:
        return {}
    return {
        "active_session": {
            "session_id": active_session.id,
            "status": active_session.status,
            "mode": active_session.mode,
        }
    }


def _device_platform(device: Device | None) -> str | None:
    raw = str(getattr(device, "os", "") or "").strip().lower()
    if not raw:
        return None
    if "windows" in raw or raw.startswith("win"):
        return "win32"
    if "darwin" in raw or "mac" in raw:
        return "darwin"
    if "linux" in raw:
        return "linux"
    return raw


def _installed_module_map(items: list[DeviceModule]) -> dict:
    result = {}
    for item in items:
        result[item.module_name] = {
            "version": item.version,
            "installed": item.installed,
            "active": item.active,
            "state": item.state,
            "last_error_code": item.last_error_code,
        }
    return result


def _desired_module_map(items: list[DeviceDesiredModule]) -> dict:
    return {
        item.module_name: {
            "version": item.desired_version,
            "state": item.state,
            "reason": item.reason,
        }
        for item in items
    }


def _request_idempotency_key(request: web.Request, payload: dict) -> str | None:
    raw = payload.get("idempotency_key") or request.headers.get("X-Idempotency-Key")
    value = str(raw or "").strip()
    return value or None


def _request_timeout_ms(payload: dict) -> int | None:
    raw = payload.get("timeout_ms")
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return min(value, 300_000)


def _result_should_persist_as_evidence(capability, result: dict) -> bool:
    if capability is None or not isinstance(result, dict):
        return False
    if result.get("error_code") in {"CAPABILITY_NOT_FOUND", "CAPABILITY_NOT_READY", "CAPABILITY_TARGET_UNSUPPORTED"}:
        return False
    if capability.execution_target in {"agent_builtin", "agent_managed_module"}:
        return False
    if capability.execution_target == "endpoint_operation":
        # The reconciler owns terminal safe-result projection.  A queued local
        # facade must not create premature diagnostic evidence.
        return False
    if capability.execution_target == "agent_recipe" and result.get("status") in {
        "queued",
        "accepted",
        "running",
        "waiting_dependency",
        "installing_dependency",
    }:
        return False
    if capability.execution_target == "manual" and result.get("evidence_id"):
        return False
    return bool((capability.evidence or {}).get("produces_evidence") or result.get("evidence_preview"))


async def _valid_diagnostic_session_id(session, *, ticket_id: str, raw_session_id) -> str | None:
    session_id = str(raw_session_id or "").strip()
    if not session_id:
        return None
    repo = DiagnosticRepo(session)
    item = await repo.get_session(session_id)
    if item is None or item.ticket_id != ticket_id:
        return None
    return session_id


def _with_provider_runtime_params(params: dict, capability, persisted_maps) -> dict:
    result = dict(params or {})
    integration_key = getattr(capability, "integration_key", None)
    if not integration_key:
        return result
    config = persisted_maps.integration_configs.get(integration_key)
    if config is not None and "integration_config" not in result and "_integration_config" not in result:
        result["_integration_config"] = config
    credential_ref = getattr(persisted_maps, "credential_refs", {}).get(integration_key)
    if credential_ref is not None and "credentials_ref" not in result and "_credentials_ref" not in result:
        result["_credentials_ref"] = credential_ref
    mapping_key = getattr(capability, "mapping_key", None)
    mapping = None
    if mapping_key and mapping_key in persisted_maps.mappings:
        mapping = {mapping_key: persisted_maps.mappings[mapping_key]}
    elif persisted_maps.mappings:
        mapping = persisted_maps.mappings
    if mapping is not None and "mapping" not in result and "_mapping" not in result:
        result["_mapping"] = mapping
    return result


@require_auth("admin", "support", "auditor")
async def handle_diagnostics_capabilities(request: web.Request) -> web.Response:
    state = request.app.get("state")
    tool_service = ToolExecutionService(state)
    registry = CapabilityRegistry(tool_service=tool_service, state=state)
    device_id = request.query.get("device_id")
    capabilities = await registry.list_capabilities(device_id=device_id)
    existing_ids = {capability.id for capability in capabilities}
    async with get_session() as session:
        for recipe in await AgentRecipeRepo(session).list_published_capabilities():
            descriptor = recipe.descriptor()
            if descriptor.id not in existing_ids:
                capabilities.append(descriptor)
                existing_ids.add(descriptor.id)
        capabilities = await ToolPresentationOverrideService(session).apply_to_capabilities(capabilities)
    return web.json_response(
        {
            "status": "ok",
            "capabilities": [_capability_payload(capability) for capability in capabilities],
            "count": len(capabilities),
        },
        headers={"Cache-Control": "no-store"},
    )


@require_auth("admin")
async def handle_diagnostics_provider_configs(request: web.Request) -> web.Response:
    async with get_session() as session:
        provider_configs = await DiagnosticProviderConfigService(session).list_provider_configs()
    return web.json_response(
        {
            "status": "ok",
            "provider_configs": provider_configs,
            "count": len(provider_configs),
        }
    )


@require_auth("admin")
async def handle_diagnostics_provider_config_get(request: web.Request) -> web.Response:
    provider_id = str(request.match_info.get("provider_id") or "").strip()
    async with get_session() as session:
        provider_config = await DiagnosticProviderConfigService(session).get_provider_config(provider_id)
    if provider_config is None:
        return web.json_response(
            {"status": "error", "error_code": "PROVIDER_CONFIG_NOT_FOUND", "error": "Provider config not found"},
            status=404,
        )
    return web.json_response({"status": "ok", "provider_config": provider_config})


@require_auth("admin")
async def handle_diagnostics_provider_config_put(request: web.Request) -> web.Response:
    provider_id = str(request.match_info.get("provider_id") or "").strip()
    if not provider_id:
        return web.json_response(
            {"status": "error", "error_code": "PROVIDER_ID_REQUIRED", "error": "provider_id is required"},
            status=400,
        )
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    auth_context = request.get("auth_context")
    async with get_session() as session:
        service = DiagnosticProviderConfigService(session)
        try:
            await service.upsert_provider_config(
                provider_id=provider_id,
                provider_type=str(payload.get("provider_type") or "server_connector"),
                integration_key=payload.get("integration_key"),
                enabled=bool(payload.get("enabled", True)),
                config=payload.get("config") if isinstance(payload.get("config"), dict) else {},
                credential_refs=payload.get("credential_refs") if isinstance(payload.get("credential_refs"), list) else [],
                health=payload.get("health") if isinstance(payload.get("health"), dict) else {},
                actor_id=getattr(auth_context, "actor_id", None),
                actor_role=getattr(auth_context, "actor_role", None),
            )
        except ValueError as exc:
            return web.json_response(
                {"status": "error", "error_code": "PROVIDER_CONFIG_INVALID", "error": str(exc)},
                status=400,
            )
        provider_config = await service.get_provider_config(provider_id)
        await session.commit()
    return web.json_response({"status": "ok", "provider_config": provider_config})


def _primitive_payload(row) -> dict:
    if isinstance(row, dict):
        payload = dict(row)
        primitive_id = str(payload.get("primitive_id") or "")
        payload.setdefault("presentation_schema", PRIMITIVE_PRESENTATION_SCHEMAS.get(primitive_id, {}))
        return payload
    primitive_id = str(row.primitive_id or "")
    return {
        "id": row.id,
        "runner_provider_id": row.runner_provider_id,
        "runner_version": row.runner_version,
        "primitive_id": row.primitive_id,
        "primitive_version": row.primitive_version,
        "title": row.title,
        "description": row.description,
        "platforms": row.platforms_json,
        "params_schema": row.params_schema,
        "output_schema": row.output_schema,
        "output_contract": row.output_contract,
        "presentation_schema": PRIMITIVE_PRESENTATION_SCHEMAS.get(primitive_id, {}),
        "safety": row.safety_json,
        "evidence_defaults": row.evidence_defaults_json,
        "resource_limits": row.resource_limits_json,
        "redaction": row.redaction_json,
    }


@require_auth("admin")
async def handle_agent_recipe_primitives(request: web.Request) -> web.Response:
    async with get_session() as session:
        persisted = await AgentRecipeRepo(session).list_primitives()
    primitives = [_primitive_payload(item) for item in persisted]
    known = {(item.get("primitive_id"), item.get("primitive_version")) for item in primitives}
    for item in DEFAULT_AGENT_RECIPE_PRIMITIVES:
        key = (item.get("primitive_id"), item.get("primitive_version"))
        if key not in known:
            primitives.append({"runner_provider_id": "agent_recipe_runner", "runner_version": "1.0.0", **item})
    return web.json_response({"status": "ok", "primitives": primitives, "count": len(primitives)})


@require_auth("admin")
async def handle_agent_recipes_list(request: web.Request) -> web.Response:
    async with get_session() as session:
        recipes = await AgentRecipeRepo(session).list_published_capabilities()
    return web.json_response(
        {
            "status": "ok",
            "capabilities": [item.descriptor().to_dict() for item in recipes],
            "count": len(recipes),
        }
    )


@require_auth("admin")
async def handle_agent_recipe_create(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    canonical_id = str(payload.get("canonical_id") or "").strip()
    title = str(payload.get("title") or "").strip()
    primitive_id = str(payload.get("primitive_id") or "").strip()
    version = str(payload.get("version") or "1.0.0").strip()
    if not canonical_id or not title or not primitive_id:
        return web.json_response(
            {"status": "error", "error_code": "AGENT_RECIPE_INVALID", "error": "canonical_id, title and primitive_id are required"},
            status=400,
        )
    try:
        platforms = normalize_recipe_platforms(payload.get("platforms") or ["win32"])
    except AgentRecipeValidationError as exc:
        return web.json_response({"status": "error", "error_code": "AGENT_RECIPE_INVALID", "error": str(exc)}, status=400)

    evidence_mapping = payload.get("evidence_mapping") if isinstance(payload.get("evidence_mapping"), dict) else {}
    if not evidence_mapping:
        evidence_mapping = {
            "produces_evidence": True,
            "kind": str(payload.get("evidence_kind") or "endpoint.recipe"),
            "domain": str(payload.get("domain") or "endpoint"),
            "perspective": "endpoint",
            "passport_eligible": bool(payload.get("passport_eligible", True)),
        }
    capability_version_id = str(uuid.uuid4())
    recipe_version_id = str(uuid.uuid4())
    descriptor = {
        "id": canonical_id,
        "title": title,
        "description": str(payload.get("description") or ""),
        "provider_id": "agent_recipe_runner",
        "provider_type": "agent_recipe_runner",
        "execution_target": "agent_recipe",
        "platforms": platforms,
        "tool_kind": "diagnostic",
        "risk_level": "low",
        "evidence": evidence_mapping,
        "presentation_schema": payload.get("presentation_schema")
        if isinstance(payload.get("presentation_schema"), dict)
        else COMPOSITE_RECIPE_PRESENTATION_SCHEMA,
    }
    auth_context = request.get("auth_context")
    async with get_session() as session:
        provider = await session.get(DiagnosticProvider, "agent_recipe_runner")
        if provider is None:
            session.add(
                DiagnosticProvider(
                    provider_id="agent_recipe_runner",
                    provider_type="agent_recipe_runner",
                    title="Agent Recipe Runner",
                    description="Protected managed module for declarative endpoint diagnostics.",
                    source="managed_module",
                    status="available",
                )
            )
            await session.flush()
        capability = await session.get(DiagnosticCapability, canonical_id)
        if capability is None:
            capability = DiagnosticCapability(
                capability_id=canonical_id,
                provider_id="agent_recipe_runner",
                execution_target="agent_recipe",
                title=title,
                description=descriptor["description"],
                status="draft",
                latest_version=version,
                descriptor_json=descriptor,
            )
            session.add(capability)
        capability_version = DiagnosticCapabilityVersion(
            id=capability_version_id,
            capability_id=canonical_id,
            version=version,
            status="draft",
            descriptor_json=descriptor,
            params_schema_json=payload.get("params_schema") if isinstance(payload.get("params_schema"), dict) else {},
            output_schema_json=payload.get("output_schema") if isinstance(payload.get("output_schema"), dict) else {},
            output_contract_json=payload.get("output_contract") if isinstance(payload.get("output_contract"), dict) else {},
            safety_json={"read_only": True, "side_effects": False, **(payload.get("safety") if isinstance(payload.get("safety"), dict) else {})},
            evidence_mapping_json=evidence_mapping,
            deployment_json={"runner_provider_id": "agent_recipe_runner", "min_runner_version": str(payload.get("min_runner_version") or "1.0.0")},
            readiness_json={},
            contract_hash=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{canonical_id}:{version}:{primitive_id}")),
            created_by=getattr(auth_context, "actor_id", None),
        )
        session.add(capability_version)
        await session.flush()
        recipe = AgentRecipeVersion(
            id=recipe_version_id,
            capability_version_id=capability_version_id,
            recipe_schema_version=str(payload.get("recipe_schema_version") or "1.0"),
            runner_provider_id="agent_recipe_runner",
            min_runner_version=str(payload.get("min_runner_version") or "1.0.0"),
            primitive_id=primitive_id,
            primitive_version=str(payload.get("primitive_version") or "1.0"),
            platforms_json=platforms,
            platform_variants_json=payload.get("platform_variants") if isinstance(payload.get("platform_variants"), dict) else {},
            recipe_json=payload.get("recipe") if isinstance(payload.get("recipe"), dict) else {"params": payload.get("params") if isinstance(payload.get("params"), dict) else {}},
            parameter_bindings_json=payload.get("parameter_bindings") if isinstance(payload.get("parameter_bindings"), dict) else {},
            resource_limits_json=payload.get("resource_limits") if isinstance(payload.get("resource_limits"), dict) else {"timeout_sec": 10},
            redaction_json=payload.get("redaction") if isinstance(payload.get("redaction"), dict) else {},
            validation_status="unknown",
        )
        session.add(recipe)
        await session.commit()
    return web.json_response(
        {
            "status": "ok",
            "capability_id": canonical_id,
            "capability_version_id": capability_version_id,
            "recipe_version_id": recipe_version_id,
            "capability": descriptor,
        },
        status=201,
    )


@require_auth("admin")
async def handle_agent_recipe_validate(request: web.Request) -> web.Response:
    recipe_id = str(request.match_info.get("recipe_id") or "").strip()
    async with get_session() as session:
        recipe = await session.get(AgentRecipeVersion, recipe_id)
        if recipe is None:
            return web.json_response({"status": "error", "error_code": "RECIPE_NOT_FOUND", "error": "Recipe not found"}, status=404)
        try:
            normalize_recipe_platforms(recipe.platforms_json)
        except AgentRecipeValidationError as exc:
            recipe.validation_status = "failed"
            await session.commit()
            return web.json_response({"status": "error", "validation_status": "failed", "error": str(exc)}, status=400)
        recipe.validation_status = "passed"
        await session.commit()
    return web.json_response({"status": "ok", "recipe_version_id": recipe_id, "validation_status": "passed"})


@require_auth("admin")
async def handle_agent_recipe_publish(request: web.Request) -> web.Response:
    recipe_id = str(request.match_info.get("recipe_id") or "").strip()
    async with get_session() as session:
        recipe = await session.get(AgentRecipeVersion, recipe_id)
        if recipe is None:
            return web.json_response({"status": "error", "error_code": "RECIPE_NOT_FOUND", "error": "Recipe not found"}, status=404)
        version = await session.get(DiagnosticCapabilityVersion, recipe.capability_version_id)
        if version is None:
            return web.json_response({"status": "error", "error_code": "CAPABILITY_VERSION_NOT_FOUND", "error": "Capability version not found"}, status=404)
        capability = await session.get(DiagnosticCapability, version.capability_id)
        if capability is None:
            return web.json_response({"status": "error", "error_code": "CAPABILITY_NOT_FOUND", "error": "Capability not found"}, status=404)
        recipe.validation_status = "passed"
        version.status = "published"
        version.is_current = True
        version.published_at = datetime.now(timezone.utc)
        capability.status = "active"
        capability.latest_version = version.version
        capability.descriptor_json = dict(version.descriptor_json or {})
        await session.commit()
    return web.json_response({"status": "ok", "capability_id": capability.capability_id, "version_id": version.id, "recipe_version_id": recipe.id})


def _auth_actor_label(request: web.Request) -> str:
    auth_context = request.get("auth_context")
    return str(getattr(auth_context, "actor_id", None) or getattr(auth_context, "actor_role", None) or "admin")


async def _resolve_tool_presentation_descriptor(request: web.Request, session, tool_id: str):
    state = request.app.get("state")
    registry = CapabilityRegistry(tool_service=ToolExecutionService(state), state=state)
    descriptor = await registry.resolve_capability(tool_id, device_id=request.query.get("device_id"))
    service = ToolPresentationOverrideService(session)
    if descriptor is None:
        descriptor = await service.descriptor_from_persisted_capability(tool_id)
    return descriptor


def _tool_presentation_error(error: PresentationSchemaValidationError) -> web.Response:
    return web.json_response(
        {
            "status": "error",
            "error_code": error.code,
            "error": error.message,
            "path": error.path,
        },
        status=400,
    )


@require_auth("admin")
async def handle_tool_presentation_get(request: web.Request) -> web.Response:
    tool_id = str(request.query.get("tool_id") or "").strip()
    tool_version = str(request.query.get("tool_version") or "").strip() or None
    if not tool_id:
        return web.json_response({"status": "error", "error_code": "TOOL_ID_REQUIRED", "error": "tool_id is required"}, status=400)
    async with get_session() as session:
        descriptor = await _resolve_tool_presentation_descriptor(request, session, tool_id)
        if descriptor is None:
            return web.json_response({"status": "error", "error_code": "CAPABILITY_NOT_FOUND", "error": "Capability not found"}, status=404)
        detail = await ToolPresentationOverrideService(session).get_presentation_detail(descriptor, tool_version=tool_version)
    return web.json_response({"status": "ok", **detail}, headers={"Cache-Control": "no-store"})


@require_auth("admin")
async def handle_tool_presentation_put(request: web.Request) -> web.Response:
    tool_id = str(request.query.get("tool_id") or "").strip()
    tool_version = str(request.query.get("tool_version") or "").strip() or None
    if not tool_id:
        return web.json_response({"status": "error", "error_code": "TOOL_ID_REQUIRED", "error": "tool_id is required"}, status=400)
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    async with get_session() as session:
        descriptor = await _resolve_tool_presentation_descriptor(request, session, tool_id)
        if descriptor is None:
            return web.json_response({"status": "error", "error_code": "CAPABILITY_NOT_FOUND", "error": "Capability not found"}, status=404)
        service = ToolPresentationOverrideService(session)
        try:
            await service.upsert_override(
                tool_id,
                payload.get("presentation_schema"),
                tool_version=tool_version,
                enabled=bool(payload.get("enabled", True)),
                actor_id=_auth_actor_label(request),
            )
        except PresentationSchemaValidationError as exc:
            return _tool_presentation_error(exc)
        detail = await service.get_presentation_detail(descriptor, tool_version=tool_version)
        await session.commit()
    return web.json_response({"status": "ok", **detail}, headers={"Cache-Control": "no-store"})


@require_auth("admin")
async def handle_tool_presentation_delete(request: web.Request) -> web.Response:
    tool_id = str(request.query.get("tool_id") or "").strip()
    tool_version = str(request.query.get("tool_version") or "").strip() or None
    if not tool_id:
        return web.json_response({"status": "error", "error_code": "TOOL_ID_REQUIRED", "error": "tool_id is required"}, status=400)
    async with get_session() as session:
        descriptor = await _resolve_tool_presentation_descriptor(request, session, tool_id)
        if descriptor is None:
            return web.json_response({"status": "error", "error_code": "CAPABILITY_NOT_FOUND", "error": "Capability not found"}, status=404)
        service = ToolPresentationOverrideService(session)
        await service.delete_or_disable_override(tool_id, tool_version=tool_version, actor_id=_auth_actor_label(request))
        detail = await service.get_presentation_detail(descriptor, tool_version=tool_version)
        await session.commit()
    return web.json_response({"status": "ok", **detail}, headers={"Cache-Control": "no-store"})


async def _runner_rollout_action(request: web.Request, action: str) -> web.Response:
    plan_id = str(request.match_info.get("plan_id") or "").strip()
    if not plan_id:
        return web.json_response(
            {"status": "error", "error_code": "PLAN_ID_REQUIRED", "error": "plan_id is required"},
            status=400,
        )
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    actor = _auth_actor_label(request)
    async with get_session() as session:
        service = RunnerRolloutService(session, state=request.app.get("state"))
        try:
            if action == "start-canary":
                plan = await service.start_canary(plan_id, actor=actor)
            elif action == "promote-next-wave":
                plan = await service.promote_next_wave(plan_id, actor=actor)
            elif action == "pause":
                plan = await service.pause_plan(plan_id, actor=actor)
            elif action == "resume":
                plan = await service.resume_plan(plan_id, actor=actor)
            elif action == "rollback":
                plan = await service.rollback_plan(plan_id, actor=actor, reason=str(payload.get("reason") or "").strip() or None)
            elif action == "refresh":
                plan = await service.refresh_plan(plan_id)
            else:
                return web.json_response({"status": "error", "error_code": "UNKNOWN_ACTION", "error": "Unknown rollout action"}, status=400)
        except RunnerRolloutStateError as exc:
            return web.json_response({"status": "error", "error_code": "RUNNER_ROLLOUT_STATE", "error": str(exc)}, status=409)
        except RunnerRolloutError as exc:
            return web.json_response({"status": "error", "error_code": "RUNNER_ROLLOUT_INVALID", "error": str(exc)}, status=400)
        await session.commit()
    return web.json_response({"status": "ok", "plan": plan})


@require_auth("admin")
async def handle_runner_rollout_summary(request: web.Request) -> web.Response:
    async with get_session() as session:
        service = RunnerRolloutService(session, state=request.app.get("state"))
        summary = await service.summary()
        plans = await service.list_plans()
    return web.json_response({"status": "ok", "summary": summary, "plans": plans})


@require_auth("admin")
async def handle_runner_rollout_create_plan(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    actor = _auth_actor_label(request)
    async with get_session() as session:
        service = RunnerRolloutService(session, state=request.app.get("state"))
        try:
            plan = await service.create_plan(
                target_version=str(payload.get("target_version") or "").strip(),
                rollback_version=str(payload.get("rollback_version") or "").strip() or None,
                target_device_ids=payload.get("target_device_ids") if isinstance(payload.get("target_device_ids"), list) else None,
                canary_size=int(payload.get("canary_size") or 1),
                wave_size=int(payload.get("wave_size") or 10),
                max_concurrency=int(payload.get("max_concurrency") or 10),
                actor=actor,
            )
        except RunnerRolloutError as exc:
            return web.json_response({"status": "error", "error_code": "RUNNER_ROLLOUT_INVALID", "error": str(exc)}, status=400)
        await session.commit()
    return web.json_response({"status": "ok", "plan": plan}, status=201)


@require_auth("admin")
async def handle_runner_rollout_get_plan(request: web.Request) -> web.Response:
    plan_id = str(request.match_info.get("plan_id") or "").strip()
    async with get_session() as session:
        service = RunnerRolloutService(session, state=request.app.get("state"))
        try:
            plan = await service.get_plan(plan_id)
        except RunnerRolloutError as exc:
            return web.json_response({"status": "error", "error_code": "RUNNER_ROLLOUT_NOT_FOUND", "error": str(exc)}, status=404)
    return web.json_response({"status": "ok", "plan": plan})


@require_auth("admin")
async def handle_runner_rollout_start_canary(request: web.Request) -> web.Response:
    return await _runner_rollout_action(request, "start-canary")


@require_auth("admin")
async def handle_runner_rollout_promote_next_wave(request: web.Request) -> web.Response:
    return await _runner_rollout_action(request, "promote-next-wave")


@require_auth("admin")
async def handle_runner_rollout_pause(request: web.Request) -> web.Response:
    return await _runner_rollout_action(request, "pause")


@require_auth("admin")
async def handle_runner_rollout_resume(request: web.Request) -> web.Response:
    return await _runner_rollout_action(request, "resume")


@require_auth("admin")
async def handle_runner_rollout_refresh(request: web.Request) -> web.Response:
    return await _runner_rollout_action(request, "refresh")


@require_auth("admin")
async def handle_runner_rollout_rollback(request: web.Request) -> web.Response:
    return await _runner_rollout_action(request, "rollback")


@require_auth("admin", "support", "auditor")
async def handle_ticket_diagnostics_capabilities(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    if not ticket_id:
        return web.json_response(
            {"status": "error", "error_code": "TICKET_ID_REQUIRED", "error": "ticket_id is required"},
            status=400,
        )
    state = request.app.get("state")
    async with get_session() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one_or_none()
        device = None
        installed_modules = []
        desired_modules = []
        active_remote_assist_session = None
        if ticket is not None and getattr(ticket, "device_id", None):
            device = (
                await session.execute(
                    select(Device).where(Device.device_id == ticket.device_id, Device.deleted_at.is_(None))
                )
            ).scalar_one_or_none()
            installed_modules = list(
                (
                    await session.execute(select(DeviceModule).where(DeviceModule.device_id == ticket.device_id))
                ).scalars()
            )
            desired_modules = list(
                (
                    await session.execute(select(DeviceDesiredModule).where(DeviceDesiredModule.device_id == ticket.device_id))
                ).scalars()
            )
            active_remote_assist_session = await RemoteAccessRepo(session).active_for_ticket_device(
                ticket.ticket_id,
                ticket.device_id,
            )
    if ticket is None:
        return web.json_response(
            {"status": "error", "error_code": "TICKET_NOT_FOUND", "error": "Ticket not found"},
            status=404,
        )
    device_id = str(getattr(ticket, "device_id", "") or "").strip() or None
    runtime = _build_diagnostic_runtime(state=state, ticket_id=ticket_id)
    endpoint_device_ref = await _endpoint_device_ref_for_readiness(
        ticket_id=ticket_id, endpoint_port=runtime.endpoint_port
    )
    registry = runtime.registry
    readiness_service = CapabilityReadinessService(state=state)
    capabilities = await registry.list_capabilities(device_id=device_id)
    auth_context = request.get("auth_context")
    access = resolve_effective_access(
        actor_id=getattr(auth_context, "actor_id", None),
        actor_role=getattr(auth_context, "actor_role", None),
    )
    async with get_session() as session:
        persisted_maps = await DiagnosticProviderConfigService(session).build_readiness_maps()
        capabilities = await ToolPresentationOverrideService(session).apply_to_capabilities(capabilities)
    context = ReadinessContext(
        ticket_id=ticket_id,
        device_id=device_id,
        actor=auth_context,
        device_platform=_device_platform(device),
        installed_modules=_installed_module_map(installed_modules),
        desired_modules=_desired_module_map(desired_modules),
        integration_configs=_merge_maps(
            _state_mapping(state, "diagnostic_integration_configs", "integration_configs"),
            persisted_maps.integration_configs,
        ),
        credential_keys=_merge_maps(
            _state_mapping(state, "diagnostic_credential_keys", "credential_keys"),
            persisted_maps.credential_keys,
        ),
        mappings=_merge_maps(
            _state_mapping(state, "diagnostic_mappings", "integration_mappings"),
            persisted_maps.mappings,
        ),
        policy_flags=_merge_maps(
            _remote_assist_policy_flags(),
            _state_mapping(state, "diagnostic_policy_flags", "policy_flags"),
            persisted_maps.policy_flags,
        ),
        permissions=set(access.permissions),
        has_root_trace=bool(getattr(ticket, "observer_root_trace_id", None)),
        remote_assist=_remote_assist_context(active_remote_assist_session),
        endpoint_execution_mode=str(config.ENDPOINT_DIAGNOSTIC_EXECUTION_MODE or "legacy"),
        endpoint_port=runtime.endpoint_port,
        endpoint_device_ref=endpoint_device_ref,
    )
    capability_items = []
    for capability in capabilities:
        readiness = await readiness_service.get_readiness(capability, context)
        item = capability.to_dict()
        item.update(readiness.to_dict())
        item["id"] = capability.id
        capability_items.append(item)
    return web.json_response(
        {
            "status": "ok",
            "ticket_id": ticket_id,
            "device_id": device_id,
            "capabilities": capability_items,
            "count": len(capability_items),
        }
    )


@require_auth("admin", "support")
async def handle_ticket_diagnostics_capability_run(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    capability_id = str(request.match_info.get("capability_id") or "").strip()
    if not ticket_id or not capability_id:
        return web.json_response(
            {"status": "error", "error_code": "CAPABILITY_RUN_TARGET_REQUIRED", "error": "ticket_id and capability_id are required"},
            status=400,
        )
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    raw_params = payload.get("params", {}) if isinstance(payload, dict) else {}
    if capability_id == ENDPOINT_DIAGNOSTIC_CAPABILITY_ID and (
        not isinstance(raw_params, dict) or raw_params
    ):
        return web.json_response(
            {
                "status": "error",
                "error_code": "ENDPOINT_DIAGNOSTIC_PARAMS_INVALID",
                "error": "Endpoint diagnostic capability accepts only an empty params object",
            },
            status=400,
        )
    params = raw_params if isinstance(raw_params, dict) else {}
    idempotency_key = _request_idempotency_key(request, payload)
    timeout_ms = _request_timeout_ms(payload)
    state = request.app.get("state")
    async with get_session() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one_or_none()
        device = None
        installed_modules = []
        desired_modules = []
        active_remote_assist_session = None
        if ticket is not None and getattr(ticket, "device_id", None):
            device = (
                await session.execute(
                    select(Device).where(Device.device_id == ticket.device_id, Device.deleted_at.is_(None))
                )
            ).scalar_one_or_none()
            installed_modules = list(
                (
                    await session.execute(select(DeviceModule).where(DeviceModule.device_id == ticket.device_id))
                ).scalars()
            )
            desired_modules = list(
                (
                    await session.execute(select(DeviceDesiredModule).where(DeviceDesiredModule.device_id == ticket.device_id))
                ).scalars()
            )
            active_remote_assist_session = await RemoteAccessRepo(session).active_for_ticket_device(
                ticket.ticket_id,
                ticket.device_id,
            )
    if ticket is None:
        return web.json_response(
            {"status": "error", "error_code": "TICKET_NOT_FOUND", "error": "Ticket not found"},
            status=404,
        )
    device_id = str(getattr(ticket, "device_id", "") or "").strip() or None
    runtime = _build_diagnostic_runtime(state=state, ticket_id=ticket_id)
    endpoint_device_ref = await _endpoint_device_ref_for_readiness(
        ticket_id=ticket_id, endpoint_port=runtime.endpoint_port
    )
    registry = runtime.registry
    capability = await registry.resolve_capability(capability_id, device_id=device_id)
    readiness = None
    if capability is not None:
        access = resolve_effective_access(
            actor_id=getattr(request.get("auth_context"), "actor_id", None),
            actor_role=getattr(request.get("auth_context"), "actor_role", None),
        )
        async with get_session() as session:
            persisted_maps = await DiagnosticProviderConfigService(session).build_readiness_maps()
        readiness_context = ReadinessContext(
            ticket_id=ticket_id,
            device_id=device_id,
            actor=request.get("auth_context"),
            device_platform=_device_platform(device),
            installed_modules=_installed_module_map(installed_modules),
            desired_modules=_desired_module_map(desired_modules),
            integration_configs=_merge_maps(
                _state_mapping(state, "diagnostic_integration_configs", "integration_configs"),
                persisted_maps.integration_configs,
            ),
            credential_keys=_merge_maps(
                _state_mapping(state, "diagnostic_credential_keys", "credential_keys"),
                persisted_maps.credential_keys,
            ),
            mappings=_merge_maps(
                _state_mapping(state, "diagnostic_mappings", "integration_mappings"),
                persisted_maps.mappings,
            ),
            policy_flags=_merge_maps(
                _remote_assist_policy_flags(),
                _state_mapping(state, "diagnostic_policy_flags", "policy_flags"),
                persisted_maps.policy_flags,
            ),
            permissions=set(access.permissions),
            has_root_trace=bool(getattr(ticket, "observer_root_trace_id", None)),
            remote_assist=_remote_assist_context(active_remote_assist_session),
            endpoint_execution_mode=str(config.ENDPOINT_DIAGNOSTIC_EXECUTION_MODE or "legacy"),
            endpoint_port=runtime.endpoint_port,
            endpoint_device_ref=endpoint_device_ref,
        )
        readiness = await CapabilityReadinessService(state=state).get_readiness(capability, readiness_context)
        params = _with_provider_runtime_params(params, capability, persisted_maps)
    observability = RuntimeAuditCapabilityExecutionObserver(state=state)
    router = CapabilityExecutionRouter(
        capability_registry=registry,
        tool_service=runtime.tool_service,
        endpoint_platform_provider=runtime.endpoint_platform_provider,
        observability=observability,
    )
    result = await router.run_capability(
        ticket_id=ticket_id,
        device_id=device_id,
        capability_id=capability_id,
        params=params,
        actor=request.get("auth_context"),
        readiness=readiness,
        idempotency_key=idempotency_key,
        timeout_ms=timeout_ms,
    )
    if _result_should_persist_as_evidence(capability, result):
        async with get_session() as session:
            session_id = await _valid_diagnostic_session_id(
                session,
                ticket_id=ticket_id,
                raw_session_id=payload.get("session_id") if isinstance(payload, dict) else None,
            )
            evidence = await DiagnosticProjectionService(session).project_capability_result(
                ticket_id=ticket_id,
                capability_descriptor=capability,
                result=result,
                actor=request.get("auth_context"),
                session_id=session_id,
                readiness=readiness.to_dict() if hasattr(readiness, "to_dict") else readiness,
                params=params,
            )
            await session.commit()
        result = dict(result)
        result["diagnostic_evidence_id"] = evidence.id
        result["evidence_persisted"] = True
        await observability.record_evidence_linked(
            capability=capability,
            ticket_id=ticket_id,
            device_id=device_id,
            actor=request.get("auth_context"),
            params=params,
            result=result,
            readiness=readiness,
            evidence_id=evidence.id,
            idempotency_key=idempotency_key,
            timeout_ms=timeout_ms,
        )
    status = 200
    if result.get("error_code") == "CAPABILITY_NOT_FOUND":
        status = 404
    elif result.get("error_code") == "CAPABILITY_NOT_READY":
        status = 409
    elif result.get("error_code") == "CAPABILITY_TARGET_UNSUPPORTED":
        status = 501
    elif result.get("execution_target") == "endpoint_operation" and result.get("status") == "queued":
        status = 202
    elif result.get("status") == "error":
        status = 400
    return web.json_response(result, status=status)


@require_auth("admin")
async def handle_admin_ticket_endpoint_device_mapping(request: web.Request) -> web.Response:
    """Admin-only exact provider-id mapping, verified before it is persisted."""

    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    try:
        payload = await request.json()
    except Exception:
        payload = None
    endpoint_device_ref = payload.get("endpoint_device_ref") if isinstance(payload, dict) else None
    if not ticket_id or not isinstance(endpoint_device_ref, str):
        return web.json_response(
            {"status": "error", "error_code": "ENDPOINT_DEVICE_MAPPING_REQUEST_INVALID"}, status=400
        )
    endpoint_port = DomainPortContainer.from_config().endpoint
    resolution = await EndpointDeviceReferenceService(
        endpoint_port, get_session_maker
    ).assign_verified_mapping(ticket_id=ticket_id, endpoint_device_ref=endpoint_device_ref)
    if resolution.status != "resolved":
        status = 503 if resolution.code == "ENDPOINT_UNAVAILABLE" else 409
        return web.json_response(
            {"status": "error", "error_code": resolution.code}, status=status
        )
    return web.json_response(
        {
            "status": "ok",
            "ticket_id": ticket_id,
            "endpoint_device_ref": resolution.device_ref,
            "verified": True,
        }
    )


@require_auth("admin", "support", "auditor")
async def handle_ticket_diagnostics_overview(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    async with get_session() as session:
        try:
            payload = await DiagnosticOverviewService(session).get_ticket_diagnostics_overview(
                ticket_id,
                actor=request.get("auth_context"),
            )
            await session.commit()
        except KeyError:
            return web.json_response({"status": "error", "error_code": "TICKET_NOT_FOUND", "error": "Ticket not found"}, status=404)
    return web.json_response(payload)


@require_auth("admin", "support", "auditor")
async def handle_web_support_ticket_diagnostics_overview(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    async with get_session() as session:
        try:
            payload = await DiagnosticOverviewService(session).get_ticket_diagnostics_overview(
                ticket_id,
                actor=request.get("auth_context"),
            )
            await session.commit()
        except KeyError:
            return web.json_response({"status": "error", "error_code": "TICKET_NOT_FOUND", "error": "Ticket not found"}, status=404)
    return web.json_response({"status": "success", "data": payload})


@require_auth("admin", "support", "auditor")
async def handle_ticket_diagnostics_sessions(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    async with get_session() as session:
        items = await DiagnosticSessionService(session).list_sessions(ticket_id)
    return web.json_response({"status": "ok", "ticket_id": ticket_id, "sessions": [session_to_dict(item) for item in items]})


@require_auth("admin", "support")
async def handle_ticket_diagnostics_session_create(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    async with get_session() as session:
        service = DiagnosticSessionService(session)
        item = await service.create_session(
            ticket_id=ticket_id,
            profile_id=payload.get("profile_id") if isinstance(payload, dict) else None,
            trigger_source=payload.get("trigger_source", "manual") if isinstance(payload, dict) else "manual",
            actor=request.get("auth_context"),
        )
        await session.commit()
    return web.json_response({"status": "ok", "session": session_to_dict(item)}, status=201)


@require_auth("admin", "support", "auditor")
async def handle_ticket_diagnostics_session_detail(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    session_id = str(request.match_info.get("session_id") or "").strip()
    async with get_session() as session:
        repo = DiagnosticRepo(session)
        item = await repo.get_session(session_id)
        if item is None or item.ticket_id != ticket_id:
            return web.json_response({"status": "error", "error_code": "SESSION_NOT_FOUND"}, status=404)
        steps = await repo.list_steps(ticket_id, session_id=session_id)
    return web.json_response({"status": "ok", "session": session_to_dict(item, steps=steps)})


@require_auth("admin", "support", "auditor")
async def handle_ticket_diagnostics_evidence(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    async with get_session() as session:
        items = await DiagnosticRepo(session).list_evidence(ticket_id)
    return web.json_response({"status": "ok", "ticket_id": ticket_id, "evidence": [evidence_to_dict(item) for item in items]})


@require_auth("admin", "support")
async def handle_ticket_diagnostics_manual_evidence(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    actor = request.get("auth_context")
    access = resolve_effective_access(
        actor_id=getattr(actor, "actor_id", None),
        actor_role=getattr(actor, "actor_role", None),
    )
    if "diagnostics.create_manual_evidence" not in set(access.permissions):
        return web.json_response(
            {
                "status": "error",
                "error_code": "PERMISSION_DENIED",
                "error": "Operator lacks permission to create manual diagnostic evidence",
            },
            status=403,
        )
    capability_id = str(payload.get("capability_id") or payload.get("kind") or "manual.visual_check").strip()
    if capability_id not in {"manual.visual_check", "manual.vendor_response", "manual.operator_note", "manual.customer_confirmation"}:
        capability_id = "manual.visual_check"
    state = request.app.get("state")
    capability = await CapabilityRegistry(tool_service=ToolExecutionService(state), state=state).resolve_capability(capability_id)
    if capability is None:
        return web.json_response({"status": "error", "error_code": "CAPABILITY_NOT_FOUND"}, status=404)
    result = await ManualCapabilityProvider().run(
        capability,
        ticket_id=ticket_id,
        device_id=payload.get("device_id"),
        actor=actor,
        params=payload,
        state=state,
    )
    if result.get("status") == "error":
        return web.json_response(result, status=400)
    if result.get("status") == "unsupported":
        return web.json_response(result, status=501)
    return web.json_response({"status": "ok", "evidence": result.get("output") or {}, "event_id": result.get("event_id")}, status=201)


@require_auth("admin", "support")
async def handle_ticket_diagnostics_evidence_patch(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    evidence_id = str(request.match_info.get("evidence_id") or "").strip()
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    async with get_session() as session:
        repo = DiagnosticRepo(session)
        item = await repo.get_evidence(evidence_id)
        if item is None or item.ticket_id != ticket_id:
            return web.json_response({"status": "error", "error_code": "EVIDENCE_NOT_FOUND"}, status=404)
        if isinstance(payload, dict) and "selected_for_passport" in payload:
            item.selected_for_passport = bool(payload["selected_for_passport"])
        await session.commit()
    return web.json_response({"status": "ok", "evidence": evidence_to_dict(item)})


@require_auth("admin", "support", "auditor")
async def handle_ticket_diagnostics_findings(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    async with get_session() as session:
        items = await DiagnosticFindingService(session).list_findings(ticket_id)
    return web.json_response({"status": "ok", "ticket_id": ticket_id, "findings": [finding_to_dict(item) for item in items]})


@require_auth("admin", "support")
async def handle_ticket_diagnostics_findings_evaluate(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    async with get_session() as session:
        await DiagnosticProjectionService(session).project_ticket_sources(ticket_id)
        items = await DiagnosticFindingService(session).evaluate_ticket(ticket_id)
        await session.commit()
    return web.json_response({"status": "ok", "ticket_id": ticket_id, "findings": [finding_to_dict(item) for item in items]})


@require_auth("admin", "support")
async def handle_ticket_diagnostics_manual_finding(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    async with get_session() as session:
        item = await DiagnosticRepo(session).upsert_finding(
            ticket_id=ticket_id,
            session_id=payload.get("session_id"),
            root_cause_code=payload.get("root_cause_code"),
            title=str(payload.get("title") or "Manual finding"),
            description=payload.get("description"),
            confidence=payload.get("confidence"),
            status=str(payload.get("status") or "suspected"),
            evidence_ids=payload.get("evidence_ids") if isinstance(payload.get("evidence_ids"), list) else [],
            recommended_actions=payload.get("recommended_actions") if isinstance(payload.get("recommended_actions"), list) else [],
            created_by="support",
        )
        await session.commit()
    return web.json_response({"status": "ok", "finding": finding_to_dict(item)}, status=201)


@require_auth("admin", "support")
async def handle_ticket_diagnostics_finding_patch(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    finding_id = str(request.match_info.get("finding_id") or "").strip()
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    async with get_session() as session:
        item = await session.get(DiagnosticFinding, finding_id)
        if item is None or item.ticket_id != ticket_id:
            return web.json_response({"status": "error", "error_code": "FINDING_NOT_FOUND"}, status=404)
        if isinstance(payload, dict):
            for field in ("status", "description", "confidence"):
                if field in payload:
                    setattr(item, field, payload[field])
        await session.commit()
    return web.json_response({"status": "ok", "finding": finding_to_dict(item)})


@require_auth("admin", "support")
async def handle_ticket_diagnostics_bundle_create(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    async with get_session() as session:
        await DiagnosticProjectionService(session).project_ticket_sources(ticket_id)
        item = await DiagnosticBundleService(session).build_bundle(
            ticket_id=ticket_id,
            session_id=payload.get("session_id"),
            actor=request.get("auth_context"),
            include_agent_actions=bool(payload.get("include_agent_actions", False)),
            include_observer=bool(payload.get("include_observer", True)),
            include_artifacts=bool(payload.get("include_artifacts", True)),
            include_remote_assist=bool(payload.get("include_remote_assist", True)),
            include_monitoring=bool(payload.get("include_monitoring", True)),
        )
        await session.commit()
    return web.json_response({"status": "ok", "bundle": bundle_to_dict(item)}, status=201)


@require_auth("admin", "support", "auditor")
async def handle_ticket_diagnostics_bundle_get(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    bundle_id = str(request.match_info.get("bundle_id") or "").strip()
    async with get_session() as session:
        item = await DiagnosticBundleService(session).get_bundle(bundle_id)
        if item is None or item.ticket_id != ticket_id:
            return web.json_response({"status": "error", "error_code": "BUNDLE_NOT_FOUND"}, status=404)
    return web.json_response({"status": "ok", "bundle": bundle_to_dict(item)})


@require_auth("admin", "support")
async def handle_ticket_diagnostics_passport_attach_selected(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    async with get_session() as session:
        items = await DiagnosticPassportBridgeService(session).attach_selected_diagnostic_evidence_to_passport(
            ticket_id=ticket_id,
            actor=request.get("auth_context"),
            passport_id=payload.get("passport_id"),
        )
        await session.commit()
    return web.json_response(
        {
            "status": "ok",
            "ticket_id": ticket_id,
            "attached_count": len(items),
            "evidence": [ticket_evidence_to_dict(item) for item in items],
        }
    )


@require_auth("admin", "support")
async def handle_ticket_diagnostics_run_profile(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    async with get_session() as session:
        try:
            result = await DiagnosticProfileRunnerService(session).run_profile(
                ticket_id=ticket_id,
                profile_id=payload.get("profile_id"),
                params=payload.get("params") if isinstance(payload.get("params"), dict) else {},
                auto_select_evidence=bool(payload.get("auto_select_evidence", False)),
                actor=request.get("auth_context"),
            )
            await session.commit()
        except KeyError:
            return web.json_response({"status": "error", "error_code": "TICKET_NOT_FOUND"}, status=404)
    response = {"status": "ok", **result}
    return web.json_response(response, status=201)


@require_auth("admin", "support", "auditor")
async def handle_diagnostics_profiles(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "profiles": list_profiles()})


@require_auth("admin", "support", "auditor")
async def handle_ticket_diagnostics_profile(request: web.Request) -> web.Response:
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    async with get_session() as session:
        ticket = await session.get(Ticket, ticket_id)
        if ticket is None:
            return web.json_response({"status": "error", "error_code": "TICKET_NOT_FOUND"}, status=404)
        profile = resolve_ticket_profile(ticket)
    return web.json_response({"status": "ok", "ticket_id": ticket_id, "profile": profile})
