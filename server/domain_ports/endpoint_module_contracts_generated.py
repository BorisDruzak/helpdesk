"""Generated public-contract DTOs. Regenerate with generate_endpoint_tool_contracts.py."""
from __future__ import annotations
from typing import Annotated, Literal
from uuid import UUID
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, StrictBool, StrictFloat, StrictInt, StrictStr

class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

class AdapterListResultV1(_Contract):
    adapter_count: Annotated[StrictInt, Field(ge=0, le=32)] = Field(ge=0, le=32)
    adapters: list[AdapterSummaryItemV1] = Field(default_factory=list, max_length=32)
    collected_at: AwareDatetime
    error_code: Annotated[StrictStr, Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]{0,63}$')] | None = Field(default=None)
    schema_version: Literal['adapter_list_result_v1']
    status: Literal['succeeded', 'failed']
    up_count: Annotated[StrictInt, Field(ge=0, le=32)] = Field(ge=0, le=32)

class AdapterSummaryItemV1(_Contract):
    ipv4_addresses: list[StrictStr] = Field(default_factory=list, max_length=4)
    ipv6_addresses: list[StrictStr] = Field(default_factory=list, max_length=4)
    kind: Literal['ethernet', 'wifi', 'loopback', 'tunnel', 'virtual', 'unknown']
    mtu: Annotated[StrictInt, Field(ge=0, le=65535)] = Field(ge=0, le=65535)
    name: Annotated[StrictStr, Field(min_length=1, max_length=128, pattern='^[A-Za-z0-9][A-Za-z0-9 ._:-]{0,127}$')] = Field(min_length=1, max_length=128, pattern='^[A-Za-z0-9][A-Za-z0-9 ._:-]{0,127}$')
    primary: StrictBool
    speed_mbps: Annotated[StrictInt, Field(ge=0, le=1000000)] = Field(ge=0, le=1000000)
    state: Literal['up', 'down', 'unknown']

class DnsResolveResultV1(_Contract):
    address_count: Annotated[StrictInt, Field(ge=0, le=16)] = Field(ge=0, le=16)
    addresses: list[NetworkAddressV1] = Field(default_factory=list, max_length=16)
    canonical_name: Annotated[StrictStr, Field(min_length=1, max_length=253)] | None = Field(default=None)
    collected_at: AwareDatetime
    error_code: Annotated[StrictStr, Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]{0,63}$')] | None = Field(default=None)
    schema_version: Literal['dns_resolve_result_v1']
    status: Literal['succeeded', 'failed']
    target: Annotated[StrictStr, Field(min_length=1, max_length=253)] = Field(min_length=1, max_length=253)

class EndpointCapabilityParameterDescriptorV1(_Contract):
    allowed_sources: list[Literal['input', 'literal']] = Field(min_length=1, max_length=2)
    default_literal: StrictStr | StrictInt | None
    enum_values: list[StrictStr] | None
    maximum: StrictInt | None
    minimum: StrictInt | None
    name: Annotated[StrictStr, Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]{0,63}$')] = Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]{0,63}$')
    required: StrictBool
    secret: Literal[False]
    value_type: Literal['string', 'integer', 'enum']

class EndpointDeviceModulesPageV1(_Contract):
    device_id: UUID
    items: list[PublishedDeviceModuleV1] = Field(max_length=100)
    next_cursor: Annotated[StrictStr, Field(max_length=1024)] | None
    observed_at: AwareDatetime
    schema_version: Literal['endpoint_device_modules_v1'] = Field(default='endpoint_device_modules_v1')

class EndpointRecipeModuleSpecV1(_Contract):
    inputs: list[ModuleRecipeInputV1] = Field(default_factory=list, max_length=8)
    module_key: Annotated[StrictStr, Field(min_length=3, max_length=128, pattern='^[a-z][a-z0-9]*(?:\\.[a-z][a-z0-9]*){1,7}$')] = Field(min_length=3, max_length=128, pattern='^[a-z][a-z0-9]*(?:\\.[a-z][a-z0-9]*){1,7}$')
    schema_version: Literal['endpoint_recipe_module_v1']
    steps: list[EndpointRecipeStepV1] = Field(min_length=1, max_length=8)
    supported_platforms: list[Literal['linux_amd64', 'windows_amd64']] = Field(min_length=1, max_length=2)

class EndpointRecipeStepV1(_Contract):
    capability: Literal['dns.resolve', 'network.ping', 'tcp.connect', 'route.get', 'adapter.list', 'system.service_status', 'system.resource_snapshot', 'process.list', 'process.find', 'service.list', 'service.status', 'printer.list', 'printer.status', 'printer.queue.summary', 'software.list', 'software.find', 'filesystem.free_space', 'filesystem.path_exists', 'filesystem.file_metadata', 'eventlog.query', 'eventlog.recent_errors']
    parameters: dict[Annotated[StrictStr, Field(pattern='^[a-z][a-z0-9_]{0,63}$', min_length=1, max_length=64)], Annotated[RecipeInputBindingV1 | RecipeLiteralBindingV1, Field(discriminator='kind')]] = Field(max_length=4)
    step_id: Annotated[StrictStr, Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]{0,63}$')] = Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]{0,63}$')

class EventFactV1(_Contract):
    event_id: Annotated[StrictInt, Field(ge=0, le=4294967295)] = Field(ge=0, le=4294967295)
    message_code: Annotated[StrictStr, Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]*$')] = Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]*$')
    provider: Annotated[StrictStr, Field(min_length=1, max_length=128, pattern='^[^\\x00-\\x1f\\x7f]+$')] = Field(min_length=1, max_length=128, pattern='^[^\\x00-\\x1f\\x7f]+$')
    severity: Literal['error', 'warning', 'information']
    timestamp: AwareDatetime

class EventQueryResultV1(_Contract):
    collected_at: AwareDatetime
    error_code: Annotated[StrictStr, Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]*$')] | None = Field(default=None)
    event_count: Annotated[StrictInt, Field(ge=0, le=32)] = Field(ge=0, le=32)
    events: list[EventFactV1] = Field(default_factory=list, max_length=32)
    schema_version: Literal['eventlog_query_result_v1']
    status: Literal['succeeded', 'failed']

class FileMetadataResultV1(_Contract):
    collected_at: AwareDatetime
    error_code: Annotated[StrictStr, Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]*$')] | None = Field(default=None)
    exists: StrictBool
    modified_at: AwareDatetime | None = Field(default=None)
    path_key: Literal['endpoint_runtime_manifest']
    schema_version: Literal['filesystem_file_metadata_result_v1']
    size: Annotated[StrictInt, Field(ge=0, le=9223372036854775807)] | None = Field(default=None)
    status: Literal['succeeded', 'failed']
    version: Annotated[StrictStr, Field(min_length=1, max_length=32)] | None = Field(default=None)

class FreeSpaceResultV1(_Contract):
    collected_at: AwareDatetime
    error_code: Annotated[StrictStr, Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]*$')] | None = Field(default=None)
    schema_version: Literal['filesystem_free_space_result_v1']
    status: Literal['succeeded', 'failed']
    volumes: list[VolumeFactV1] = Field(default_factory=list, max_length=16)

class ModuleCapabilityAuthoringV1(_Contract):
    capability: Literal['dns.resolve', 'network.ping', 'tcp.connect', 'route.get', 'adapter.list', 'system.service_status', 'system.resource_snapshot', 'process.list', 'process.find', 'service.list', 'service.status', 'printer.list', 'printer.status', 'printer.queue.summary', 'software.list', 'software.find', 'filesystem.free_space', 'filesystem.path_exists', 'filesystem.file_metadata', 'eventlog.query', 'eventlog.recent_errors']
    category: Literal['network', 'system', 'process', 'service', 'printer', 'software', 'eventlog', 'filesystem']
    consent_required: Literal[False]
    display_name_ru: Annotated[StrictStr, Field(min_length=1, max_length=128)] = Field(min_length=1, max_length=128)
    execution_timeout_seconds: Annotated[StrictInt, Field(ge=1, le=30)] = Field(ge=1, le=30)
    feature_flag: Literal['endpoint_network_primitives_enabled', 'endpoint_read_only_primitives_enabled', 'endpoint_system_primitives_enabled', 'endpoint_process_primitives_enabled', 'endpoint_printer_primitives_enabled', 'endpoint_software_primitives_enabled', 'endpoint_filesystem_primitives_enabled', 'endpoint_eventlog_primitives_enabled']
    max_result_items: Annotated[StrictInt, Field(ge=1, le=100)] = Field(ge=1, le=100)
    minimum_agent_version: Annotated[StrictStr, Field(min_length=5, max_length=32, pattern='^\\d+\\.\\d+\\.\\d+$')] = Field(min_length=5, max_length=32, pattern='^\\d+\\.\\d+\\.\\d+$')
    parameter_schema_version: Annotated[StrictStr, Field(min_length=1, max_length=128)] = Field(min_length=1, max_length=128)
    parameters: list[EndpointCapabilityParameterDescriptorV1] = Field(max_length=4)
    platforms: list[Literal['linux_amd64', 'windows_amd64']] = Field(min_length=1, max_length=2)
    policy: Literal['network_target_policy', 'none', 'process_metadata', 'service_catalog', 'local_printers', 'machine_software', 'local_volumes', 'logical_paths', 'event_profile']
    result_schema_version: Annotated[StrictStr, Field(min_length=1, max_length=128)] = Field(min_length=1, max_length=128)
    risk: Literal['safe_read', 'controlled_read']

class ModuleCapabilityCatalogV1(_Contract):
    items: list[ModuleCapabilityAuthoringV1] = Field(min_length=6, max_length=32)
    schema_version: Literal['endpoint_module_capability_catalog_v1']

class ModuleOperationCreateV1(_Contract):
    inputs: dict[Annotated[StrictStr, Field(pattern='^[a-z][a-z0-9_]{0,63}$', min_length=1, max_length=64)], StrictStr | StrictInt] = Field(min_length=0, max_length=8)
    module_key: Annotated[StrictStr, Field(min_length=3, max_length=128, pattern='^[a-z][a-z0-9]*(?:\\.[a-z][a-z0-9]*){1,7}$')] = Field(min_length=3, max_length=128, pattern='^[a-z][a-z0-9]*(?:\\.[a-z][a-z0-9]*){1,7}$')
    schema_version: Literal['endpoint_module_operation_create_v1']
    version: Annotated[StrictStr, Field(min_length=5, max_length=64, pattern='^\\d+\\.\\d+\\.\\d+$')] = Field(min_length=5, max_length=64, pattern='^\\d+\\.\\d+\\.\\d+$')

class ModuleOperationDetailV1(_Contract):
    completed_at: AwareDatetime | None = Field(default=None)
    created_at: AwareDatetime
    deadline_at: AwareDatetime
    device_id: UUID
    expected_step_count: Annotated[StrictInt, Field(ge=1, le=8)] = Field(ge=1, le=8)
    module_key: Annotated[StrictStr, Field(min_length=3, max_length=128, pattern='^[a-z][a-z0-9]*(?:\\.[a-z][a-z0-9]*){1,7}$')] = Field(min_length=3, max_length=128, pattern='^[a-z][a-z0-9]*(?:\\.[a-z][a-z0-9]*){1,7}$')
    operation_id: UUID
    schema_version: Literal['endpoint_module_operation_v1']
    status: Literal['queued', 'delivered', 'acknowledged', 'running', 'succeeded', 'failed', 'canceled', 'expired']
    steps: list[ModuleOperationStepV1] = Field(min_length=1, max_length=8)
    version: Annotated[StrictStr, Field(min_length=5, max_length=64, pattern='^\\d+\\.\\d+\\.\\d+$')] = Field(min_length=5, max_length=64, pattern='^\\d+\\.\\d+\\.\\d+$')

class ModuleOperationStepV1(_Contract):
    capability: Literal['dns.resolve', 'network.ping', 'tcp.connect', 'route.get', 'adapter.list', 'system.service_status', 'system.resource_snapshot', 'process.list', 'process.find', 'service.list', 'service.status', 'printer.list', 'printer.status', 'printer.queue.summary', 'software.list', 'software.find', 'filesystem.free_space', 'filesystem.path_exists', 'filesystem.file_metadata', 'eventlog.query', 'eventlog.recent_errors']
    error_code: Annotated[StrictStr, Field(min_length=3, max_length=64, pattern='^[a-z][a-z0-9_]{1,63}$')] | None = Field(default=None)
    safe_result: Annotated[DnsResolveResultV1 | NetworkPingResultV1 | TcpConnectResultV1 | RouteGetResultV1 | AdapterListResultV1 | endpoint_contracts__read_only_primitives__ServiceStatusResultV1 | SystemResourceSnapshotResultV1 | ProcessListResultV1 | ProcessFindResultV1 | ServiceListResultV1 | endpoint_contracts__service_printer_primitives__ServiceStatusResultV1 | PrinterListResultV1 | PrinterStatusResultV1 | PrinterQueueSummaryResultV1 | SoftwareListResultV1 | SoftwareFindResultV1 | FreeSpaceResultV1 | PathExistsResultV1 | FileMetadataResultV1 | EventQueryResultV1 | RecentErrorsResultV1, Field(discriminator='schema_version')] | None = Field(default=None)
    sequence: Annotated[StrictInt, Field(ge=0, le=7)] = Field(ge=0, le=7)
    status: Literal['queued', 'delivered', 'acknowledged', 'running', 'succeeded', 'failed', 'canceled', 'expired']

class ModuleOperationV1(_Contract):
    completed_at: AwareDatetime | None = Field(default=None)
    created_at: AwareDatetime
    deadline_at: AwareDatetime
    device_id: UUID
    module_key: Annotated[StrictStr, Field(min_length=3, max_length=128, pattern='^[a-z][a-z0-9]*(?:\\.[a-z][a-z0-9]*){1,7}$')] = Field(min_length=3, max_length=128, pattern='^[a-z][a-z0-9]*(?:\\.[a-z][a-z0-9]*){1,7}$')
    operation_id: UUID
    schema_version: Literal['endpoint_module_operation_v1']
    status: Literal['queued', 'delivered', 'acknowledged', 'running', 'succeeded', 'failed', 'canceled', 'expired']
    version: Annotated[StrictStr, Field(min_length=5, max_length=64, pattern='^\\d+\\.\\d+\\.\\d+$')] = Field(min_length=5, max_length=64, pattern='^\\d+\\.\\d+\\.\\d+$')

class ModuleRecipeInputV1(_Contract):
    name: Annotated[StrictStr, Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]{0,63}$')] = Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]{0,63}$')
    value_type: Literal['string', 'integer']

class ModuleVersionViewV1(_Contract):
    display_name: Annotated[StrictStr, Field(min_length=1, max_length=128)] = Field(min_length=1, max_length=128)
    module_key: Annotated[StrictStr, Field(min_length=3, max_length=128, pattern='^[a-z][a-z0-9]*(?:\\.[a-z][a-z0-9]*){1,7}$')] = Field(min_length=3, max_length=128, pattern='^[a-z][a-z0-9]*(?:\\.[a-z][a-z0-9]*){1,7}$')
    recipe: EndpointRecipeModuleSpecV1
    state: Literal['draft', 'validation_failed', 'validated', 'lab_accepted', 'published', 'deprecated', 'revoked']
    version: Annotated[StrictStr, Field(min_length=5, max_length=64, pattern='^\\d+\\.\\d+\\.\\d+$')] = Field(min_length=5, max_length=64, pattern='^\\d+\\.\\d+\\.\\d+$')

class NetworkAddressV1(_Contract):
    address: Annotated[StrictStr, Field(min_length=1, max_length=253)] = Field(min_length=1, max_length=253)
    family: Literal['ipv4', 'ipv6']

class NetworkPingResultV1(_Contract):
    avg_ms: Annotated[StrictFloat, Field(ge=0, le=60000)] | None = Field(default=None)
    collected_at: AwareDatetime
    error_code: Annotated[StrictStr, Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]{0,63}$')] | None = Field(default=None)
    max_ms: Annotated[StrictFloat, Field(ge=0, le=60000)] | None = Field(default=None)
    min_ms: Annotated[StrictFloat, Field(ge=0, le=60000)] | None = Field(default=None)
    packet_loss_percent: Annotated[StrictFloat, Field(ge=0, le=100)] = Field(ge=0, le=100)
    reachable: StrictBool
    received: Annotated[StrictInt, Field(ge=0, le=5)] = Field(ge=0, le=5)
    resolved_ip: Annotated[StrictStr, Field(min_length=1, max_length=253)] | None = Field(default=None)
    schema_version: Literal['network_ping_result_v1']
    status: Literal['succeeded', 'failed']
    target: Annotated[StrictStr, Field(min_length=1, max_length=253)] = Field(min_length=1, max_length=253)
    transmitted: Annotated[StrictInt, Field(ge=0, le=5)] = Field(ge=0, le=5)

class PathExistsResultV1(_Contract):
    collected_at: AwareDatetime
    error_code: Annotated[StrictStr, Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]*$')] | None = Field(default=None)
    exists: StrictBool
    kind: Literal['file', 'directory', 'other', 'missing']
    path_key: Literal['endpoint_install_root', 'endpoint_data_root', 'endpoint_runtime_manifest']
    schema_version: Literal['filesystem_path_exists_result_v1']
    status: Literal['succeeded', 'failed']

class PrinterFactV1(_Contract):
    default: StrictBool
    driver_name: Annotated[StrictStr, Field(min_length=1, max_length=128)] | None = Field(default=None)
    name: Annotated[StrictStr, Field(min_length=1, max_length=128, pattern='^[^\\x00-\\x1f\\x7f]+$')] = Field(min_length=1, max_length=128, pattern='^[^\\x00-\\x1f\\x7f]+$')
    port_type: Literal['local', 'network', 'usb', 'virtual', 'unknown']
    state: Literal['ready', 'offline', 'paused', 'error', 'unknown']

class PrinterListResultV1(_Contract):
    collected_at: AwareDatetime
    error_code: Annotated[StrictStr, Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]*$')] | None = Field(default=None)
    printers: list[PrinterFactV1] = Field(default_factory=list, max_length=16)
    schema_version: Literal['printer_list_result_v1']
    status: Literal['succeeded', 'failed']

class PrinterQueueSummaryResultV1(_Contract):
    collected_at: AwareDatetime
    error_code: Annotated[StrictStr, Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]*$')] | None = Field(default=None)
    error_count: Annotated[StrictInt, Field(ge=0, le=10000)] = Field(ge=0, le=10000)
    job_count: Annotated[StrictInt, Field(ge=0, le=10000)] = Field(ge=0, le=10000)
    oldest_job_age_seconds: Annotated[StrictInt, Field(ge=0, le=31536000)] | None = Field(default=None)
    paused_count: Annotated[StrictInt, Field(ge=0, le=10000)] = Field(ge=0, le=10000)
    printing_count: Annotated[StrictInt, Field(ge=0, le=10000)] = Field(ge=0, le=10000)
    queued_count: Annotated[StrictInt, Field(ge=0, le=10000)] = Field(ge=0, le=10000)
    schema_version: Literal['printer_queue_summary_result_v1']
    status: Literal['succeeded', 'failed']

class PrinterStatusResultV1(_Contract):
    collected_at: AwareDatetime
    error: StrictBool
    error_code: Annotated[StrictStr, Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]*$')] | None = Field(default=None)
    exists: StrictBool
    offline: StrictBool
    paused: StrictBool
    schema_version: Literal['printer_status_result_v1']
    state: Literal['ready', 'offline', 'paused', 'error', 'unknown']
    status: Literal['succeeded', 'failed']

class ProcessFindResultV1(_Contract):
    collected_at: AwareDatetime
    error_code: Annotated[StrictStr, Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]*$')] | None = Field(default=None)
    matches: list[ProcessSummaryV1] = Field(default_factory=list, max_length=20)
    present: StrictBool
    process_count: Annotated[StrictInt, Field(ge=0, le=2147483647)] = Field(ge=0, le=2147483647)
    schema_version: Literal['process_find_result_v1']
    status: Literal['succeeded', 'failed']

class ProcessListResultV1(_Contract):
    collected_at: AwareDatetime
    error_code: Annotated[StrictStr, Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]*$')] | None = Field(default=None)
    process_count: Annotated[StrictInt, Field(ge=0, le=32)] = Field(ge=0, le=32)
    processes: list[ProcessSummaryV1] = Field(default_factory=list, max_length=32)
    schema_version: Literal['process_list_result_v1']
    status: Literal['succeeded', 'failed']

class ProcessSummaryV1(_Contract):
    cpu_percent: Annotated[StrictFloat, Field(ge=0, le=10000)] | None = Field(default=None)
    memory_bytes: Annotated[StrictInt, Field(ge=0, le=9223372036854775807)] | None = Field(default=None)
    name: Annotated[StrictStr, Field(min_length=1, max_length=128, pattern='^[^\\x00-\\x1f\\x7f]+$')] = Field(min_length=1, max_length=128, pattern='^[^\\x00-\\x1f\\x7f]+$')
    pid: Annotated[StrictInt, Field(ge=0, le=2147483647)] = Field(ge=0, le=2147483647)
    state: Annotated[StrictStr, Field(min_length=1, max_length=32, pattern='^[a-z_]+$')] = Field(min_length=1, max_length=32, pattern='^[a-z_]+$')

class PublishedDeviceModuleV1(_Contract):
    availability: Literal['available', 'unavailable', 'unknown']
    display_name: Annotated[StrictStr, Field(min_length=1, max_length=128)] = Field(min_length=1, max_length=128)
    module_key: Annotated[StrictStr, Field(min_length=3, max_length=128, pattern='^[a-z][a-z0-9]*(?:\\.[a-z][a-z0-9]*){1,7}$')] = Field(min_length=3, max_length=128, pattern='^[a-z][a-z0-9]*(?:\\.[a-z][a-z0-9]*){1,7}$')
    reason_code: Literal['device_offline', 'agent_facts_missing', 'platform_unsupported', 'agent_version_unsupported', 'capability_not_announced', 'feature_disabled', 'network_policy_missing', 'invalid_recipe'] | None
    recipe: EndpointRecipeModuleSpecV1 | None
    state: Literal['published'] = Field(default='published')
    version: Annotated[StrictStr, Field(min_length=1, max_length=64)] = Field(min_length=1, max_length=64)

class RecentErrorsResultV1(_Contract):
    collected_at: AwareDatetime
    error_code: Annotated[StrictStr, Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]*$')] | None = Field(default=None)
    event_count: Annotated[StrictInt, Field(ge=0, le=20)] = Field(ge=0, le=20)
    events: list[EventFactV1] = Field(default_factory=list, max_length=20)
    schema_version: Literal['eventlog_recent_errors_result_v1']
    status: Literal['succeeded', 'failed']

class RecipeInputBindingV1(_Contract):
    kind: Literal['input']
    name: Annotated[StrictStr, Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]{0,63}$')] = Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]{0,63}$')

class RecipeLiteralBindingV1(_Contract):
    kind: Literal['literal']
    value: StrictStr | StrictInt

class RouteGetResultV1(_Contract):
    collected_at: AwareDatetime
    error_code: Annotated[StrictStr, Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]{0,63}$')] | None = Field(default=None)
    family: Literal['ipv4', 'ipv6'] | None = Field(default=None)
    interface_name: Annotated[StrictStr, Field(min_length=1, max_length=128, pattern='^[A-Za-z0-9][A-Za-z0-9 ._:-]{0,127}$')] | None = Field(default=None)
    port: Annotated[StrictInt, Field(ge=1, le=65535)] = Field(ge=1, le=65535)
    resolved_ip: StrictStr | None = Field(default=None)
    schema_version: Literal['route_get_result_v1']
    source_ip: StrictStr | None = Field(default=None)
    status: Literal['succeeded', 'failed']
    strategy: Literal['udp_socket_inference'] = Field(default='udp_socket_inference')
    target: Annotated[StrictStr, Field(min_length=1, max_length=253)] = Field(min_length=1, max_length=253)

class ServiceFactV1(_Contract):
    display_name: Annotated[StrictStr, Field(min_length=1, max_length=128)] = Field(min_length=1, max_length=128)
    installed: StrictBool
    service_key: Literal['endpoint_agent', 'endpoint_agent_updater', 'print_service']
    startup_type: Literal['automatic', 'manual', 'disabled', 'unknown']
    state: Literal['running', 'stopped', 'paused', 'failed', 'not_found', 'unknown']

class ServiceListResultV1(_Contract):
    collected_at: AwareDatetime
    error_code: Annotated[StrictStr, Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]*$')] | None = Field(default=None)
    schema_version: Literal['service_list_result_v1']
    services: list[ServiceFactV1] = Field(default_factory=list, max_length=3)
    status: Literal['succeeded', 'failed']

class SoftwareFactV1(_Contract):
    architecture: Annotated[StrictStr, Field(min_length=1, max_length=32)] | None = Field(default=None)
    name: Annotated[StrictStr, Field(min_length=1, max_length=128, pattern='^[^\\x00-\\x1f\\x7f]+$')] = Field(min_length=1, max_length=128, pattern='^[^\\x00-\\x1f\\x7f]+$')
    publisher: Annotated[StrictStr, Field(min_length=1, max_length=128, pattern='^[^\\x00-\\x1f\\x7f]+$')] | None = Field(default=None)
    source: Literal['windows_registry', 'alt_rpm']
    version: Annotated[StrictStr, Field(min_length=1, max_length=64)] | None = Field(default=None)

class SoftwareFindResultV1(_Contract):
    collected_at: AwareDatetime
    error_code: Annotated[StrictStr, Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]*$')] | None = Field(default=None)
    matches: list[SoftwareFactV1] = Field(default_factory=list, max_length=20)
    present: StrictBool
    schema_version: Literal['software_find_result_v1']
    status: Literal['succeeded', 'failed']

class SoftwareListResultV1(_Contract):
    collected_at: AwareDatetime
    error_code: Annotated[StrictStr, Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]*$')] | None = Field(default=None)
    schema_version: Literal['software_list_result_v1']
    software: list[SoftwareFactV1] = Field(default_factory=list, max_length=32)
    status: Literal['succeeded', 'failed']

class SystemResourceSnapshotResultV1(_Contract):
    collected_at: AwareDatetime
    cpu_percent: Annotated[StrictFloat, Field(ge=0, le=100)] | None = Field(default=None)
    error_code: Annotated[StrictStr, Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]*$')] | None = Field(default=None)
    memory_available_bytes: Annotated[StrictInt, Field(ge=0, le=9223372036854775807)] | None = Field(default=None)
    memory_total_bytes: Annotated[StrictInt, Field(ge=0, le=9223372036854775807)] | None = Field(default=None)
    schema_version: Literal['system_resource_snapshot_result_v1']
    status: Literal['succeeded', 'failed']
    system_drive_free_bytes: Annotated[StrictInt, Field(ge=0, le=9223372036854775807)] | None = Field(default=None)
    uptime_seconds: Annotated[StrictInt, Field(ge=0, le=9223372036854775807)] | None = Field(default=None)

class TcpConnectResultV1(_Contract):
    collected_at: AwareDatetime
    error_code: Annotated[StrictStr, Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]{0,63}$')] | None = Field(default=None)
    latency_ms: Annotated[StrictFloat, Field(ge=0, le=60000)] | None = Field(default=None)
    port: Annotated[StrictInt, Field(ge=1, le=65535)] = Field(ge=1, le=65535)
    reachable: StrictBool
    resolved_ip: Annotated[StrictStr, Field(min_length=1, max_length=253)] | None = Field(default=None)
    schema_version: Literal['tcp_connect_result_v1']
    status: Literal['succeeded', 'failed']
    target: Annotated[StrictStr, Field(min_length=1, max_length=253)] = Field(min_length=1, max_length=253)

class VolumeFactV1(_Contract):
    filesystem_type: Annotated[StrictStr, Field(min_length=1, max_length=32, pattern='^[A-Za-z0-9._-]+$')] = Field(min_length=1, max_length=32, pattern='^[A-Za-z0-9._-]+$')
    free_bytes: Annotated[StrictInt, Field(ge=0, le=9223372036854775807)] = Field(ge=0, le=9223372036854775807)
    total_bytes: Annotated[StrictInt, Field(ge=0, le=9223372036854775807)] = Field(ge=0, le=9223372036854775807)
    volume_key: Annotated[StrictStr, Field(min_length=1, max_length=32, pattern='^(?:system|local_[1-9][0-9]?)$')] = Field(min_length=1, max_length=32, pattern='^(?:system|local_[1-9][0-9]?)$')

class endpoint_contracts__read_only_primitives__ServiceStatusResultV1(_Contract):
    collected_at: AwareDatetime
    error_code: Annotated[StrictStr, Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]{0,63}$')] | None = Field(default=None)
    installed: StrictBool
    schema_version: Literal['service_status_result_v1']
    service_key: Literal['endpoint_agent', 'endpoint_agent_updater']
    start_mode: Literal['automatic', 'manual', 'disabled', 'unknown']
    state: Literal['running', 'stopped', 'paused', 'failed', 'not_found', 'unknown']
    status: Literal['succeeded', 'failed']

class endpoint_contracts__service_printer_primitives__ServiceStatusResultV1(_Contract):
    collected_at: AwareDatetime
    error_code: Annotated[StrictStr, Field(min_length=1, max_length=64, pattern='^[a-z][a-z0-9_]*$')] | None = Field(default=None)
    schema_version: Literal['service_status_v2_result_v1']
    service: ServiceFactV1 | None = Field(default=None)
    status: Literal['succeeded', 'failed']

for _model in (AdapterListResultV1, AdapterSummaryItemV1, DnsResolveResultV1, EndpointCapabilityParameterDescriptorV1, EndpointDeviceModulesPageV1, EndpointRecipeModuleSpecV1, EndpointRecipeStepV1, EventFactV1, EventQueryResultV1, FileMetadataResultV1, FreeSpaceResultV1, ModuleCapabilityAuthoringV1, ModuleCapabilityCatalogV1, ModuleOperationCreateV1, ModuleOperationDetailV1, ModuleOperationStepV1, ModuleOperationV1, ModuleRecipeInputV1, ModuleVersionViewV1, NetworkAddressV1, NetworkPingResultV1, PathExistsResultV1, PrinterFactV1, PrinterListResultV1, PrinterQueueSummaryResultV1, PrinterStatusResultV1, ProcessFindResultV1, ProcessListResultV1, ProcessSummaryV1, PublishedDeviceModuleV1, RecentErrorsResultV1, RecipeInputBindingV1, RecipeLiteralBindingV1, RouteGetResultV1, ServiceFactV1, ServiceListResultV1, SoftwareFactV1, SoftwareFindResultV1, SoftwareListResultV1, SystemResourceSnapshotResultV1, TcpConnectResultV1, VolumeFactV1, endpoint_contracts__read_only_primitives__ServiceStatusResultV1, endpoint_contracts__service_printer_primitives__ServiceStatusResultV1):
    _model.model_rebuild()
