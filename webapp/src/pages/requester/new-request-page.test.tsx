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

function renderPage(initialEntry = "/app/requester/new") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
    },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={[initialEntry]}>
        <QueryClientProvider client={queryClient}>
          <LocationProbe />
          {children}
        </QueryClientProvider>
      </MemoryRouter>
    );
  }
  return render(<RequesterNewRequestPage />, { wrapper: Wrapper });
}

async function chooseCategory(label: string) {
  const select = await screen.findByLabelText("Категория обращения");
  const option = Array.from((select as HTMLSelectElement).options).find((item) => item.textContent?.includes(label));
  if (!option) {
    throw new Error(`Category option not found: ${label}`);
  }
  fireEvent.change(select, { target: { value: option.value } });
}

afterEach(() => {
  window.sessionStorage.clear();
  vi.unstubAllGlobals();
});

describe("RequesterNewRequestPage", () => {
  function draftEntries() {
    return Array.from({ length: window.sessionStorage.length }, (_, index) => window.sessionStorage.key(index))
      .filter((key): key is string => Boolean(key?.startsWith("pc_client.requester.new_request.draft.v1")))
      .map((key) => [key, window.sessionStorage.getItem(key)] as const);
  }

  async function fillLaptopForm(summary = "Ноутбук не включается") {
    await chooseCategory("Сломался ноутбук");
    fireEvent.change(await screen.findByLabelText("Кратко"), {
      target: { value: summary },
    });
  }

  it("starts with category and form fields instead of built-in description and pre-submit hints", async () => {
    const fetchMock = installNewRequestMock();
    renderPage();

    expect(await screen.findByLabelText("Категория обращения")).toBeInTheDocument();
    expect(screen.queryByLabelText("Что случилось или что нужно?")).not.toBeInTheDocument();
    expect(screen.queryByText("Возможно, поможет")).not.toBeInTheDocument();

    await fillLaptopForm();
    expect(screen.getByLabelText("Кратко")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([input]) => String(input) === "/api/knowledge/suggest")).toBe(false);
  });

  it("creates a requester ticket from the first-step form and navigates to chat", async () => {
    const fetchMock = installNewRequestMock();
    renderPage();

    await fillLaptopForm();
    fireEvent.click(screen.getByRole("button", { name: "К проверке" }));

    fireEvent.click(await screen.findByRole("button", { name: "Проверить обращение" }));
    expect(await screen.findByText("Безопасная проверка")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Создать обращение" }));

    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/app/requester/tickets/T-77"));
    expect(screen.getByTestId("location")).not.toHaveTextContent("550e8400-e29b-41d4-a716-446655440077");
    const createCall = fetchMock.mock.calls.find(
      ([input, init]) => String(input) === "/api/web/requester/tickets" && init?.method === "POST",
    );
    expect(JSON.parse(String(createCall?.[1]?.body))).toMatchObject({
      title: "Ноутбук не включается",
      description: "Ноутбук не включается",
      device_id: "device-1",
      service_code: "workplace",
      offering_full_code: "workplace.laptop_broken",
      request_template_key: "breakage",
      form_key: "breakage",
      form_payload: {
        summary: "Ноутбук не включается",
        device_id: "device-1",
      },
      knowledge_attempts: [],
    });
    expect(fetchMock.mock.calls.some(([input]) => String(input) === "/api/knowledge/suggest")).toBe(false);
    expect(draftEntries()).toHaveLength(0);
  });

  it("allows moving between form and review through the stepper", async () => {
    installNewRequestMock();
    renderPage();

    await fillLaptopForm("Ноутбук выключается после входа");
    fireEvent.click(screen.getByRole("button", { name: "К проверке" }));

    expect(await screen.findByRole("heading", { name: "Проверка" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Категория и форма/ }));
    expect(await screen.findByRole("heading", { name: "Категория и форма" })).toBeInTheDocument();
    expect(screen.getByLabelText("Кратко")).toHaveValue("Ноутбук выключается после входа");

    fireEvent.click(screen.getByRole("button", { name: /Проверка/ }));
    expect(await screen.findByText("Проверка перед отправкой")).toBeInTheDocument();
  });

  it("saves unfinished progress as a draft and restores it after remount", async () => {
    installNewRequestMock();
    const view = renderPage();

    await fillLaptopForm("Черновик: ноутбук шумит");

    await waitFor(() => {
      const entries = draftEntries();
      expect(entries).toHaveLength(1);
      expect(JSON.parse(String(entries[0]?.[1]))).toMatchObject({
        status: "draft",
        selectedCategoryKey: expect.stringContaining("breakage"),
        fieldValues: { summary: "Черновик: ноутбук шумит" },
      });
    });

    view.unmount();
    renderPage();

    expect(await screen.findByRole("heading", { name: "Категория и форма" })).toBeInTheDocument();
    expect(await screen.findByLabelText("Кратко")).toHaveValue("Черновик: ноутбук шумит");
  });

  it("requires an explicit category choice when no form is selected", async () => {
    installNewRequestMock({ withDistractorOffering: true });
    renderPage();

    const selector = await screen.findByLabelText("Категория обращения");
    expect(selector).toHaveValue("");
    expect(screen.getByRole("button", { name: "К проверке" })).toBeDisabled();
    expect(screen.queryByLabelText("Кратко")).not.toBeInTheDocument();
  });

  it("selects the requested printer category without exposing the laptop form first", async () => {
    installNewRequestMock({ withPrinterOffering: true });
    renderPage();

    await chooseCategory("Проблема с принтером");
    expect(await screen.findByRole("heading", { name: "Проблема с принтером" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Проблема с ноутбуком" })).not.toBeInTheDocument();
  });

  it("does not treat an on-behalf-only form as available for a self no-device request", async () => {
    installNewRequestMock({
      withDevice: false,
      withOnBehalfOnlyForm: true,
    });
    renderPage();

    await chooseCategory("Доступ для сотрудника");

    expect(await screen.findByText("Для обращения за себя нужно основное устройство.")).toBeInTheDocument();
    expect(screen.getByLabelText("Обращение за другого сотрудника")).toBeChecked();
    expect(screen.queryByLabelText("Кратко")).not.toBeInTheDocument();
  });

  it("does not submit an arbitrary device when primary device resolution is ambiguous", async () => {
    const fetchMock = installNewRequestMock({
      primaryDeviceResolution: "ambiguous",
      withNoDeviceManualForm: true,
    });
    renderPage();

    await chooseCategory("Ручная помощь без устройства");
    fireEvent.change(await screen.findByLabelText("Описание"), {
      target: { value: "Нужно разобраться без выбора устройства" },
    });
    fireEvent.click(screen.getByRole("button", { name: "К проверке" }));
    fireEvent.click(await screen.findByRole("button", { name: "Проверить обращение" }));
    fireEvent.click(await screen.findByRole("button", { name: "Создать обращение" }));

    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/app/requester/tickets/T-77"));
    const createCall = fetchMock.mock.calls.find(
      ([input, init]) => String(input) === "/api/web/requester/tickets" && init?.method === "POST",
    );
    const body = JSON.parse(String(createCall?.[1]?.body));
    expect(body).not.toHaveProperty("device_id");
    expect(body.form_payload).not.toHaveProperty("device_id");
    expect(body).toMatchObject({
      title: "Нужно разобраться без выбора устройства",
      description: "Нужно разобраться без выбора устройства",
    });
  });

  it("blocks create when safe preview returns blockers", async () => {
    installNewRequestMock({ previewBlockers: ["Недостаточно данных для маршрута."] });
    renderPage();

    await fillLaptopForm("Нужна помощь");
    fireEvent.click(screen.getByRole("button", { name: "К проверке" }));
    fireEvent.click(await screen.findByRole("button", { name: "Проверить обращение" }));

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

    expect(await screen.findByLabelText("Категория обращения")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Сначала заполните профиль" })).not.toBeInTheDocument();
  });

  it("uses per-form no-device availability instead of treating the global flag as a device context", async () => {
    installNewRequestMock({
      withDevice: false,
      noDeviceCreate: true,
      withNoDeviceManualForm: true,
    });
    renderPage();

    await chooseCategory("Ручная помощь без устройства");

    expect(await screen.findByLabelText("Описание")).toBeInTheDocument();
    expect(screen.queryByLabelText("Устройство")).not.toBeInTheDocument();
  });

  it("uses the owner-change intent to open the explicit owner verification form", async () => {
    installNewRequestMock({ withOwnerChangeForm: true });
    renderPage("/app/requester/new?intent=device_owner_change");

    expect(await screen.findByRole("heading", { name: "Проверка владельца устройства" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Что случилось или что нужно?")).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Что нужно проверить")).toHaveValue("Нужно проверить владельца устройства"));
    expect(screen.queryByLabelText("Устройство")).not.toBeInTheDocument();
  });

  it("focuses the first missing dynamic field only after the user tries to continue", async () => {
    installNewRequestMock();
    renderPage();

    await chooseCategory("Сломался ноутбук");
    const summary = await screen.findByLabelText("Кратко");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "К проверке" }));

    await waitFor(() => expect(summary).toHaveFocus());
    expect(screen.getByRole("alert")).toHaveTextContent("Заполните: Кратко");
    expect(screen.queryByLabelText(/summary|device_id/i)).not.toBeInTheDocument();
  });
});

function installNewRequestMock(
  options: {
    noDeviceCreate?: boolean;
    primaryDeviceResolution?: "available" | "missing" | "ambiguous";
    previewBlockers?: string[];
    profileComplete?: boolean;
    setupHelpForm?: boolean;
    withDistractorOffering?: boolean;
    withDevice?: boolean;
    withNoDeviceManualForm?: boolean;
    withOnBehalfOnlyForm?: boolean;
    withOwnerChangeForm?: boolean;
    withPrinterOffering?: boolean;
  } = {},
) {
  const profileComplete = options.profileComplete ?? true;
  const devices = options.withDevice === false ? [] : [{ device_id: "device-1", hostname: "desk-1", asset_name: "Desk 1" }];
  const primaryDeviceResolution = options.primaryDeviceResolution ?? (devices.length ? "available" : "missing");
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
          primary_device: primaryDeviceResolution === "available" ? devices[0] ?? null : null,
          primary_device_resolution: {
            status: primaryDeviceResolution,
            reason_code: primaryDeviceResolution,
            candidate_count: primaryDeviceResolution === "ambiguous" ? devices.length : primaryDeviceResolution === "available" ? 1 : 0,
          },
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
            ...(options.withNoDeviceManualForm
              ? [
                  {
                    key: "manual_help",
                    title: "Ручная помощь",
                    request_kind: "service_request",
                    availability_policy: { available_without_agent_binding: true, contact_required: true },
                    fields: [{ key: "description", label: "Описание", type: "textarea", required: true }],
                  },
                ]
              : []),
            ...(options.withPrinterOffering
              ? [
                  {
                    key: "printer_issue",
                    title: "Проблема с принтером",
                    request_kind: "incident",
                    fields: [
                      { key: "summary", label: "Кратко", type: "text", required: true },
                      { key: "device_id", label: "Устройство", type: "device_picker", required: true },
                    ],
                  },
                ]
              : []),
            ...(options.withOnBehalfOnlyForm
              ? [
                  {
                    key: "on_behalf_access",
                    title: "Доступ для сотрудника",
                    request_kind: "service_request",
                    on_behalf_policy: {
                      allowed: true,
                      label: "Обращение за другого сотрудника",
                      affected_person_required: true,
                      reason_required: true,
                    },
                    fields: [{ key: "summary", label: "Кратко", type: "text", required: true }],
                  },
                ]
              : []),
            ...(options.withOwnerChangeForm
              ? [
                  {
                    key: "device_owner_change",
                    title: "Проверка владельца устройства",
                    request_kind: "service_request",
                    availability_policy: { available_without_agent_binding: true, contact_required: true },
                    fields: [{ key: "owner_context", label: "Что нужно проверить", type: "textarea", required: true }],
                  },
                ]
              : []),
          ],
        },
      });
    }
    if (url === "/api/service-catalog/current") {
      const workplaceService = {
        service_code: "workplace",
        title: "Рабочее место",
        offerings: [
          {
            offering_code: "laptop_broken",
            full_code: "workplace.laptop_broken",
            title: "Сломался ноутбук",
            request_template_key: "breakage",
          },
          ...(options.withPrinterOffering
            ? [
                {
                  offering_code: "printer_issue",
                  full_code: "workplace.printer_issue",
                  title: "Проблема с принтером",
                  request_template_key: "printer_issue",
                },
              ]
            : []),
        ],
      };
      const manualService = {
        service_code: "manual",
        title: "Ручная помощь",
        offerings: [
          {
            offering_code: "manual_help",
            full_code: "manual.manual_help",
            title: "Ручная помощь без устройства",
            request_template_key: "manual_help",
          },
        ],
      };
      const ownerService = {
        service_code: "ownership",
        title: "Владельцы устройств",
        offerings: [
          {
            offering_code: "device_owner_change",
            full_code: "ownership.device_owner_change",
            title: "Проверка владельца устройства",
            request_template_key: "device_owner_change",
          },
        ],
      };
      const onBehalfService = {
        service_code: "access",
        title: "Доступы",
        offerings: [
          {
            offering_code: "on_behalf_access",
            full_code: "access.on_behalf_access",
            title: "Доступ для сотрудника",
            request_template_key: "on_behalf_access",
          },
        ],
      };
      return jsonResponse({
        status: "ok",
        catalog_version: "phase-g",
        services: options.withDistractorOffering
          ? [
              {
                service_code: "access",
                title: "Доступы",
                offerings: [
                  {
                    offering_code: "vpn",
                    full_code: "access.vpn",
                    title: "Доступ VPN",
                    description: "Подключение и доступ к сети в кабинете.",
                    request_template_key: "access_request",
                  },
                ],
              },
              workplaceService,
            ]
          : options.withNoDeviceManualForm
            ? [workplaceService, manualService]
          : options.withOwnerChangeForm
            ? [workplaceService, ownerService]
          : options.withOnBehalfOnlyForm
            ? [onBehalfService]
          : [workplaceService],
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
          ticket_id: "550e8400-e29b-41d4-a716-446655440077",
          ticket_code: "T-77",
          ticket: { ticket_id: "550e8400-e29b-41d4-a716-446655440077", ticket_code: "T-77", title: "Ноутбук не включается", status: "new" },
        },
      });
    }
    throw new Error(`Unexpected fetch: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock as typeof fetch);
  return fetchMock;
}
