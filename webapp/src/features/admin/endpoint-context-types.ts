// Safe projections mirrored from the immutable Helpdesk Context DTOs. No provider payloads.
export type BaselineHardwareV1 = {
  readonly manufacturer: string;
  readonly model: string;
  readonly cpu_model: string;
  readonly memory_bytes: number;
};

export type BaselineInterfaceV1 = {
  readonly stable_key: string;
  readonly name: string;
  readonly link_type: "ethernet" | "loopback" | "wireless" | "other";
};

export type BaselineSectionsV1 = {
  readonly system: BaselineSystemV1;
  readonly hardware: BaselineHardwareV1;
  readonly storage: ReadonlyArray<BaselineStorageV1>;
  readonly interfaces: ReadonlyArray<BaselineInterfaceV1>;
  readonly software: ReadonlyArray<BaselineSoftwareV1>;
};

export type BaselineSoftwareV1 = {
  readonly name: string;
  readonly version: string;
  readonly source: "installer" | "package" | "system";
};

export type BaselineStorageV1 = {
  readonly stable_key: string;
  readonly model: string;
  readonly size_bytes: number;
};

export type BaselineSystemV1 = {
  readonly platform: "linux" | "windows";
  readonly distribution: string;
  readonly architecture: "x86_64" | "aarch64";
};

export type DeviceContextDiffChangeV1 = {
  readonly code: "agent_changed" | "hardware_changed" | "network_changed" | "platform_changed" | "software_changed" | "storage_changed" | "AGENT_CHANGED" | "HARDWARE_CHANGED" | "HOSTNAME_CHANGED" | "NETWORK_CHANGED" | "NETWORK_ADAPTER_CHANGED" | "OS_CHANGED" | "PLATFORM_CHANGED" | "RAM_CHANGED" | "SOFTWARE_CHANGED" | "STORAGE_CHANGED";
  readonly summary: string;
};

export type DeviceContextDiffV1 = {
  readonly schema_version: "device_context_diff_v1";
  readonly profile: "baseline_v1" | "inventory_v1";
  readonly from_hash: string;
  readonly to_hash: string;
  readonly changes: ReadonlyArray<DeviceContextDiffChangeV1>;
};

export type EndpointCollectionDetails = {
  readonly collection: EndpointContextCollection;
  readonly snapshot: EndpointContextSnapshot | null;
};

export type EndpointContextCollection = {
  readonly id: string;
  readonly device_id: string;
  readonly profile: "baseline_v1" | "health_v1" | "network_v1" | "inventory_v1" | "session_v1";
  readonly status: "requested" | "queued" | "delivered" | "collecting" | "result_received" | "validated" | "completed" | "failed" | "expired";
  readonly requested_at: string;
  readonly result_received_at: string | null;
  readonly completed_at: string | null;
  readonly failure_code: string | null;
};

export type EndpointContextDevice = {
  readonly id: string;
  readonly device_identifier: string;
  readonly display_name: string;
  readonly retired_at: string | null;
  readonly last_seen_at: string | null;
  readonly online: boolean;
};

export type EndpointContextHistory = {
  readonly snapshots: ReadonlyArray<EndpointContextSnapshot>;
};

export type EndpointDeviceContext = {
  readonly device: EndpointContextDevice;
  readonly profiles: ReadonlyArray<EndpointProfileAvailability>;
  readonly snapshots: ReadonlyArray<EndpointContextSnapshot>;
};

export type EndpointDeviceFleet = {
  readonly items: ReadonlyArray<EndpointFleetItem>;
  readonly next_cursor: string | null;
};

export type EndpointFleetItem = {
  readonly device: EndpointContextDevice;
  readonly profiles: ReadonlyArray<EndpointProfileAvailability>;
  readonly inventory_summary: EndpointInventorySummary | null;
};

export type EndpointInventorySummary = {
  readonly hostname?: string | null;
  readonly platform?: "linux" | "windows" | null;
  readonly os_name?: string | null;
  readonly os_version?: string | null;
  readonly architecture?: "x86_64" | "aarch64" | null;
  readonly manufacturer?: string | null;
  readonly model?: string | null;
  readonly serial_number?: string | null;
  readonly cpu_model?: string | null;
  readonly memory_bytes?: number | null;
};

export type EndpointProfileAvailability = {
  readonly profile: "baseline_v1" | "health_v1" | "network_v1" | "inventory_v1" | "session_v1";
  readonly status: "requested" | "queued" | "delivered" | "collecting" | "result_received" | "validated" | "completed" | "failed" | "expired";
  readonly last_collected_at: string | null;
};

export type HealthResourcesV1 = {
  readonly uptime_seconds: number;
  readonly load_1m: number;
  readonly free_bytes: number;
};

export type HealthSectionsV1 = {
  readonly resources: HealthResourcesV1;
  readonly services: ReadonlyArray<HealthServiceV1>;
};

export type HealthServiceV1 = {
  readonly name: string;
  readonly status: "active" | "inactive" | "failed" | "unknown";
};

export type InventoryHardwareV1 = {
  readonly manufacturer?: string | null;
  readonly model?: string | null;
  readonly serial_number?: string | null;
  readonly product_uuid?: string | null;
  readonly cpu_model?: string | null;
  readonly bios_vendor?: string | null;
  readonly bios_version?: string | null;
  readonly baseboard_manufacturer?: string | null;
  readonly baseboard_model?: string | null;
  readonly baseboard_serial?: string | null;
};

export type InventoryInterfaceV1 = {
  readonly name: string;
  readonly stable_key: string;
  readonly mac?: string | null;
  readonly ipv4: ReadonlyArray<string>;
  readonly ipv6: ReadonlyArray<string>;
  readonly link_type: "ethernet" | "loopback" | "wireless" | "other";
  readonly operational_state: "up" | "down" | "unknown";
};

export type InventoryMemoryModuleV1 = {
  readonly slot?: string | null;
  readonly manufacturer?: string | null;
  readonly part_number?: string | null;
  readonly serial?: string | null;
  readonly capacity_bytes?: number | null;
  readonly speed_mt_s?: number | null;
  readonly memory_type?: "DDR" | "DDR2" | "DDR3" | "DDR4" | "DDR5" | "UNKNOWN" | null;
};

export type InventoryMemoryV1 = {
  readonly total_bytes?: number | null;
  readonly memory_type?: "DDR" | "DDR2" | "DDR3" | "DDR4" | "DDR5" | "UNKNOWN" | null;
  readonly module_count: number;
  readonly modules: ReadonlyArray<InventoryMemoryModuleV1>;
};

export type InventoryPhysicalStorageV1 = {
  readonly stable_key: string;
  readonly model?: string | null;
  readonly serial?: string | null;
  readonly size_bytes?: number | null;
  readonly media_type: "HDD" | "SSD" | "UNKNOWN";
  readonly bus_type: "SATA" | "NVME" | "USB" | "SAS" | "OTHER" | "UNKNOWN";
};

export type InventorySectionsV1 = {
  readonly system: InventorySystemV1;
  readonly hardware: InventoryHardwareV1;
  readonly memory: InventoryMemoryV1;
  readonly storage: InventoryStorageV1;
  readonly interfaces: ReadonlyArray<InventoryInterfaceV1>;
};

export type InventoryStorageV1 = {
  readonly physical_devices: ReadonlyArray<InventoryPhysicalStorageV1>;
};

export type InventorySystemV1 = {
  readonly hostname?: string | null;
  readonly platform?: "linux" | "windows" | null;
  readonly os_name?: string | null;
  readonly os_version?: string | null;
  readonly os_build?: string | null;
  readonly architecture?: "x86_64" | "aarch64" | null;
};

export type NetworkInterfaceV1 = {
  readonly name: string;
  readonly addresses: ReadonlyArray<string>;
};

export type NetworkRouteV1 = {
  readonly interface: string;
  readonly gateway?: string | null;
};

export type NetworkSectionsV1 = {
  readonly default_route: NetworkRouteV1;
  readonly interfaces: ReadonlyArray<NetworkInterfaceV1>;
};

export type RegistryBindingOverlay = {
  readonly binding_id: string;
  readonly relationship_type: string;
  readonly person_id: string;
  readonly display_name: string;
  readonly department_id: string | null;
  readonly department: string | null;
  readonly location_id: string | null;
  readonly location: string | null;
};

export type RegistryDeviceOverlay = {
  readonly status: "mapped" | "unmapped" | "unavailable";
  readonly local_device_id?: string | null;
  readonly asset_id?: string | null;
  readonly asset_name?: string | null;
  readonly inventory_number?: string | null;
  readonly asset_status?: string | null;
  readonly department_id?: string | null;
  readonly department?: string | null;
  readonly location_id?: string | null;
  readonly location?: string | null;
  readonly bindings: ReadonlyArray<RegistryBindingOverlay>;
  readonly bindings_truncated?: boolean;
};

export type SessionSectionsV1 = {
  readonly current_user_login?: string | null;
  readonly interactive_session_present: boolean;
};

export type SafeContextProfile = "baseline_v1" | "inventory_v1" | "health_v1" | "network_v1" | "session_v1";
export type EndpointContextSnapshot = { readonly id: string; readonly collected_at: string; readonly semantic_hash: string | null; readonly warnings: ReadonlyArray<string> } & (
  | { readonly profile: "baseline_v1"; readonly sections: BaselineSectionsV1 }
  | { readonly profile: "inventory_v1"; readonly sections: InventorySectionsV1 }
  | { readonly profile: "health_v1"; readonly sections: HealthSectionsV1 }
  | { readonly profile: "network_v1"; readonly sections: NetworkSectionsV1 }
  | { readonly profile: "session_v1"; readonly sections: SessionSectionsV1 }
);
export type AdminEndpointFleetItem = EndpointFleetItem & { readonly registry: RegistryDeviceOverlay };
export type AdminEndpointFleet = { readonly items: ReadonlyArray<AdminEndpointFleetItem>; readonly next_cursor: string | null; readonly technical_source: "endpoint"; readonly business_source: "registry" };
export type AdminEndpointContext = EndpointDeviceContext & { readonly registry: RegistryDeviceOverlay; readonly technical_source: "endpoint"; readonly business_source: "registry" };
export type ContextRefreshResult = { readonly request_id: string; readonly status: "requested" | "partial" | "failed"; readonly results: ReadonlyArray<{ readonly profile: SafeContextProfile; readonly collection: EndpointContextCollection | null; readonly error_code: string | null }> };
