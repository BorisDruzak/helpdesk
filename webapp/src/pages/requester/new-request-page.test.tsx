import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RequesterNewRequestPage } from "./new-request-page";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{`${location.pathname}${location.search}`}</span>;
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
    },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={["/app/requester/new"]}>
        <QueryClientProvider client={queryClient}>
          <LocationProbe />
          {children}
        </QueryClientProvider>
      </MemoryRouter>
    );
  }
  return render(<RequesterNewRequestPage />, { wrapper: Wrapper });
}

afterEach(() => {
  window.sessionStorage.clear();
  vi.unstubAllGlobals();
});

describe("RequesterNewRequestPage", () => {
  it("creates a requester ticket through the guided wizard and navigates to chat", async () => {
    const fetchMock = installNewRequestMock();
    renderPage();

    expect(await screen.findByLabelText("Что случилось или что нужно?")).toBeInTheDocument();
    expect(screen.queryByLabelText("Вариант услуги")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Что случилось или что нужно?"), {
      target: { value: "Ноутбук не включается" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));

    expect(await screen.findByText("Проверьте питание ноутбука")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Не помогло" }));
    fireEvent.click(screen.getByRole("button", { name: "Продолжить оформление" }));

    fireEvent.change(await screen.findByLabelText("Кратко"), {
      target: { value: "Ноутбук не включается" },
    });
    fireEvent.click(screen.getByRole("button", { name: "К проверке" }));

    fireEvent.click(await screen.findByRole("button", { name: "Проверить заявку" }));
    expect(await screen.findByText("Безопасный preview")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Создать обращение" }));

    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/app/requester/tickets/T-77"));
    const createCall = fetchMock.mock.calls.find(
      ([input, init]) => String(input) === "/api/web/requester/tickets" && init?.method === "POST",
    );
    expect(JSON.parse(String(createCall?.[1]?.body))).toMatchObject({
      device_id: "device-1",
      service_code: "workplace",
      offering_full_code: "workplace.laptop_broken",
      request_template_key: "breakage",
      form_key: "breakage",
      form_payload: {
        summary: "Ноутбук не включается",
        device_id: "device-1",
      },
      knowledge_attempts: expect.arrayContaining([
        expect.objectContaining({ item_id: "kb-1", result: "not_helpful", surface: "requester_portal" }),
      ]),
    });
  });

  it("blocks create when safe preview returns blockers", async () => {
    installNewRequestMock({ previewBlockers: ["Недостаточно данных для маршрута."] });
    renderPage();

    fireEvent.change(await screen.findByLabelText("Что случилось или что нужно?"), {
      target: { value: "Нужна помощь" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));
    fireEvent.click(await screen.findByRole("button", { name: "Продолжить оформление" }));
    fireEvent.change(await screen.findByLabelText("Кратко"), {
      target: { value: "Нужна помощь" },
    });
    fireEvent.click(screen.getByRole("button", { name: "К проверке" }));
    fireEvent.click(await screen.findByRole("button", { name: "Проверить заявку" }));

    expect(await screen.findByText("Недостаточно данных для маршрута.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Создать обращение" })).toBeDisabled();
  });

  it("keeps policy-allowed setup-help forms available for incomplete profiles", async () => {
    installNewRequestMock({
      profileComplete: false,
      setupHelpForm: true,
      withDevice: false,
      noDeviceCreate: false,
    });
    renderPage();

    expect(await screen.findByLabelText("Что случилось или что нужно?")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Сначала заполните профиль" })).not.toBeInTheDocument();
  });

  it("focuses the first missing dynamic field without exposing technical field names", async () => {
    installNewRequestMock();
    renderPage();

    fireEvent.change(await screen.findByLabelText("Что случилось или что нужно?"), {
      target: { value: "Нужна помощь с ноутбуком" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));
    fireEvent.click(await screen.findByRole("button", { name: "Продолжить оформление" }));

    const summary = await screen.findByLabelText("Кратко");
    fireEvent.click(screen.getByRole("button", { name: "К проверке" }));

    await waitFor(() => expect(summary).toHaveFocus());
    expect(screen.getByRole("alert")).toHaveTextContent("Заполните: Кратко");
    expect(screen.queryByLabelText(/summary|device_id/i)).not.toBeInTheDocument();
  });
});

function installNewRequestMock(
  options: {
    noDeviceCreate?: boolean;
    previewBlockers?: string[];
    profileComplete?: boolean;
    setupHelpForm?: boolean;
    withDevice?: boolean;
  } = {},
) {
  const profileComplete = options.profileComplete ?? true;
  const devices = options.withDevice === false ? [] : [{ device_id: "device-1", hostname: "desk-1", asset_name: "Desk 1" }];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === "/api/web/requester/bootstrap") {
      return jsonResponse({
        status: "success",
        data: {
          workspace: "requester",
          profile: { person_id: "person-1", display_name: "Requester One", full_name: "Requester One" },
          profile_completion: {
            complete: profileComplete,
            status: profileComplete ? "complete" : "incomplete",
            setup_path: "/app/requester/profile/setup",
            required_fields: [],
            missing_fields: profileComplete ? [] : ["department_id"],
            blocks: { ticket_create: !profileComplete, ticket_preview: !profileComplete },
          },
          profile_schema: { schema_key: "requester_profile", fields: [], custom_fields: [], required_fields: [] },
          requester_context: {
            profile: { full_name: "Requester One", department: "IT", location: "HQ" },
            form_prefill: { device_id: "device-1" },
          },
          devices,
          active_bindings: [],
          pending_registration_claims: [],
          open_ticket_count: 0,
          tickets_requiring_user_action_count: 0,
          pending_consent_count: 0,
          recent_tickets: [],
          feature_flags: { requester_ticket_create: true, requester_no_device_create: options.noDeviceCreate ?? true },
        },
      });
    }
    if (url === "/public_api/ticket_forms/current?pack_key=request_forms") {
      return jsonResponse({
        status: "ok",
        pack: {
          pack_key: "request_forms",
          version: "phase-g",
          forms: [
            {
              key: "breakage",
              title: "Проблема с ноутбуком",
              request_kind: "incident",
              availability_policy: options.setupHelpForm
                ? { available_without_completed_profile: true, available_without_agent_binding: true, contact_required: true }
                : undefined,
              fields: options.setupHelpForm
                ? [{ key: "summary", label: "Кратко", type: "text", required: true }]
                : [
                    { key: "summary", label: "Кратко", type: "text", required: true },
                    { key: "device_id", label: "Устройство", type: "device_picker", required: true },
                  ],
            },
          ],
        },
      });
    }
    if (url === "/api/service-catalog/current") {
      return jsonResponse({
        status: "ok",
        catalog_version: "phase-g",
        services: [
          {
            service_code: "workplace",
            title: "Рабочее место",
            offerings: [
              {
                offering_code: "laptop_broken",
                full_code: "workplace.laptop_broken",
                title: "Сломался ноутбук",
                request_template_key: "breakage",
              },
            ],
          },
        ],
      });
    }
    if (url === "/api/registry/options") {
      return jsonResponse({ status: "success", data: { departments: [], locations: [] } });
    }
    if (url === "/api/knowledge/suggest") {
      return jsonResponse({
        status: "ok",
        suggestions: [
          {
            item_id: "kb-1",
            version_id: "ver-1",
            title: "Проверьте питание ноутбука",
            summary: "Отключите зарядку на 10 секунд.",
          },
        ],
        rollout: { enabled: true, show_before_form: true },
      });
    }
    if (url === "/api/knowledge/feedback") {
      return jsonResponse({ status: "ok" });
    }
    if (url === "/api/web/requester/tickets/preview") {
      return jsonResponse({
        status: "success",
        data: {
          ok: !options.previewBlockers?.length,
          service: { title: "Рабочее место" },
          offering: { title: "Сломался ноутбук" },
          request_type_label: "Инцидент",
          blockers: options.previewBlockers ?? [],
          warnings: [],
          diagnostics: { text: "Диагностика будет выполнена по выбранному устройству." },
        },
      });
    }
    if (url === "/api/web/requester/tickets" && init?.method === "POST") {
      return jsonResponse({
        status: "success",
        data: {
          ticket_id: "T-77",
          ticket: { ticket_id: "T-77", title: "Ноутбук не включается", status: "new" },
        },
      });
    }
    throw new Error(`Unexpected fetch: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock as typeof fetch);
  return fetchMock;
}
