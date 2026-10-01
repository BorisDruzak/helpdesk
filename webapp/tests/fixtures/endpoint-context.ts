import type { Page } from "playwright/test";

export const endpointDeviceId = "b101d111-1a11-4b11-8c11-123456789012";
export const endpointContext = {
  device: { id: endpointDeviceId, device_identifier: "WIN", display_name: "Windows fixture", online: true, retired_at: null, last_seen_at: null },
  profiles: [], snapshots: [],
};
export const registryContext = { status: "unmapped", bindings: [] };

export async function mockEndpointFleet(page: Page) {
  await page.route("**/api/web/admin/endpoint/devices?*", route => route.fulfill({
    json: { status: "success", data: { items: [{ ...endpointContext, inventory_summary: null, registry: registryContext }], next_cursor: null, technical_source: "endpoint", business_source: "registry" } },
  }));
  await page.route(`**/api/web/admin/endpoint/devices/${endpointDeviceId}`, route => route.fulfill({
    json: { status: "success", data: { ...endpointContext, registry: registryContext } },
  }));
}
