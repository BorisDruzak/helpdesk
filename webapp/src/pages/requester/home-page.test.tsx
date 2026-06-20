import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RequesterHomePage } from "./home-page";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

function renderHomePage() {
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
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }

  return render(<RequesterHomePage />, { wrapper: Wrapper });
}

function installDashboardMock({
  devices = [{ device_id: "device-1", hostname: "WORKSTATION-1", os: "Windows", agent_version: "3.1.71", online: true }],
  primaryDevice = devices[0] ?? null,
  primaryDeviceResolution = primaryDevice ? "available" : "missing",
  profileComplete = true,
  pendingConsents = 1,
}: {
  devices?: Array<Record<string, unknown>>;
  primaryDevice?: Record<string, unknown> | null;
  primaryDeviceResolution?: "available" | "missing" | "ambiguous";
  profileComplete?: boolean;
  pendingConsents?: number;
} = {}) {
  const rawTicketId = "550e8400-e29b-41d4-a716-446655440000";
  let pendingConsentCount = pendingConsents;
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url === "/api/web/requester/bootstrap") {
      return jsonResponse({
        status: "success",
        data: {
          workspace: "requester",
          profile: profileComplete ? { person_id: "person-1", display_name: "Алексей Иванов" } : null,
          profile_completion: {
            complete: profileComplete,
            status: profileComplete ? "complete" : "required",
            setup_path: "/app/requester/profile/setup",
            required_fields: profileComplete ? [] : [{ key: "full_name", label: "ФИО" }],
            missing_fields: profileComplete ? [] : [{ key: "full_name", label: "ФИО" }],
            blocks: {
              ticket_create: !profileComplete,
              ticket_preview: !profileComplete,
              device_binding_confirmation: false,
            },
          },
          profile_schema: { schema_key: "requester_profile", fields: [], custom_fields: [], required_fields: [] },
          requester_context: {
            profile: { display_name: "Алексей Иванов", department: "ИТ", location: "Екатеринбург" },
          },
          devices,
          primary_device: primaryDevice,
          primary_device_resolution: {
            status: primaryDeviceResolution,
            reason_code: primaryDeviceResolution,
            candidate_count: primaryDeviceResolution === "ambiguous" ? devices.length : primaryDevice ? 1 : 0,
          },
          active_bindings: [],
          pending_registration_claims: [],
          open_ticket_count: 1,
          tickets_requiring_user_action_count: pendingConsentCount ? 1 : 0,
          pending_consent_count: pendingConsentCount,
          recent_tickets: [],
          feature_flags: { requester_ticket_create: profileComplete, requester_no_device_create: false },
        },
      });
    }
    if (url === "/api/web/requester/tickets") {
      return jsonResponse({
        status: "success",
        data: {
          tickets: [
            {
              ticket_id: rawTicketId,
              title: "VPN",
              description: "Не подключается VPN.",
              status: "waiting_user",
              requester_status_label: "Ждет пользователя",
              created_at: "2026-06-19T08:00:00Z",
            },
          ],
        },
      });
    }
    if (url === "/api/web/requester/consents?status=pending") {
      return jsonResponse({
        status: "success",
        data: {
          consents: Array.from({ length: pendingConsentCount }, (_, index) => ({
            consent_id: `consent-${index}`,
            subject_type: "remote_assist",
            subject_id: `subject-${index}`,
            ticket_id: rawTicketId,
            title: "Просмотр экрана",
            status: "pending",
            requested_by_actor_id: "support-operator-1",
            requested_by_role: "support",
            risk_level: "remote_view",
            reason: "Проверить ошибку на экране.",
            requested_action_payload_redacted: {
              session_id: "remote-session-secret",
              mode: "view_only",
              duration_minutes: 5,
            },
          })),
        },
      });
    }
    if (url === "/api/web/requester/consents/consent-0/approve") {
      pendingConsentCount = 0;
      return jsonResponse({ status: "success", data: { consent: { consent_id: "consent-0", status: "approved" } } });
    }
    if (url === "/api/web/requester/consents/consent-0/deny") {
      pendingConsentCount = 0;
      return jsonResponse({ status: "success", data: { consent: { consent_id: "consent-0", status: "denied" } } });
    }
    throw new Error(`Unexpected dashboard fetch: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock as typeof fetch);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RequesterHomePage", () => {
  it("renders a task-focused dashboard without loading forms, chat or device-link flows", async () => {
    const fetchMock = installDashboardMock();

    renderHomePage();

    expect(await screen.findByRole("heading", { name: "Главная" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Создать обращение" })).toHaveAttribute("href", "/app/requester/new");
    expect(screen.getByRole("link", { name: "Проверить согласия" })).toHaveAttribute("href", "/app/requester/tickets");
    expect(screen.getByRole("heading", { name: "Ожидают вашего решения" })).toBeInTheDocument();
    expect(screen.getAllByText("Просмотр экрана").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Обращение 550e8400").length).toBeGreaterThan(0);
    expect(screen.queryByText("consent-0")).not.toBeInTheDocument();
    expect(screen.queryByText("remote-session-secret")).not.toBeInTheDocument();
    expect(screen.queryByText("550e8400-e29b-41d4-a716-446655440000")).not.toBeInTheDocument();
    expect(screen.getByText("WORKSTATION-1")).toBeInTheDocument();
    expect(screen.queryByText("Новое обращение")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Форма обращения заявителя")).not.toBeInTheDocument();
    expect(screen.queryByText("Код привязки")).not.toBeInTheDocument();
    expect(screen.queryByText("Публичный доступ")).not.toBeInTheDocument();
    expect(screen.queryByText("Мой профиль")).not.toBeInTheDocument();

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/web/requester/bootstrap", expect.anything());
      expect(fetchMock).toHaveBeenCalledWith("/api/web/requester/tickets", expect.anything());
      expect(fetchMock).toHaveBeenCalledWith("/api/web/requester/consents?status=pending", expect.anything());
    });
    const requestedUrls = fetchMock.mock.calls.map(([input]) => String(input));
    expect(requestedUrls).not.toContain("/public_api/ticket_forms/current?pack_key=request_forms");
    expect(requestedUrls).not.toContain("/api/service-catalog/current");
    expect(requestedUrls).not.toContain("/api/web/requester/profile");

    fireEvent.click(screen.getByRole("button", { name: "Разрешить запрос согласия" }));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/requester/consents/consent-0/approve",
        expect.objectContaining({ method: "POST" }),
      );
    });
    expect(await screen.findByText("Согласие подтверждено")).toBeInTheDocument();
  });

  it("promotes profile setup before request creation when the requester is not ready", async () => {
    installDashboardMock({ devices: [], profileComplete: false, pendingConsents: 0 });

    renderHomePage();

    expect(await screen.findByRole("heading", { name: "Главная" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Заполнить профиль" })).toHaveAttribute("href", "/app/requester/profile/setup");
    expect(screen.getAllByText("Профиль нужно заполнить").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Устройство не привязано").length).toBeGreaterThan(0);
    expect(screen.queryByText("Сохранить профиль")).not.toBeInTheDocument();
  });

  it("does not display the first device as primary when server resolution is ambiguous", async () => {
    installDashboardMock({
      devices: [
        { device_id: "device-1", hostname: "WORKSTATION-1", os: "Windows", online: true },
        { device_id: "device-2", hostname: "WORKSTATION-2", os: "Linux", online: false },
      ],
      primaryDevice: null,
      primaryDeviceResolution: "ambiguous",
      pendingConsents: 0,
    });

    renderHomePage();

    expect(await screen.findByRole("heading", { name: "Главная" })).toBeInTheDocument();
    expect(screen.getAllByText("Устройство не привязано").length).toBeGreaterThan(0);
    expect(screen.queryByText("WORKSTATION-1")).not.toBeInTheDocument();
    expect(screen.queryByText("WORKSTATION-2")).not.toBeInTheDocument();
  });
});
