"""Semantic checks supplement public JSON Schema constraints."""
import ipaddress
import re

_HOSTNAME = re.compile(r"(?=.{1,253}\Z)[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*\.?\Z")


def _validate_network_fact(value):
    if type(value) is not str or value != value.strip() or len(value) > 253 or "%" in value:
        raise ValueError("invalid network fact")
    try:
        ipaddress.ip_address(value)
    except ValueError:
        if _HOSTNAME.fullmatch(value) is None:
            raise ValueError("network fact must be hostname or IP") from None

try:
    from domain_ports.endpoint_module_contracts_generated import EndpointRecipeModuleSpecV1
except ModuleNotFoundError as error:
    if error.name != "domain_ports":
        raise
    from server.domain_ports.endpoint_module_contracts_generated import EndpointRecipeModuleSpecV1


def validate_module_projection(projection):
    """Reject contradictory metadata, recipes, lifecycle and safe result facts."""
    if hasattr(projection, "recipe"):
        if projection.recipe is not None:
            recipe = EndpointRecipeModuleSpecV1.model_validate(
                projection.recipe.model_dump() if hasattr(projection.recipe, "model_dump") else projection.recipe)
            if recipe.module_key != projection.module_key:
                raise ValueError("module recipe identity mismatch")
            names = [item.name for item in recipe.inputs]
            steps = [item.step_id for item in recipe.steps]
            if len(names) != len(set(names)) or len(steps) != len(set(steps)):
                raise ValueError("duplicate recipe identifiers")
            for step in recipe.steps:
                if any(binding.kind == "input" and binding.name not in names for binding in step.parameters.values()):
                    raise ValueError("undeclared recipe input")
        elif getattr(projection, "reason_code", None) != "invalid_recipe":
            raise ValueError("missing recipe")
    if hasattr(projection, "availability"):
        if (projection.availability == "available") != (projection.reason_code is None):
            raise ValueError("availability reason mismatch")
    if hasattr(projection, "items"):
        for item in projection.items:
            validate_module_projection(item)
        if hasattr(projection, "schema_version") and projection.schema_version == "endpoint_module_capability_catalog_v1":
            names = [item.capability for item in projection.items]
            if len(names) != len(set(names)):
                raise ValueError("duplicate primitive metadata")
    if hasattr(projection, "parameters") and isinstance(projection.parameters, list):
        names = [item.name for item in projection.parameters]
        if len(names) != len(set(names)):
            raise ValueError("duplicate parameter metadata")
        for descriptor in projection.parameters:
            if descriptor.minimum is not None and descriptor.maximum is not None and descriptor.minimum > descriptor.maximum:
                raise ValueError("contradictory parameter bounds")
    if hasattr(projection, "expected_step_count"):
        if len(projection.steps) != projection.expected_step_count or [item.sequence for item in projection.steps] != list(range(projection.expected_step_count)):
            raise ValueError("incomplete operation step sequence")
        for step in projection.steps:
            if step.safe_result is not None:
                validate_safe_result(step.capability, step.safe_result)
    return projection


CAPABILITY_RESULT_SCHEMAS = {
    "dns.resolve": "dns_resolve_result_v1", "network.ping": "network_ping_result_v1",
    "tcp.connect": "tcp_connect_result_v1", "route.get": "route_get_result_v1",
    "adapter.list": "adapter_list_result_v1", "system.service_status": "service_status_result_v1",
    "system.resource_snapshot": "system_resource_snapshot_result_v1", "process.list": "process_list_result_v1",
    "process.find": "process_find_result_v1", "service.list": "service_list_result_v1", "service.status": "service_status_v2_result_v1",
    "printer.list": "printer_list_result_v1", "printer.status": "printer_status_result_v1", "printer.queue.summary": "printer_queue_summary_result_v1",
    "software.list": "software_list_result_v1", "software.find": "software_find_result_v1",
    "filesystem.free_space": "filesystem_free_space_result_v1", "filesystem.path_exists": "filesystem_path_exists_result_v1",
    "filesystem.file_metadata": "filesystem_file_metadata_result_v1", "eventlog.query": "eventlog_query_result_v1",
    "eventlog.recent_errors": "eventlog_recent_errors_result_v1",
}


def validate_safe_result(capability, result):
    if result.schema_version != CAPABILITY_RESULT_SCHEMAS.get(capability):
        raise ValueError("result does not belong to capability")
    payload = result.model_dump(mode="json")
    status = payload.get("status")
    for field in ("target", "canonical_name"):
        if payload.get(field) is not None:
            _validate_network_fact(payload[field])
    if status == "succeeded" and payload.get("error_code") is not None:
        raise ValueError("successful result contains an error")
    if status == "failed" and payload.get("error_code") is None:
        raise ValueError("failed result lacks an error")
    if capability == "system.resource_snapshot":
        required = ("uptime_seconds", "cpu_percent", "memory_total_bytes", "memory_available_bytes", "system_drive_free_bytes")
        if status == "succeeded" and any(payload.get(field) is None for field in required):
            raise ValueError("successful resource snapshot lacks facts")
        if payload.get("memory_total_bytes") is not None and payload.get("memory_available_bytes") is not None and payload["memory_available_bytes"] > payload["memory_total_bytes"]:
            raise ValueError("available memory exceeds total memory")
    for count, items in (("address_count", "addresses"), ("adapter_count", "adapters"),
        ("process_count", "processes"), ("service_count", "services"), ("printer_count", "printers"),
        ("software_count", "software"), ("event_count", "events")):
        if count in payload and items in payload and payload[count] != len(payload[items]):
            raise ValueError("result count mismatch")
    if "received" in payload and "transmitted" in payload and payload["received"] > payload["transmitted"]:
        raise ValueError("ping received exceeds transmitted")
    if capability == "network.ping":
        latencies = payload["min_ms"], payload["avg_ms"], payload["max_ms"]
        if payload["reachable"] != (payload["received"] > 0):
            raise ValueError("ping reachability mismatch")
        if payload["received"] == 0 and any(value is not None for value in latencies) or payload["received"] > 0 and any(value is None for value in latencies):
            raise ValueError("ping latency availability mismatch")
        if all(value is not None for value in latencies) and not latencies[0] <= latencies[1] <= latencies[2]:
            raise ValueError("ping latencies are unordered")
    if capability == "tcp.connect" and payload["reachable"] != (payload["latency_ms"] is not None):
        raise ValueError("TCP reachability mismatch")
    if capability == "route.get":
        fields = "resolved_ip", "source_ip", "family"
        if status == "succeeded":
            if any(payload.get(field) is None for field in fields):
                raise ValueError("route facts missing")
            if ipaddress.ip_address(payload["resolved_ip"]).version != (4 if payload["family"] == "ipv4" else 6):
                raise ValueError("route family mismatch")
        elif any(payload.get(field) is not None for field in (*fields, "interface_name")):
            raise ValueError("failed route contains success facts")
    if capability == "adapter.list":
        adapters = payload["adapters"]
        if payload["up_count"] != sum(item["state"] == "up" for item in adapters) or len({item["name"] for item in adapters}) != len(adapters):
            raise ValueError("adapter aggregate mismatch")
        for adapter in adapters:
            for family, version in (("ipv4_addresses", 4), ("ipv6_addresses", 6)):
                if any(ipaddress.ip_address(address).version != version for address in adapter[family]):
                    raise ValueError("adapter address family mismatch")
    if capability == "process.find" and (payload["present"] != (payload["process_count"] > 0) or payload["process_count"] < len(payload["matches"])):
        raise ValueError("process presence mismatch")
    if capability == "service.status" and status == "succeeded" and payload["service"] is None:
        raise ValueError("successful service result lacks facts")
    if capability == "printer.queue.summary" and any(payload[field] > payload["job_count"] for field in ("printing_count", "queued_count", "paused_count", "error_count")):
        raise ValueError("queue count exceeds total")
    if capability == "software.find" and status == "succeeded" and payload["present"] != bool(payload["matches"]):
        raise ValueError("software presence mismatch")
    if capability == "filesystem.file_metadata" and status == "succeeded" and payload["exists"] and (payload["size"] is None or payload["modified_at"] is None):
        raise ValueError("existing file lacks safe metadata")
    for field in ("resolved_ip", "source_ip"):
        if payload.get(field) is not None:
            ipaddress.ip_address(payload[field])
    for record in payload.get("addresses", []):
        address = ipaddress.ip_address(record["address"])
        if record["family"] != ("ipv4" if address.version == 4 else "ipv6"):
            raise ValueError("IP family mismatch")
    return result
