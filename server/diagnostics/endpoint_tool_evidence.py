"""Materialize one validated result, with immutable Endpoint provenance."""
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from uuid import uuid5,NAMESPACE_URL

from domain_ports.endpoint import EndpointDiagnosticResultProjection
from domain_ports.endpoint_context import EndpointContextSnapshot
from domain_ports.endpoint_module_contracts_generated import ModuleOperationDetailV1,ModuleOperationStepV1
from endpoint_adapter.modules_wire import validate_module_projection, validate_result_request


def _canonical(value): return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)


def retained_evidence_identity(run,step):
    if type(step) is not int or not 0<=step<=7: raise ValueError("unknown selected step")
    source_id=f"helpdesk-tool:{run.run_id}:step:{step}"
    return str(uuid5(NAMESPACE_URL,source_id)),source_id


def validate_retained_tool_evidence(run,step,item):
    evidence_id,source_id=retained_evidence_identity(run,step)
    payload=item.normalized_payload; provenance=payload.get("provenance",{})
    request=run.request
    if item.id!=evidence_id or item.ticket_id!=run.ticket_id or item.source_id!=source_id or item.source_type!="endpoint_platform" or item.kind!="endpoint_tool_result":
        raise ValueError("foreign retained evidence")
    expected={"source":"endpoint_platform","device_ref":run.device_ref,"run_id":run.run_id,"kind":request.kind,
        "module_key":request.module_key,"version":request.version,"profile":request.profile,"inputs":request.inputs,"step_sequence":step}
    if payload.get("schema_version")!="endpoint_tool_evidence_v1" or any(provenance.get(k)!=v for k,v in expected.items()):
        raise ValueError("retained provenance mismatch")
    unsigned={k:v for k,v in payload.items() if k!="digest_sha256"}
    if hashlib.sha256(_canonical(unsigned).encode()).hexdigest()!=payload.get("digest_sha256"):
        raise ValueError("retained evidence digest mismatch")
    if request.kind=="module":
        if step>=len(request.recipe.steps): raise ValueError("unknown module step")
        selected=ModuleOperationStepV1(sequence=step,capability=request.recipe.steps[step].capability,status=provenance["status"],safe_result=payload["result"])
        from endpoint_adapter.modules_wire import validate_safe_result
        if selected.safe_result is None or selected.status!=selected.safe_result.status: raise ValueError("retained status mismatch")
        validate_safe_result(selected.capability,selected.safe_result)
        validate_result_request(selected,request.recipe.steps[step],request.inputs)
    elif request.kind=="context_collection":
        result=EndpointContextSnapshot.model_validate(payload["result"])
        if step!=0 or result.profile!=request.profile: raise ValueError("retained profile mismatch")
    else:
        if step!=0: raise ValueError("unknown diagnostic step")
        EndpointDiagnosticResultProjection.model_validate(payload["result"])


@dataclass(frozen=True)
class DiagnosticEvidenceDraftV1:
    evidence_id: str
    source_id: str
    source_type: str
    capability_id: str
    title: str
    status: str
    observed_at: datetime
    normalized_payload: dict


def materialize_tool_evidence(run,step):
    if type(step) is not int or step<0 or step>7 or run.safe_result is None:
        raise ValueError("selected result is unavailable")
    request=run.request
    if request.kind=="module":
        detail=validate_module_projection(ModuleOperationDetailV1.model_validate(run.safe_result))
        if str(detail.device_id)!=run.device_ref or str(detail.operation_id)!=run.remote_ref or detail.module_key!=request.module_key or detail.version!=request.version:
            raise ValueError("result provenance mismatch")
        if step>=len(detail.steps) or len(detail.steps)!=len(request.recipe.steps): raise ValueError("unknown step")
        selected=detail.steps[step]
        validate_result_request(selected,request.recipe.steps[step],request.inputs)
        if selected.capability!=request.recipe.steps[step].capability or selected.status not in {"succeeded","failed"} or selected.safe_result is None:
            raise ValueError("step has no completed safe result")
        if selected.status!=selected.safe_result.status: raise ValueError("result status contradicts step")
        result=selected.safe_result
        status,capability=selected.status,selected.capability
    elif request.kind=="context_collection":
        if step!=0 or run.status not in {"succeeded","failed","expired"}: raise ValueError("unfinished context")
        result=EndpointContextSnapshot.model_validate(run.safe_result)
        if result.profile!=request.profile: raise ValueError("context profile mismatch")
        status,capability=run.status,request.profile
    else:
        if step!=0 or run.status not in {"succeeded","failed","expired","canceled"}: raise ValueError("unfinished diagnostic")
        result=EndpointDiagnosticResultProjection.model_validate(run.safe_result)
        status,capability=run.status,"context.diagnostic.collect"
    provenance={"source":"endpoint_platform","device_ref":run.device_ref,"run_id":run.run_id,"remote_ref":run.remote_ref,
        "kind":request.kind,"module_key":request.module_key,"version":request.version,"profile":request.profile,
        "inputs":request.inputs,"step_sequence":step,"capability":capability,"status":status,"collected_at":result.collected_at.isoformat(),
        "recipe_sha256":hashlib.sha256(_canonical(request.recipe.model_dump(mode="json")).encode()).hexdigest() if request.recipe else None}
    payload={"schema_version":"endpoint_tool_evidence_v1","provenance":provenance,"result":result.model_dump(mode="json")}
    payload["digest_sha256"]=hashlib.sha256(_canonical(payload).encode()).hexdigest()
    raw=_canonical(payload)
    if len(raw.encode())>1048576: raise ValueError("unbounded evidence")
    evidence_id,source_id=retained_evidence_identity(run,step)
    return DiagnosticEvidenceDraftV1(evidence_id,source_id,"endpoint_platform",capability,
        f"Endpoint · {capability}",status,result.collected_at,json.loads(raw))
