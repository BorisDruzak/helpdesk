"""Derive recipe controls by intersection; validate all resolved primitive inputs."""
import ipaddress
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr


class _DTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ToolInputV1(_DTO):
    name: str = Field(min_length=1, max_length=64)
    value_type: Literal["string", "integer"]
    minimum: int | None = None
    maximum: int | None = None
    enum_values: tuple[str, ...] | None = None
    semantic_types: tuple[Literal["network_target", "bounded_text", "software_name"], ...] = ()


class FixedSettingV1(_DTO):
    step_id: str
    parameter: str
    value: StrictStr | StrictInt


class ToolInputSchemaV1(_DTO):
    schema_version: Literal["endpoint_tool_input_schema_v1"] = "endpoint_tool_input_schema_v1"
    inputs: tuple[ToolInputV1, ...]
    fixed_settings: tuple[FixedSettingV1, ...]
    recipe: dict
    primitive_catalog: dict


class CanonicalToolInputsV1(_DTO):
    inputs: dict[str, StrictStr | StrictInt] = Field(max_length=8)


# Independent accepted bounds; remote metadata can narrow these, never widen them.
_TARGET = ("string", None, None, None, True)
_FAMILY = ("string", None, None, ("any", "ipv4", "ipv6"), True)
_PORT = ("integer", 1, 65535, None, True)
_NAME = ("string", None, None, None, True)
_SERVICE = ("string", None, None, ("endpoint_agent", "endpoint_agent_updater", "print_service"), False)
_PROFILE = ("string", None, None, ("system", "application", "print", "endpoint"), False)
_PATH = ("string", None, None, ("endpoint_install_root", "endpoint_data_root", "endpoint_runtime_manifest"), False)
PARAMETERS = {
    "dns.resolve": {"target": _TARGET, "family": _FAMILY},
    "network.ping": {"target": _TARGET, "count": ("integer", 1, 5, None, True), "timeout_ms": ("integer", 100, 5000, None, True)},
    "tcp.connect": {"target": _TARGET, "port": _PORT, "timeout_ms": ("integer", 100, 10000, None, True)},
    "route.get": {"target": _TARGET, "port": _PORT, "family": _FAMILY, "timeout_ms": ("integer", 100, 5000, None, True)},
    "adapter.list": {}, "system.service_status": {"service_key": ("string", None, None, ("endpoint_agent", "endpoint_agent_updater"), False)},
    "system.resource_snapshot": {}, "process.list": {}, "process.find": {"name": _NAME},
    "service.list": {}, "service.status": {"service_key": _SERVICE}, "printer.list": {}, "printer.status": {"printer_name": _NAME},
    "printer.queue.summary": {}, "software.list": {}, "software.find": {"name": _NAME}, "filesystem.free_space": {},
    "filesystem.path_exists": {"path_key": _PATH},
    "filesystem.file_metadata": {"path_key": ("string", None, None, ("endpoint_runtime_manifest",), False)},
    "eventlog.query": {"profile": _PROFILE, "lookback_minutes": ("integer", 1, 60, None, True),
        "severity": ("string", None, None, ("error", "warning", "information"), False), "max_events": ("integer", 1, 32, None, True)},
    "eventlog.recent_errors": {"profile": _PROFILE, "lookback_minutes": ("integer", 1, 60, None, True)},
}
_HOSTNAME = re.compile(r"(?=.{1,253}\Z)[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*\.?\Z")


def validate_network_target(value):
    if type(value) is not str or not value or len(value) > 253 or value != value.strip() or "%" in value:
        raise ValueError("invalid network target")
    try:
        ipaddress.ip_address(value)
    except ValueError:
        if _HOSTNAME.fullmatch(value) is None:
            raise ValueError("target must be hostname or IP") from None
    return value


def _plain(value):
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def _check(value, bounds, parameter):
    value_type, minimum, maximum, values, _ = bounds
    if type(value) is not (int if value_type == "integer" else str):
        raise ValueError("input type mismatch")
    if minimum is not None and value < minimum or maximum is not None and value > maximum:
        raise ValueError("input outside accepted bounds")
    if values is not None and value not in values:
        raise ValueError("input outside accepted enumeration")
    if value_type == "string":
        if parameter == "target":
            validate_network_target(value)
        elif not 1 <= len(value) <= 128 or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("invalid bounded text")


def _check_semantics(value, capability, parameter):
    if capability == "software.find" and parameter == "name" and any(char in value for char in "*?[]"):
        raise ValueError("software name must be plain text")


def derive_recipe_inputs(recipe, primitive_catalog):
    recipe, primitive_catalog = _plain(recipe), _plain(primitive_catalog)
    if recipe.get("schema_version") != "endpoint_recipe_module_v1" or not 1 <= len(recipe.get("steps", [])) <= 8:
        raise ValueError("unsupported recipe")
    declared = {item["name"]: item["value_type"] for item in recipe.get("inputs", [])}
    if len(declared) != len(recipe.get("inputs", [])) or len(declared) > 8:
        raise ValueError("invalid input declarations")
    catalog = {item["capability"]: item for item in primitive_catalog["items"]}
    controls, fixed = {}, []
    for step in recipe["steps"]:
        capability = step["capability"]
        if capability not in PARAMETERS or capability not in catalog:
            raise ValueError("unsupported capability")
        accepted_schema = {"system.service_status": "service_status_parameters_v1", "service.status": "service_status_v2_parameters_v1"}.get(
            capability, capability.replace(".", "_") + "_parameters_v1")
        if catalog[capability].get("parameter_schema_version") != accepted_schema:
            raise ValueError("unsupported parameter schema")
        expected = PARAMETERS[capability]
        metadata = {item["name"]: item for item in catalog[capability]["parameters"]}
        if set(step["parameters"]) != set(expected) or set(metadata) != set(expected):
            raise ValueError("parameter shape mismatch")
        for parameter, binding in step["parameters"].items():
            value_type, low, high, enum, editable = expected[parameter]
            descriptor = metadata[parameter]
            minimum = max(x for x in (low, descriptor.get("minimum")) if x is not None) if low is not None or descriptor.get("minimum") is not None else None
            maximum = min(x for x in (high, descriptor.get("maximum")) if x is not None) if high is not None or descriptor.get("maximum") is not None else None
            enums = set(enum) if enum is not None else None
            if descriptor.get("enum_values") is not None:
                enums = set(descriptor["enum_values"]) if enums is None else enums & set(descriptor["enum_values"])
            bounds = value_type, minimum, maximum, tuple(sorted(enums)) if enums is not None else None, editable
            if minimum is not None and maximum is not None and minimum > maximum or enums == set():
                raise ValueError("conflicting parameter bounds")
            if binding["kind"] not in descriptor["allowed_sources"]:
                raise ValueError("parameter source is not allowed")
            if binding["kind"] == "literal":
                _check(binding["value"], bounds, parameter)
                _check_semantics(binding["value"], capability, parameter)
                fixed.append(FixedSettingV1(step_id=step["step_id"], parameter=parameter, value=binding["value"]))
                continue
            name = binding["name"]
            semantics = {"network_target" if parameter == "target" else "bounded_text"} if value_type == "string" else set()
            if capability == "software.find" and parameter == "name": semantics.add("software_name")
            if not editable or declared.get(name) != value_type:
                raise ValueError("literal-only or undeclared input")
            if name in controls:
                previous = controls[name]
                semantics.update(previous.semantic_types)
                if previous.value_type != value_type:
                    raise ValueError("conflicting shared input types")
                minimum = max(x for x in (minimum, previous.minimum) if x is not None) if minimum is not None or previous.minimum is not None else None
                maximum = min(x for x in (maximum, previous.maximum) if x is not None) if maximum is not None or previous.maximum is not None else None
                if previous.enum_values is not None:
                    enums = set(previous.enum_values) if enums is None else enums & set(previous.enum_values)
            if minimum is not None and maximum is not None and minimum > maximum or enums == set():
                raise ValueError("conflicting shared input bounds")
            controls[name] = ToolInputV1(name=name, value_type=value_type, minimum=minimum, maximum=maximum,
                enum_values=tuple(sorted(enums)) if enums is not None else None, semantic_types=tuple(sorted(semantics)))
    if set(controls) != set(declared):
        raise ValueError("unused recipe inputs")
    return ToolInputSchemaV1(inputs=tuple(controls[name] for name in declared), fixed_settings=tuple(fixed),
        recipe=recipe, primitive_catalog=primitive_catalog)


def validate_tool_inputs(schema, inputs):
    if not isinstance(inputs, dict) or set(inputs) != {item.name for item in schema.inputs}:
        raise ValueError("inputs do not exactly match recipe")
    for item in schema.inputs:
        _check(inputs[item.name], (item.value_type, item.minimum, item.maximum, item.enum_values, True), item.name)
    for step in schema.recipe["steps"]:
        for parameter, binding in step["parameters"].items():
            value = binding["value"] if binding["kind"] == "literal" else inputs[binding["name"]]
            _check(value, PARAMETERS[step["capability"]][parameter], parameter)
            _check_semantics(value, step["capability"], parameter)
    return CanonicalToolInputsV1(inputs=inputs)
