"""Generate readonly browser module types from accepted public JSON Schemas."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


def name(value): return re.sub(r"[^A-Za-z0-9_]","_",value)


def expression(schema):
    if "$ref" in schema: return name(schema["$ref"].split("/")[-1])
    if "const" in schema: return json.dumps(schema["const"])
    if "enum" in schema: return " | ".join(json.dumps(v) for v in schema["enum"])
    for key in ("anyOf","oneOf"):
        if key in schema: return " | ".join(expression(v) for v in schema[key])
    kind=schema.get("type")
    if kind=="array": return "ReadonlyArray<"+expression(schema["items"])+">"
    if kind=="object":
        if not schema.get("properties") and isinstance(schema.get("additionalProperties"),dict): return "Readonly<Record<string, "+expression(schema["additionalProperties"])+">>"
        required=set(schema.get("required",[]))
        return "{\n"+"\n".join("  readonly "+json.dumps(k)+(": " if k in required else "?: ")+expression(v)+";" for k,v in schema.get("properties",{}).items())+"\n}"
    if kind in ("string","integer","number","boolean","null"): return {"integer":"number","null":"null"}.get(kind,kind)
    raise ValueError("unsupported schema shape")


def generate(repo):
    raw=subprocess.check_output(["git","-C",str(repo),"show","HEAD:contracts/jsonschema/endpoint-module-operation-detail-v1.json"])
    digest_file=Path(__file__).resolve().parents[1]/"integration/endpoint_tool_schema_digests.json"
    expected=json.loads(digest_file.read_text(encoding="utf-8"))["endpoint-module-operation-detail-v1.json"]
    if hashlib.sha256(raw).hexdigest()!=expected: raise ValueError("provider schema is not the accepted consumer contract")
    schema=json.loads(raw)
    output=["// Generated from the accepted public module-operation schema. Do not edit."]
    for key,value in sorted(schema["$defs"].items()): output.append("export type "+name(key)+" = "+expression(value)+";")
    output.append("export type ModuleOperationDetailV1 = "+expression(schema)+";")
    output.append("export type EndpointPrimitiveResult = NonNullable<ModuleOperationStepV1['safe_result']>;")
    return "\n\n".join(output)+"\n"


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--endpoint-repo",required=True);parser.add_argument("--check",action="store_true")
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    output=root/"webapp/src/features/endpoint-tools/endpoint-module-types.generated.ts"
    content=generate(Path(args.endpoint_repo))
    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8")!=content: raise SystemExit("Endpoint browser type drift")
    else: output.parent.mkdir(parents=True,exist_ok=True);output.write_text(content,encoding="utf-8")


if __name__=="__main__": main()
