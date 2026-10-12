"""Generate closed consumer DTOs from public JSON Schemas, never provider imports."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

FILES = (
    "endpoint-device-modules-v1.json", "module-capability-catalog-v1.json",
    "endpoint-module-version-view-v1.json", "endpoint-module-operation-create-v1.json",
    "endpoint-module-operation-detail-v1.json", "endpoint-module-operation-v1.json",
)


def bounded_type(base, schema):
    constraints = []
    for key, mapped in (("minimum", "ge"), ("maximum", "le"), ("minLength", "min_length"),
        ("maxLength", "max_length"), ("minItems", "min_length"), ("maxItems", "max_length"),
        ("minProperties", "min_length"), ("maxProperties", "max_length"), ("pattern", "pattern")):
        if key in schema:
            constraints.append(f"{mapped}={schema[key]!r}")
    return f"Annotated[{base}, Field({', '.join(constraints)})]" if constraints else base


def annotation(schema):
    if not schema:
        return "JsonValue"
    if "$ref" in schema:
        reference = schema["$ref"]
        if not reference.startswith("#/$defs/"):
            raise ValueError("only local contract references are supported")
        return reference.split("/")[-1]
    if "const" in schema:
        return f"Literal[{schema['const']!r}]"
    if "enum" in schema:
        return "Literal[" + ", ".join(repr(value) for value in schema["enum"]) + "]"
    for keyword in ("anyOf", "oneOf"):
        if keyword in schema:
            result = " | ".join(annotation(item) for item in schema[keyword])
            if "discriminator" in schema:
                result = f"Annotated[{result}, Field(discriminator={schema['discriminator']['propertyName']!r})]"
            return result
    kind = schema["type"]
    if kind == "string":
        return bounded_type("AwareDatetime" if schema.get("format") == "date-time" else "UUID" if schema.get("format") == "uuid" else "StrictStr", schema)
    if kind == "array":
        return f"list[{annotation(schema['items'])}]"
    if kind == "object":
        patterns = schema.get("patternProperties", {})
        if patterns:
            if len(patterns) != 1:
                raise ValueError("multiple key patterns are not supported")
            pattern, value = next(iter(patterns.items()))
            key = f"Annotated[StrictStr, Field(pattern={pattern!r}, min_length=1, max_length=64)]"
            return f"dict[{key}, {annotation(value)}]"
        return f"dict[str, {annotation(schema.get('additionalProperties', {}))}]"
    return bounded_type({"integer": "StrictInt", "number": "StrictFloat", "boolean": "StrictBool", "null": "None"}[kind], schema)


def render(provider_root):
    definitions, roots, digests = {}, {}, {}
    for filename in FILES:
        # EOL conversion in a Windows checkout must not change accepted digests.
        raw = subprocess.check_output(["git", "-C", str(provider_root), "show", "HEAD:contracts/jsonschema/" + filename])
        schema = json.loads(raw)
        digests[filename] = hashlib.sha256(raw).hexdigest()
        for name, definition in schema.get("$defs", {}).items():
            if name in definitions and definitions[name] != definition:
                raise ValueError(f"conflicting public definition: {name}")
            definitions[name] = definition
        roots[schema["title"]] = schema
    models = {**definitions, **roots}
    lines = [
        '"""Generated public-contract DTOs. Regenerate with generate_endpoint_tool_contracts.py."""',
        "from __future__ import annotations", "from typing import Annotated, Literal",
        "from uuid import UUID", "from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, StrictBool, StrictFloat, StrictInt, StrictStr",
        "", "class _Contract(BaseModel):", '    model_config = ConfigDict(extra="forbid", frozen=True)', "",
    ]
    for name, schema in sorted(models.items()):
        if schema.get("type") != "object" or "properties" not in schema:
            raise ValueError(f"unsupported contract model: {name}")
        lines.append(f"class {name}(_Contract):")
        required = set(schema.get("required", []))
        for field, value in schema["properties"].items():
            options = []
            if field not in required:
                if "default" not in value and value.get("type") in {"array", "object"}:
                    options.append("default_factory=" + ("list" if value["type"] == "array" else "dict"))
                else:
                    options.append(f"default={value.get('default')!r}")
            for key, mapped in (("minimum", "ge"), ("maximum", "le"), ("minLength", "min_length"),
                ("maxLength", "max_length"), ("minItems", "min_length"), ("maxItems", "max_length"),
                ("minProperties", "min_length"), ("maxProperties", "max_length"), ("pattern", "pattern")):
                if key in value:
                    options.append(f"{mapped}={value[key]!r}")
            suffix = f" = Field({', '.join(options)})" if options else ""
            lines.append(f"    {field}: {annotation(value)}{suffix}")
        lines.append("")
    lines.append("for _model in (" + ", ".join(sorted(models)) + "):")
    lines.append("    _model.model_rebuild()")
    lines.append("")
    return "\n".join(lines), json.dumps(digests, sort_keys=True, indent=2) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider-root", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    generated, digests = render(args.provider_root)
    root = Path(__file__).resolve().parents[1]
    for path, content in ((root / "server/domain_ports/endpoint_module_contracts_generated.py", generated),
                          (root / "integration/endpoint_tool_schema_digests.json", digests)):
        if args.check:
            if path.read_text(encoding="utf-8") != content:
                raise SystemExit(f"generated tool contract differs: {path.name}")
        else:
            path.write_text(content, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
