// Generated from the accepted public module-operation schema. Do not edit.

export type AdapterListResultV1 = {
  readonly "adapter_count": number;
  readonly "adapters"?: ReadonlyArray<AdapterSummaryItemV1>;
  readonly "collected_at": string;
  readonly "error_code"?: string | null;
  readonly "schema_version": "adapter_list_result_v1";
  readonly "status": "succeeded" | "failed";
  readonly "up_count": number;
};

export type AdapterSummaryItemV1 = {
  readonly "ipv4_addresses"?: ReadonlyArray<string>;
  readonly "ipv6_addresses"?: ReadonlyArray<string>;
  readonly "kind": "ethernet" | "wifi" | "loopback" | "tunnel" | "virtual" | "unknown";
  readonly "mtu": number;
  readonly "name": string;
  readonly "primary": boolean;
  readonly "speed_mbps": number;
  readonly "state": "up" | "down" | "unknown";
};

export type DnsResolveResultV1 = {
  readonly "address_count": number;
  readonly "addresses"?: ReadonlyArray<NetworkAddressV1>;
  readonly "canonical_name"?: string | null;
  readonly "collected_at": string;
  readonly "error_code"?: string | null;
  readonly "schema_version": "dns_resolve_result_v1";
  readonly "status": "succeeded" | "failed";
  readonly "target": string;
};

export type EventFactV1 = {
  readonly "event_id": number;
  readonly "message_code": string;
  readonly "provider": string;
  readonly "severity": "error" | "warning" | "information";
  readonly "timestamp": string;
};

export type EventQueryResultV1 = {
  readonly "collected_at": string;
  readonly "error_code"?: string | null;
  readonly "event_count": number;
  readonly "events"?: ReadonlyArray<EventFactV1>;
  readonly "schema_version": "eventlog_query_result_v1";
  readonly "status": "succeeded" | "failed";
};

export type FileMetadataResultV1 = {
  readonly "collected_at": string;
  readonly "error_code"?: string | null;
  readonly "exists": boolean;
  readonly "modified_at"?: string | null;
  readonly "path_key": "endpoint_runtime_manifest";
  readonly "schema_version": "filesystem_file_metadata_result_v1";
  readonly "size"?: number | null;
  readonly "status": "succeeded" | "failed";
  readonly "version"?: string | null;
};

export type FreeSpaceResultV1 = {
  readonly "collected_at": string;
  readonly "error_code"?: string | null;
  readonly "schema_version": "filesystem_free_space_result_v1";
  readonly "status": "succeeded" | "failed";
  readonly "volumes"?: ReadonlyArray<VolumeFactV1>;
};

export type ModuleOperationStepV1 = {
  readonly "capability": "dns.resolve" | "network.ping" | "tcp.connect" | "route.get" | "adapter.list" | "system.service_status" | "system.resource_snapshot" | "process.list" | "process.find" | "service.list" | "service.status" | "printer.list" | "printer.status" | "printer.queue.summary" | "software.list" | "software.find" | "filesystem.free_space" | "filesystem.path_exists" | "filesystem.file_metadata" | "eventlog.query" | "eventlog.recent_errors";
  readonly "error_code"?: string | null;
  readonly "safe_result"?: DnsResolveResultV1 | NetworkPingResultV1 | TcpConnectResultV1 | RouteGetResultV1 | AdapterListResultV1 | endpoint_contracts__read_only_primitives__ServiceStatusResultV1 | SystemResourceSnapshotResultV1 | ProcessListResultV1 | ProcessFindResultV1 | ServiceListResultV1 | endpoint_contracts__service_printer_primitives__ServiceStatusResultV1 | PrinterListResultV1 | PrinterStatusResultV1 | PrinterQueueSummaryResultV1 | SoftwareListResultV1 | SoftwareFindResultV1 | FreeSpaceResultV1 | PathExistsResultV1 | FileMetadataResultV1 | EventQueryResultV1 | RecentErrorsResultV1 | null;
  readonly "sequence": number;
  readonly "status": "queued" | "delivered" | "acknowledged" | "running" | "succeeded" | "failed" | "canceled" | "expired";
};

export type NetworkAddressV1 = {
  readonly "address": string;
  readonly "family": "ipv4" | "ipv6";
};

export type NetworkPingResultV1 = {
  readonly "avg_ms"?: number | null;
  readonly "collected_at": string;
  readonly "error_code"?: string | null;
  readonly "max_ms"?: number | null;
  readonly "min_ms"?: number | null;
  readonly "packet_loss_percent": number;
  readonly "reachable": boolean;
  readonly "received": number;
  readonly "resolved_ip"?: string | null;
  readonly "schema_version": "network_ping_result_v1";
  readonly "status": "succeeded" | "failed";
  readonly "target": string;
  readonly "transmitted": number;
};

export type PathExistsResultV1 = {
  readonly "collected_at": string;
  readonly "error_code"?: string | null;
  readonly "exists": boolean;
  readonly "kind": "file" | "directory" | "other" | "missing";
  readonly "path_key": "endpoint_install_root" | "endpoint_data_root" | "endpoint_runtime_manifest";
  readonly "schema_version": "filesystem_path_exists_result_v1";
  readonly "status": "succeeded" | "failed";
};

export type PrinterFactV1 = {
  readonly "default": boolean;
  readonly "driver_name"?: string | null;
  readonly "name": string;
  readonly "port_type": "local" | "network" | "usb" | "virtual" | "unknown";
  readonly "state": "ready" | "offline" | "paused" | "error" | "unknown";
};

export type PrinterListResultV1 = {
  readonly "collected_at": string;
  readonly "error_code"?: string | null;
  readonly "printers"?: ReadonlyArray<PrinterFactV1>;
  readonly "schema_version": "printer_list_result_v1";
  readonly "status": "succeeded" | "failed";
};

export type PrinterQueueSummaryResultV1 = {
  readonly "collected_at": string;
  readonly "error_code"?: string | null;
  readonly "error_count": number;
  readonly "job_count": number;
  readonly "oldest_job_age_seconds"?: number | null;
  readonly "paused_count": number;
  readonly "printing_count": number;
  readonly "queued_count": number;
  readonly "schema_version": "printer_queue_summary_result_v1";
  readonly "status": "succeeded" | "failed";
};

export type PrinterStatusResultV1 = {
  readonly "collected_at": string;
  readonly "error": boolean;
  readonly "error_code"?: string | null;
  readonly "exists": boolean;
  readonly "offline": boolean;
  readonly "paused": boolean;
  readonly "schema_version": "printer_status_result_v1";
  readonly "state": "ready" | "offline" | "paused" | "error" | "unknown";
  readonly "status": "succeeded" | "failed";
};

export type ProcessFindResultV1 = {
  readonly "collected_at": string;
  readonly "error_code"?: string | null;
  readonly "matches"?: ReadonlyArray<ProcessSummaryV1>;
  readonly "present": boolean;
  readonly "process_count": number;
  readonly "schema_version": "process_find_result_v1";
  readonly "status": "succeeded" | "failed";
};

export type ProcessListResultV1 = {
  readonly "collected_at": string;
  readonly "error_code"?: string | null;
  readonly "process_count": number;
  readonly "processes"?: ReadonlyArray<ProcessSummaryV1>;
  readonly "schema_version": "process_list_result_v1";
  readonly "status": "succeeded" | "failed";
};

export type ProcessSummaryV1 = {
  readonly "cpu_percent"?: number | null;
  readonly "memory_bytes"?: number | null;
  readonly "name": string;
  readonly "pid": number;
  readonly "state": string;
};

export type RecentErrorsResultV1 = {
  readonly "collected_at": string;
  readonly "error_code"?: string | null;
  readonly "event_count": number;
  readonly "events"?: ReadonlyArray<EventFactV1>;
  readonly "schema_version": "eventlog_recent_errors_result_v1";
  readonly "status": "succeeded" | "failed";
};

export type RouteGetResultV1 = {
  readonly "collected_at": string;
  readonly "error_code"?: string | null;
  readonly "family"?: "ipv4" | "ipv6" | null;
  readonly "interface_name"?: string | null;
  readonly "port": number;
  readonly "resolved_ip"?: string | null;
  readonly "schema_version": "route_get_result_v1";
  readonly "source_ip"?: string | null;
  readonly "status": "succeeded" | "failed";
  readonly "strategy"?: "udp_socket_inference";
  readonly "target": string;
};

export type ServiceFactV1 = {
  readonly "display_name": string;
  readonly "installed": boolean;
  readonly "service_key": "endpoint_agent" | "endpoint_agent_updater" | "print_service";
  readonly "startup_type": "automatic" | "manual" | "disabled" | "unknown";
  readonly "state": "running" | "stopped" | "paused" | "failed" | "not_found" | "unknown";
};

export type ServiceListResultV1 = {
  readonly "collected_at": string;
  readonly "error_code"?: string | null;
  readonly "schema_version": "service_list_result_v1";
  readonly "services"?: ReadonlyArray<ServiceFactV1>;
  readonly "status": "succeeded" | "failed";
};

export type SoftwareFactV1 = {
  readonly "architecture"?: string | null;
  readonly "name": string;
  readonly "publisher"?: string | null;
  readonly "source": "windows_registry" | "alt_rpm";
  readonly "version"?: string | null;
};

export type SoftwareFindResultV1 = {
  readonly "collected_at": string;
  readonly "error_code"?: string | null;
  readonly "matches"?: ReadonlyArray<SoftwareFactV1>;
  readonly "present": boolean;
  readonly "schema_version": "software_find_result_v1";
  readonly "status": "succeeded" | "failed";
};

export type SoftwareListResultV1 = {
  readonly "collected_at": string;
  readonly "error_code"?: string | null;
  readonly "schema_version": "software_list_result_v1";
  readonly "software"?: ReadonlyArray<SoftwareFactV1>;
  readonly "status": "succeeded" | "failed";
};

export type SystemResourceSnapshotResultV1 = {
  readonly "collected_at": string;
  readonly "cpu_percent"?: number | null;
  readonly "error_code"?: string | null;
  readonly "memory_available_bytes"?: number | null;
  readonly "memory_total_bytes"?: number | null;
  readonly "schema_version": "system_resource_snapshot_result_v1";
  readonly "status": "succeeded" | "failed";
  readonly "system_drive_free_bytes"?: number | null;
  readonly "uptime_seconds"?: number | null;
};

export type TcpConnectResultV1 = {
  readonly "collected_at": string;
  readonly "error_code"?: string | null;
  readonly "latency_ms"?: number | null;
  readonly "port": number;
  readonly "reachable": boolean;
  readonly "resolved_ip"?: string | null;
  readonly "schema_version": "tcp_connect_result_v1";
  readonly "status": "succeeded" | "failed";
  readonly "target": string;
};

export type VolumeFactV1 = {
  readonly "filesystem_type": string;
  readonly "free_bytes": number;
  readonly "total_bytes": number;
  readonly "volume_key": string;
};

export type endpoint_contracts__read_only_primitives__ServiceStatusResultV1 = {
  readonly "collected_at": string;
  readonly "error_code"?: string | null;
  readonly "installed": boolean;
  readonly "schema_version": "service_status_result_v1";
  readonly "service_key": "endpoint_agent" | "endpoint_agent_updater";
  readonly "start_mode": "automatic" | "manual" | "disabled" | "unknown";
  readonly "state": "running" | "stopped" | "paused" | "failed" | "not_found" | "unknown";
  readonly "status": "succeeded" | "failed";
};

export type endpoint_contracts__service_printer_primitives__ServiceStatusResultV1 = {
  readonly "collected_at": string;
  readonly "error_code"?: string | null;
  readonly "schema_version": "service_status_v2_result_v1";
  readonly "service"?: ServiceFactV1 | null;
  readonly "status": "succeeded" | "failed";
};

export type ModuleOperationDetailV1 = {
  readonly "completed_at"?: string | null;
  readonly "created_at": string;
  readonly "deadline_at": string;
  readonly "device_id": string;
  readonly "expected_step_count": number;
  readonly "module_key": string;
  readonly "operation_id": string;
  readonly "schema_version": "endpoint_module_operation_v1";
  readonly "status": "queued" | "delivered" | "acknowledged" | "running" | "succeeded" | "failed" | "canceled" | "expired";
  readonly "steps": ReadonlyArray<ModuleOperationStepV1>;
  readonly "version": string;
};

export type EndpointPrimitiveResult = NonNullable<ModuleOperationStepV1['safe_result']>;
