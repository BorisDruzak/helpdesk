"""Ticket-scoped Endpoint workspace BFF; poll reads only persisted projections."""
import hashlib
import time
from collections import OrderedDict
from functools import wraps

from aiohttp import web
from pydantic import ValidationError
from sqlalchemy import select,or_
import config
from access_control.service import can
from app.db import get_session
from app.db.engine import get_session_maker
from app.db.models import Ticket,DiagnosticEvidence,TicketEvidenceItem
from app.repos.endpoint_tool_runs_repo import EndpointToolRunsRepo, ToolRunConflict
from app.services.endpoint_device_reference_service import EndpointDeviceReferenceService
from app.services.endpoint_tool_run_service import EndpointToolRunService, ToolAdmissionError, require_projection, batch_status
from auth.middleware import require_auth
from diagnostics.endpoint_tool_parameters import derive_recipe_inputs
from domain_ports.container import DomainPortContainer
from domain_ports.endpoint import EndpointDeviceRef, EndpointFailureOutcome
from domain_ports.endpoint_context import SAFE_CONTEXT_PROFILES
from domain_ports.endpoint_module_contracts_generated import EndpointDeviceModulesPageV1, ModuleCapabilityCatalogV1
from tickets.handlers import _get_ticket_or_response
from web_api.dto.endpoint_tools import (
    EndpointToolRunCreateV1, EndpointToolBatchCreateV1, EndpointToolRunPayloadV1,
    EndpointToolBatchPayloadV1, EndpointToolItemV1, EndpointToolCatalogPayloadV1, EndpointToolAttachV1,
)

_NO_STORE = {"Cache-Control": "no-store"}


def tool_error_response(error):
    return web.json_response({"status":"error", "error_code":error.code, "error":"Инструмент Endpoint сейчас недоступен"},status=error.status,headers=_NO_STORE)


def _response(payload, status=200):
    response=web.json_response({"status":"success","data":payload.model_dump(mode="json") if hasattr(payload,"model_dump") else payload},status=status,headers=_NO_STORE)
    if len(response.body)>1048576: return tool_error_response(ToolAdmissionError("endpoint_projection_too_large",502))
    return response


def _safe(handler):
    @wraps(handler)
    async def wrapped(request):
        try: response=await handler(request)
        except ToolAdmissionError as error: return tool_error_response(error)
        except ToolRunConflict: return tool_error_response(ToolAdmissionError("endpoint_idempotency_conflict",409))
        except PermissionError: return tool_error_response(ToolAdmissionError("endpoint_permission_denied",403))
        except (ValidationError, ValueError): return tool_error_response(ToolAdmissionError("endpoint_invalid_request",400))
        except LookupError: return tool_error_response(ToolAdmissionError("endpoint_run_not_found",404))
        response.headers["Cache-Control"]="no-store"
        return response
    return wrapped


def require_run_identity(run, ticket_id, device_ref):
    if run is None or run.ticket_id!=ticket_id: raise ToolAdmissionError("endpoint_run_not_found",404)
    if run.device_ref!=device_ref: raise ToolAdmissionError("endpoint_device_changed",409)


def run_payload(run, *, summary=False,attached_steps=()):
    r=run.request
    return EndpointToolRunPayloadV1(run_id=run.run_id,ticket_id=run.ticket_id,device_ref=run.device_ref,kind=r.kind,
        module_key=r.module_key,version=r.version,profile=r.profile,inputs=r.inputs,status=run.status,
        remote_ref=run.remote_ref,safe_result=None if summary else run.safe_result,error_code=run.error_code,
        created_at=run.created_at,batch_id=run.batch_id,attached_steps=attached_steps)


async def _attached_steps(session,runs):
    if not runs: return {}
    refs=list((await session.execute(select(DiagnosticEvidence.source_id).join(TicketEvidenceItem,
        TicketEvidenceItem.source_id==DiagnosticEvidence.id).where(DiagnosticEvidence.ticket_id==runs[0].ticket_id,
        TicketEvidenceItem.ticket_id==runs[0].ticket_id,TicketEvidenceItem.source_kind=="diagnostic_evidence",
        DiagnosticEvidence.kind=="endpoint_tool_result",DiagnosticEvidence.source_type=="endpoint_platform",
        or_(*(DiagnosticEvidence.source_id.like(f"helpdesk-tool:{run.run_id}:step:%") for run in runs))))).scalars())
    result={r.run_id:set() for r in runs}
    for ref in refs:
        parts=ref.split(":")
        if len(parts)==4 and parts[0]=="helpdesk-tool" and parts[2]=="step" and parts[1] in result and parts[3] in tuple(str(i) for i in range(8)):
            result[parts[1]].add(int(parts[3]))
    return {key:tuple(sorted(values)) for key,values in result.items()}


class EndpointToolCatalogCache:
    """Bounded per-provider cache. Mutations bypass it completely."""
    def __init__(self, provider, *, clock=time.monotonic):
        self.provider,self.clock,self.entries=provider,clock,OrderedDict()

    async def _get(self,key,ttl,load):
        now=self.clock(); cached=self.entries.get(key)
        if cached and now-cached[0]<ttl: self.entries.move_to_end(key); return cached[1]
        result=await load()
        if not isinstance(result,EndpointFailureOutcome):
            self.entries[key]=(self.clock(),result)
            while len(self.entries)>256: self.entries.popitem(last=False)
        else: self.entries.pop(key,None)
        return result

    async def primitives(self):
        return await self._get(("primitives",),60,self.provider.list_primitives)

    async def device_page(self,device,*,limit=50,cursor=None):
        return await self._get(("device",device.external_id,limit,cursor),5,
            lambda:self.provider.list_device_modules(device,limit=limit,cursor=cursor))


def _runtime(request):
    identity=(config.ENDPOINT_EXTERNAL_BASE_URL,hashlib.sha256(config.ENDPOINT_EXTERNAL_SERVICE_TOKEN.encode()).digest())
    cached=request.app.get("endpoint_tool_catalog_runtime")
    if cached is None or cached[0]!=identity:
        ports=DomainPortContainer.from_config()
        cached=(identity,ports,EndpointToolCatalogCache(ports.endpoint_modules))
        request.app["endpoint_tool_catalog_runtime"]=cached
    return cached[1:]


async def _ticket_access(request, *, mutation=False,permission_code=None,admit_run=True):
    async with get_session() as session:
        ticket,error,_repo,actor=await _get_ticket_or_response(request,session,write=mutation)
        if error is not None: return None,error
        permission=permission_code or ("ticket.tool.run" if mutation else "ticket.detail.view")
        if not await can(session,actor,permission): raise ToolAdmissionError("endpoint_permission_denied",403)
        if mutation and admit_run and not config.ENDPOINT_TOOLS_WORKSPACE_ENABLED: raise ToolAdmissionError("endpoint_tools_disabled",409)
        return (ticket,actor),None


class _VerifiedAccess:
    def __init__(self,request): self.request=request
    async def require_ticket_operation_access(self,*,actor,ticket_id):
        result,error=await _ticket_access(self.request,mutation=True)
        if error is not None or result[0].ticket_id!=ticket_id or result[1].actor_id!=actor.actor_id:
            raise ToolAdmissionError("endpoint_permission_denied",403)


def _service(request):
    ports,_cache=_runtime(request)
    sessions=get_session_maker()
    return EndpointToolRunService(access_service=_VerifiedAccess(request),device_resolver=EndpointDeviceReferenceService(ports.endpoint,sessions),
        endpoint_port=ports.endpoint,modules_port=ports.endpoint_modules,session_factory=sessions)


def _device(ticket):
    mapping=EndpointDeviceReferenceService._validated_existing(ticket)
    if mapping.status!="resolved": raise ToolAdmissionError("endpoint_device_mapping_missing",409)
    return EndpointDeviceRef(external_id=mapping.device_ref)


@require_auth("admin","support","auditor")
@_safe
async def handle_tool_catalog(request):
    access,error=await _ticket_access(request)
    if error is not None: return error
    ticket,actor=access
    limit=int(request.query.get("limit","50"))
    cursor=request.query.get("cursor")
    if not 1<=limit<=100 or cursor is not None and not 1<=len(cursor)<=1024: raise ValueError("invalid pagination")
    _ports,cache=_runtime(request)
    device=_device(ticket)
    page=require_projection(await cache.device_page(device,limit=limit,cursor=cursor),EndpointDeviceModulesPageV1)
    primitives=require_projection(await cache.primitives(),ModuleCapabilityCatalogV1)
    items=[]
    for module in page.items:
        schema=None; availability,reason=module.availability,module.reason_code
        try:
            if module.recipe: schema=derive_recipe_inputs(module.recipe,primitives)
        except ValueError: availability,reason="unavailable","endpoint_schema_not_supported"
        items.append(EndpointToolItemV1(module_key=module.module_key,version=module.version,title=module.display_name,
            availability=availability,reason_code=reason,input_controls=schema.inputs if schema else (),fixed_settings=schema.fixed_settings if schema else (),
            capabilities=tuple(s.capability for s in module.recipe.steps) if schema else ()))
    async with get_session() as session: permitted=actor.actor_role in {"admin","support"} and await can(session,actor,"ticket.tool.run")
    return _response(EndpointToolCatalogPayloadV1(ticket_id=ticket.ticket_id,device_ref=device.external_id,
        enabled=config.ENDPOINT_TOOLS_WORKSPACE_ENABLED,can_run=permitted and config.ENDPOINT_TOOLS_WORKSPACE_ENABLED,
        observed_at=page.observed_at,items=tuple(items),next_cursor=page.next_cursor,profiles=SAFE_CONTEXT_PROFILES+("diagnostic_v1",)))


@require_auth("admin","support")
@_safe
async def handle_tool_run_create(request):
    access,error=await _ticket_access(request,mutation=True)
    if error is not None: return error
    ticket,actor=access
    body=EndpointToolRunCreateV1.model_validate(await request.json())
    run=await _service(request).create_module(actor,ticket.ticket_id,body,body.caller_key)
    return _response(run_payload(run),202)


@require_auth("admin","support","auditor")
@_safe
async def handle_tool_run_get(request):
    access,error=await _ticket_access(request)
    if error is not None: return error
    ticket,_actor=access
    async with get_session() as session:
        run=await EndpointToolRunsRepo(session).get_authorized_run(request.match_info["run_id"],ticket.ticket_id)
        attached=await _attached_steps(session,[run]) if run else {}
    require_run_identity(run,ticket.ticket_id,_device(ticket).external_id)
    return _response(run_payload(run,attached_steps=attached.get(run.run_id,())))


@require_auth("admin","support","auditor")
@_safe
async def handle_tool_runs_list(request):
    access,error=await _ticket_access(request)
    if error is not None: return error
    ticket,_actor=access
    async with get_session() as session: runs=await EndpointToolRunsRepo(session).list_runs(ticket.ticket_id)
    device=_device(ticket)
    return _response({"schema_version":"endpoint_tool_run_history_v1","items":[run_payload(r,summary=True).model_dump(mode="json") for r in runs if r.device_ref==device.external_id]})


def _batch_payload(batch_id,ticket_id,runs,attached=None):
    if len(runs)!=6: raise ToolAdmissionError("endpoint_batch_not_found",404)
    return EndpointToolBatchPayloadV1(batch_id=batch_id,ticket_id=ticket_id,status=batch_status([r.status for r in runs]),runs=tuple(run_payload(r,attached_steps=(attached or {}).get(r.run_id,())) for r in runs))


@require_auth("admin","support")
@_safe
async def handle_tool_batch_create(request):
    access,error=await _ticket_access(request,mutation=True)
    if error is not None: return error
    ticket,actor=access
    body=EndpointToolBatchCreateV1.model_validate(await request.json())
    batch,runs=await _service(request).create_context_batch(actor,ticket.ticket_id,body.caller_key)
    return _response(_batch_payload(batch,ticket.ticket_id,runs),202)


@require_auth("admin","support","auditor")
@_safe
async def handle_tool_batch_get(request):
    access,error=await _ticket_access(request)
    if error is not None: return error
    ticket,_actor=access
    async with get_session() as session:
        runs=await EndpointToolRunsRepo(session).list_runs(ticket.ticket_id,batch_id=request.match_info["run_id"],limit=6)
        attached=await _attached_steps(session,runs)
    for run in runs: require_run_identity(run,ticket.ticket_id,_device(ticket).external_id)
    return _response(_batch_payload(request.match_info["run_id"],ticket.ticket_id,runs,attached))


@require_auth("admin","support")
@_safe
async def handle_tool_attach(request):
    from diagnostics.passport_bridge import DiagnosticPassportBridgeService
    access,error=await _ticket_access(request,mutation=True,permission_code="ticket.passport.manage",admit_run=False)
    if error is not None: return error
    ticket,actor=access
    body=EndpointToolAttachV1.model_validate(await request.json())
    async with get_session() as session:
        item=await DiagnosticPassportBridgeService(session).attach_endpoint_tool_result(ticket_id=ticket.ticket_id,
            run_id=request.match_info["run_id"],step_sequence=body.step_sequence,actor=actor)
    return _response({"schema_version":"endpoint_tool_attachment_v1","evidence_id":item.source_id,"passport_evidence_id":item.id,"run_id":request.match_info["run_id"],"step_sequence":body.step_sequence})
