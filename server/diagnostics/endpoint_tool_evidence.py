"""Materialize one validated result, with immutable Endpoint provenance."""
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from uuid import uuid5,NAMESPACE_URL

from domain_ports.endpoint import EndpointDiagnosticResultProjection
from domain_ports.endpoint_context import EndpointContextSnapshot
from domain_ports.endpoint_module_contracts_generated import ModuleOperationDetailV1
from endpoint_adapter.modules_wire import validate_module_projection


def _canonical(value): return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)


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
    source_id=f"helpdesk-tool:{run.run_id}:step:{step}"
    evidence_id=str(uuid5(NAMESPACE_URL,source_id))
    return DiagnosticEvidenceDraftV1(evidence_id,source_id,"endpoint_platform",capability,
        f"Endpoint · {capability}",status,result.collected_at,json.loads(raw))
