"""Ticket-facing tool orchestration; admission precedes durable intent creation."""
from uuid import uuid5, NAMESPACE_URL
from app.repos.endpoint_tool_runs_repo import EndpointToolRunsRepo, TERMINAL, canonical_json
from domain_ports.endpoint import EndpointDeviceRef, EndpointDevicePresenceProjection, EndpointFailureOutcome
from domain_ports.endpoint_context import SAFE_CONTEXT_PROFILES
from domain_ports.endpoint_modules import EndpointDeviceModulesPageV1, ModuleCapabilityCatalogV1, ModuleVersionViewV1
from domain_ports.endpoint_tools import ToolRunRequestV1
from diagnostics.endpoint_tool_parameters import derive_recipe_inputs, validate_tool_inputs


class ToolAdmissionError(ValueError):
    def __init__(self, code, status=409): self.code, self.status = code, status


def collection_requests():
    return tuple(ToolRunRequestV1(kind="context_collection", profile=p) for p in SAFE_CONTEXT_PROFILES) + (ToolRunRequestV1(kind="diagnostic"),)


def batch_status(statuses):
    if len(statuses) != 6 or any(s not in TERMINAL for s in statuses): return "running"
    if all(s == "succeeded" for s in statuses): return "succeeded"
    return "partial" if "succeeded" in statuses else "failed"


def require_projection(outcome, expected):
    if isinstance(outcome, expected): return outcome
    status = getattr(outcome, "status", "invalid_projection")
    # Provider authentication is distinct from the browser session.
    raise ToolAdmissionError(getattr(outcome, "code", "endpoint_invalid_projection"), 503 if status == "unavailable" else 502)


class EndpointToolRunService:
    def __init__(self, *, access_service, device_resolver, endpoint_port, modules_port, session_factory):
        self.access, self.resolver, self.endpoint, self.modules, self.sessions = access_service, device_resolver, endpoint_port, modules_port, session_factory

    async def _device(self, actor, ticket_id):
        await self.access.require_ticket_operation_access(actor=actor, ticket_id=ticket_id)
        result = await self.resolver.resolve_ticket(ticket_id)
        if result.status != "resolved" or not result.device_ref: raise ToolAdmissionError("endpoint_device_mapping_missing")
        return EndpointDeviceRef(external_id=result.device_ref)

    async def create_module(self, actor, ticket_id, request, caller_key):
        device = await self._device(actor, ticket_id)
        found, cursor, seen = None, None, set()
        for _ in range(20):
            page = require_projection(await self.modules.list_device_modules(device, limit=100, cursor=cursor), EndpointDeviceModulesPageV1)
            found = next((m for m in page.items if m.module_key == request.module_key and m.version == request.version), None)
            if found or page.next_cursor is None: break
            if page.next_cursor in seen: raise ToolAdmissionError("endpoint_invalid_projection", 502)
            seen.add(page.next_cursor); cursor = page.next_cursor
        if found is None: raise ToolAdmissionError("endpoint_module_not_published")
        if found.availability != "available": raise ToolAdmissionError(found.reason_code or "endpoint_module_unavailable")
        version = require_projection(await self.modules.read_module_version(request.module_key, request.version), ModuleVersionViewV1)
        if version.state != "published" or version.recipe != found.recipe: raise ToolAdmissionError("endpoint_module_changed")
        primitives = require_projection(await self.modules.list_primitives(), ModuleCapabilityCatalogV1)
        schema = derive_recipe_inputs(version.recipe, primitives)
        inputs = validate_tool_inputs(schema, request.inputs).inputs
        intent = ToolRunRequestV1(kind="module", module_key=version.module_key, version=version.version, inputs=inputs, recipe=version.recipe)
        return await self._persist(actor, ticket_id, device, intent, caller_key)

    async def _persist(self, actor, ticket_id, device, intent, caller_key, batch_id=None):
        async with self.sessions() as session:
            async with session.begin():
                return await EndpointToolRunsRepo(session).create_pending(intent, actor_id=str(actor.actor_id),
                    actor_role=actor.actor_role, ticket_id=ticket_id, device_ref=device.external_id, caller_key=caller_key, batch_id=batch_id)

    async def create_context_batch(self, actor, ticket_id, caller_key):
        device = await self._device(actor, ticket_id)
        if not isinstance(caller_key, str) or not 1 <= len(caller_key) <= 128 or any(ord(c) < 33 or ord(c) > 126 for c in caller_key):
            raise ValueError("invalid caller key")
        presence = require_projection(await self.endpoint.read_device_presence(device), EndpointDevicePresenceProjection)
        if presence.retired or not presence.online: raise ToolAdmissionError("device_offline")
        batch_id = str(uuid5(NAMESPACE_URL, canonical_json(["helpdesk-context-batch-v1", actor.actor_id, ticket_id, caller_key])))
        async with self.sessions() as session:
            async with session.begin():
                repo = EndpointToolRunsRepo(session)
                runs = []
                for intent in collection_requests():
                    key = f"batch:{batch_id}:{intent.profile or 'diagnostic_v1'}"
                    runs.append(await repo.create_pending(intent, actor_id=str(actor.actor_id), actor_role=actor.actor_role,
                        ticket_id=ticket_id, device_ref=device.external_id, caller_key=key, batch_id=batch_id))
                return batch_id, runs
