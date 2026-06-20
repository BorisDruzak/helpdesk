import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RequesterDeviceLinkPage, RequesterDevicesPage } from "./devices-page";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

function renderDevicesPage(initialEntry = "/app/requester/devices", Page = RequesterDevicesPage) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        refetchOnWindowFocus: false,
        retry: false,
      },
    },
  });

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[initialEntry]}>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }

  return render(<Page />, { wrapper: Wrapper });
}

function requesterBootstrap({
  devices = [
    {
      device_id: "device-1",
      hostname: "WORKSTATION-1",
      os: "Windows",
      agent_version: "3.1.72",
      relationship_type: "primary_user",
      binding_status: "active",
      online: true,
      last_seen_at: "2026-06-19T09:00:00Z",
      open_ticket_count: 2,
    },
  ],
  profileComplete = true,
  pendingClaims = [],
}: {
  devices?: Array<Record<string, unknown>>;
  profileComplete?: boolean;
  pendingClaims?: Array<Record<string, unknown>>;
} = {}) {
  return {
    workspace: "requester",
    profile: profileComplete ? { person_id: "person-1", display_name: "Иван Петров" } : null,
    profile_completion: {
      complete: profileComplete,
      status: profileComplete ? "complete" : "required",
      setup_path: "/app/requester/profile/setup",
      required_fields: profileComplete ? [] : [{ key: "full_name", label: "ФИО" }],
      missing_fields: profileComplete ? [] : [{ key: "full_name", label: "ФИО" }],
      blocks: { ticket_create: !profileComplete, ticket_preview: !profileComplete, device_binding_confirmation: false },
    },
    profile_schema: { schema_key: "requester_profile", fields: [], custom_fields: [], required_fields: [] },
    requester_context: { profile: {}, form_prefill: {}, summary: [] },
    devices,
    active_bindings: [],
    pending_registration_claims: pendingClaims,
    open_ticket_count: 0,
    tickets_requiring_user_action_count: 0,
    pending_consent_count: 0,
    recent_tickets: [],
    feature_flags: { requester_ticket_create: profileComplete, requester_no_device_create: true },
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RequesterDevicesPage", () => {
  it("renders device cards and details without diagnostic radio selection or raw technical terms", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/web/requester/bootstrap") {
        return jsonResponse({
          status: "success",
          data: requesterBootstrap({
            pendingClaims: [{ claim_id: "claim-1", device_id: "raw-device-id", status: "pending_admin_review" }],
          }),
        });
      }
      if (url === "/api/web/requester/devices/device-1") {
        return jsonResponse({
          status: "success",
          data: {
            device: {
              device_id: "device-1",
              hostname: "WORKSTATION-1",
              os: "Windows",
              agent_version: "3.1.72",
              relationship_type: "primary_user",
              binding_status: "active",
              online: true,
              open_ticket_count: 2,
            },
            recent_tickets: [{ ticket_id: "550e8400-e29b-41d4-a716-446655440000", ticket_code: "REQ-42", title: "VPN", status: "new" }],
          },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderDevicesPage();

    expect(await screen.findByRole("heading", { name: "Устройства" })).toBeInTheDocument();
    expect(screen.getByText("Основное устройство")).toBeInTheDocument();
    expect(screen.getByText("WORKSTATION-1")).toBeInTheDocument();
    expect(screen.getByText("Онлайн")).toBeInTheDocument();
    expect(screen.getByText(/Агент 3\.1\.72/)).toBeInTheDocument();
    expect(screen.getByText("Открытые обращения: 2")).toBeInTheDocument();
    expect(screen.getByText("Ожидает проверки администратора")).toBeInTheDocument();
    expect(screen.queryAllByRole("radio")).toHaveLength(0);
    expect(screen.queryByText(/binding|claim|session|pairing_id|raw-device-id|550e8400-e29b/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Подробнее о WORKSTATION-1" }));

    expect(await screen.findByText("Последние обращения")).toBeInTheDocument();
    expect(screen.getByText("REQ-42")).toBeInTheDocument();
  });

  it("keeps device linking available before profile completion and returns manual-review result copy", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/requester/bootstrap") {
        return jsonResponse({ status: "success", data: requesterBootstrap({ devices: [], profileComplete: false }) });
      }
      if (url === "/api/web/registry/browser-pairings/lookup") {
        expect(init?.method).toBe("POST");
        expect(JSON.parse(String(init?.body))).toEqual({ pairing_code: "ABCD-1234" });
        return jsonResponse({
          status: "success",
          data: { pairing_id: "pair-manual", purpose: "registration", next_url: "/app/device/register?pairing_id=pair-manual" },
        });
      }
      if (url === "/api/web/registry/browser-pairings/pair-manual") {
        return jsonResponse({
          status: "success",
          data: {
            pairing_id: "pair-manual",
            purpose: "registration",
            status: "pending",
            device: { device_id: "device-manual", hostname: "R4-PC", os: "Windows", agent_version: "3.1.64" },
          },
        });
      }
      if (url === "/api/web/registry/browser-pairings/pair-manual/registration/confirm") {
        expect(init?.method).toBe("POST");
        return jsonResponse({
          status: "success",
          data: {
            pairing_id: "pair-manual",
            purpose: "registration",
            status: "confirmed",
            device: { device_id: "device-manual", hostname: "R4-PC", os: "Windows", agent_version: "3.1.64" },
            registration: { status: "pending_admin_review", device_id: "device-manual" },
          },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderDevicesPage("/app/requester/devices/link", RequesterDeviceLinkPage);

    expect(await screen.findByRole("heading", { name: "Подключить устройство" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Мои устройства" })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Код подключения"), { target: { value: "abcd-1234" } });
    fireEvent.click(screen.getByRole("button", { name: "Проверить код" }));

    expect(await screen.findByText("R4-PC")).toBeInTheDocument();
    expect(screen.getByText(/Windows/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Подключить устройство" }));

    expect(await screen.findByText("Запрос отправлен на проверку")).toBeInTheDocument();
    expect(screen.queryByText(/pair-manual|device-manual|claim|session|binding/i)).not.toBeInTheDocument();
  });

  it("loads direct link preview without displaying pairing id and treats active result as connected", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/requester/bootstrap") {
        return jsonResponse({ status: "success", data: requesterBootstrap({ devices: [] }) });
      }
      if (url === "/api/web/registry/browser-pairings/pair-direct") {
        return jsonResponse({
          status: "success",
          data: {
            pairing_id: "pair-direct",
            purpose: "registration",
            status: "pending",
            device: { device_id: "device-direct", hostname: "DIRECT-PC", os: "Windows", agent_version: "3.1.64" },
          },
        });
      }
      if (url === "/api/web/registry/browser-pairings/pair-direct/registration/confirm") {
        expect(init?.method).toBe("POST");
        return jsonResponse({
          status: "success",
          data: {
            pairing_id: "pair-direct",
            purpose: "registration",
            status: "confirmed",
            device: { device_id: "device-direct", hostname: "DIRECT-PC", os: "Windows", agent_version: "3.1.64" },
            registration: { status: "active", device_id: "device-direct" },
          },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderDevicesPage("/app/requester/devices?pairing_id=pair-direct");

    expect(await screen.findByText("DIRECT-PC")).toBeInTheDocument();
    expect(screen.getByText("Проверьте устройство перед подключением.")).toBeInTheDocument();
    expect(screen.queryByText(/pair-direct|device-direct|pairing_id/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Подключить устройство" }));

    await waitFor(() => expect(screen.getByText("Устройство подключено")).toBeInTheDocument());
    expect(screen.queryByText(/pair-direct|device-direct|pairing_id/i)).not.toBeInTheDocument();
  });

  it("does not retry a failed direct pairing id load in a loop", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/web/requester/bootstrap") {
        return jsonResponse({ status: "success", data: requesterBootstrap({ devices: [] }) });
      }
      if (url === "/api/web/registry/browser-pairings/broken-direct") {
        return jsonResponse({ status: "error", error_code: "PAIRING_NOT_FOUND", error: "pairing not found" }, 404);
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderDevicesPage("/app/requester/devices/link?pairing_id=broken-direct", RequesterDeviceLinkPage);

    expect(await screen.findByRole("alert")).toHaveTextContent(/не найдено|недоступно/i);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(fetchMock.mock.calls.filter(([input]) => String(input) === "/api/web/registry/browser-pairings/broken-direct")).toHaveLength(1);
  });
});
