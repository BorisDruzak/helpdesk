import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RequesterWorkspacePage } from ".";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

afterEach(() => {
  window.sessionStorage.clear();
  window.history.pushState({}, "", "/");
  vi.unstubAllGlobals();
});

function installSetupAssistanceFormsMock({
  devices = [],
  knowledgeSuggestions = [],
  profileComplete,
  withServiceCatalog = false,
}: {
  devices?: Array<{ device_id: string; hostname: string; os?: string; agent_version?: string }>;
  knowledgeSuggestions?: Array<Record<string, unknown>>;
  profileComplete: boolean;
  withServiceCatalog?: boolean;
}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === "/api/web/requester/bootstrap") {
      return jsonResponse({
        status: "success",
        data: {
          workspace: "requester",
          profile: profileComplete ? { person_id: "person-setup", display_name: "Setup User" } : null,
          profile_completion: {
            complete: profileComplete,
            status: profileComplete ? "complete" : "required",
            setup_path: "/app/requester/profile/setup",
            required_fields: [],
            missing_fields: profileComplete ? [] : [{ key: "full_name", label: "ФИО" }],
            blocks: {
              ticket_create: !profileComplete,
              ticket_preview: !profileComplete,
              device_binding_confirmation: false,
            },
          },
          profile_schema: {
            schema_key: "requester_profile",
            fields: [],
            custom_fields: [],
            required_fields: [],
          },
          devices,
          active_bindings: devices.map((device) => ({
            binding_id: `binding-${device.device_id}`,
            device,
            relationship_type: "primary_user",
            status: "active",
          })),
          pending_registration_claims: [],
          open_ticket_count: 0,
          tickets_requiring_user_action_count: 0,
          pending_consent_count: 0,
          recent_tickets: [],
          feature_flags: { requester_no_device_create: false, requester_ticket_create: profileComplete },
        },
      });
    }
    if (url === "/api/web/requester/tickets") {
      return jsonResponse({ status: "success", data: { tickets: [] } });
    }
    if (url === "/api/web/requester/consents?status=pending") {
      return jsonResponse({ status: "success", data: { consents: [] } });
    }
    if (url === "/public_api/ticket_forms/current?pack_key=request_forms") {
      return jsonResponse({
        status: "ok",
        pack: {
          pack_key: "request_forms",
          version: "setup-visibility",
          forms: [
            {
              key: "profile_completion_help",
              title: "Помощь с заполнением профиля",
              request_kind: "profile_completion_help",
              availability_policy: {
                available_without_completed_profile: true,
                available_without_agent_binding: true,
                requires_manual_triage: true,
                contact_required: true,
                allowed_for_anonymous: false,
              },
              fields: [{ key: "contact_phone", label: "Телефон для связи", type: "phone", required: true }],
            },
            {
              key: "agent_binding_help",
              title: "Помощь с привязкой агента",
              request_kind: "agent_binding_help",
              availability_policy: {
                available_without_completed_profile: true,
                available_without_agent_binding: true,
                requires_manual_triage: true,
                contact_required: true,
                allowed_for_anonymous: false,
              },
              fields: [{ key: "contact_phone", label: "Телефон для связи", type: "phone", required: true }],
            },
            {
              key: "normal_access",
              title: "Обычный доступ",
              request_kind: "request",
              availability_policy: {
                available_without_completed_profile: false,
                available_without_agent_binding: false,
                requires_manual_triage: false,
                contact_required: false,
                allowed_for_anonymous: false,
              },
              fields: [{ key: "summary", label: "Кратко", type: "text", required: false }],
            },
          ],
        },
      });
    }
    if (url === "/api/service-catalog/current") {
      if (withServiceCatalog) {
        return jsonResponse({
          status: "ok",
          catalog_version: "test",
          services: [
            {
              service_code: "workplace",
              title: "Workplace",
              offerings: [
                {
                  offering_code: "breakage",
                  full_code: "workplace.breakage",
                  title: "Laptop breakage",
                  request_template_key: "normal_access",
                },
              ],
            },
          ],
        });
      }
      return jsonResponse({ status: "ok", catalog_version: "test", services: [] });
    }
    if (url === "/api/registry/options") {
      return jsonResponse({ status: "success", data: { departments: [], locations: [] } });
    }
    if (url === "/api/knowledge/suggest" && init?.method === "POST") {
      return jsonResponse({
        status: "ok",
        suggestions: knowledgeSuggestions,
        rollout: { enabled: true, show_before_form: true, show_quality_badge: true, show_review_freshness: true },
      });
    }
    throw new Error(`Unexpected fetch: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock as typeof fetch);
  return fetchMock;
}

describe("RequesterWorkspacePage", () => {
  it("prefills requester ticket draft from Knowledge Ask context and submits knowledge attempts", async () => {
    window.history.pushState({}, "", "/app/requester/new");
    window.sessionStorage.setItem(
      "pc_client.knowledge_ask.ticket_context",
      JSON.stringify({
        source: "knowledge_ask",
        query: "VPN access error",
        created_at: new Date().toISOString(),
        answer_status: "ai_disabled",
        effective_mode: "keyword_only",
        ai_used: false,
        audit_id: "ask-audit-prefill",
        primary_item: {
          item_id: "ki-ask-prefill",
          version_id: "kv-ask-prefill",
          slug: "vpn-access",
          title: "VPN access article",
          chunk_id: "chunk-ask-prefill",
        },
        retrieval_results: [
          {
            item_id: "ki-ask-prefill",
            version_id: "kv-ask-prefill",
            slug: "vpn-access",
            title: "VPN access article",
            chunk_id: "chunk-ask-prefill",
            score: 110,
          },
        ],
      }),
    );
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/requester/bootstrap") {
        return jsonResponse({
          status: "success",
          data: {
            workspace: "requester",
            profile: { person_id: "person-1", display_name: "Requester One" },
            devices: [],
            active_bindings: [],
            pending_registration_claims: [],
            open_ticket_count: 0,
            tickets_requiring_user_action_count: 0,
            pending_consent_count: 0,
            recent_tickets: [],
            feature_flags: { requester_no_device_create: true },
          },
        });
      }
      if (url === "/api/web/requester/tickets" && init?.method !== "POST") {
        return jsonResponse({ status: "success", data: { tickets: [] } });
      }
      if (url === "/api/web/requester/tickets" && init?.method === "POST") {
        return jsonResponse({ status: "success", data: { ticket_id: "T-ASK", ticket: { ticket_id: "T-ASK", title: "Запрос из базы знаний: VPN access error" } } });
      }
      if (url === "/api/web/requester/consents?status=pending") {
        return jsonResponse({ status: "success", data: { consents: [] } });
      }
      if (url === "/public_api/ticket_forms/current?pack_key=request_forms") {
        return jsonResponse({ status: "ok", pack: { pack_key: "request_forms", version: "test", forms: [] } });
      }
      if (url === "/api/service-catalog/current") {
        return jsonResponse({ status: "ok", catalog_version: "test", services: [] });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    render(<RequesterWorkspacePage />);

    expect(await screen.findByDisplayValue("Запрос из базы знаний: VPN access error")).toBeInTheDocument();
    expect(screen.getByDisplayValue(/Вопрос в базе знаний: VPN access error/)).toBeInTheDocument();
    expect(screen.getByDisplayValue(/Статус ответа: AI отключен/)).toBeInTheDocument();
    expect(screen.getByDisplayValue(/Режим поиска: Поиск по ключевым словам/)).toBeInTheDocument();
    expect(screen.queryByDisplayValue(/Knowledge Ask/)).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue(/ask-audit-prefill/)).not.toBeInTheDocument();
    expect(window.sessionStorage.getItem("pc_client.knowledge_ask.ticket_context")).toBeNull();

    fireEvent.click(screen.getByLabelText("Создать обращение в кабинете пользователя"));

    await waitFor(() => expect(fetchMock.mock.calls.some((call) => String(call[0]) === "/api/web/requester/tickets" && call[1]?.method === "POST")).toBe(true));
    const createCall = fetchMock.mock.calls.find((call) => String(call[0]) === "/api/web/requester/tickets" && call[1]?.method === "POST");
    expect(JSON.parse(createCall?.[1]?.body as string)).toMatchObject({
      title: "Запрос из базы знаний: VPN access error",
      knowledge_attempts: [
        {
          item_id: "ki-ask-prefill",
          version_id: "kv-ask-prefill",
          result: "ticket_created_after_view",
          surface: "requester_portal",
        },
      ],
    });
  });

  it("shows pending requester consent and approves it", async () => {
    let approved = false;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/requester/bootstrap") {
        return jsonResponse({
          status: "success",
          data: {
            workspace: "requester",
            profile: { person_id: "person-1", display_name: "Requester One" },
            devices: [],
            active_bindings: [],
            pending_registration_claims: [],
            open_ticket_count: 0,
            tickets_requiring_user_action_count: 0,
            pending_consent_count: approved ? 0 : 1,
            recent_tickets: [],
          },
        });
      }
      if (url === "/api/web/requester/tickets" && init?.method !== "POST") {
        return jsonResponse({ status: "success", data: { tickets: [] } });
      }
      if (url === "/api/web/requester/consents?status=pending") {
        return jsonResponse({
          status: "success",
          data: {
            consents: approved
              ? []
              : [
                  {
                    consent_id: "consent-1",
                    subject_type: "remote_assist",
                    subject_id: "remote-1",
                    ticket_id: "T-1",
                    device_id: "device-1",
                    risk_level: "remote_view",
                    status: "pending",
                    title: "Просмотр экрана",
                    description: "Специалист просит доступ",
                  },
                ],
          },
        });
      }
      if (url === "/api/web/requester/consents/consent-1/approve") {
        approved = true;
        return jsonResponse({
          status: "success",
          data: { consent: { consent_id: "consent-1", subject_type: "remote_assist", subject_id: "remote-1", status: "approved" } },
        });
      }
      if (url === "/public_api/ticket_forms/current?pack_key=request_forms") {
        return jsonResponse({ status: "ok", pack: { pack_key: "request_forms", version: "test", forms: [] } });
      }
      if (url === "/api/service-catalog/current") {
        return jsonResponse({ status: "ok", catalog_version: "test", services: [] });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    render(<RequesterWorkspacePage />);

    await screen.findByText("Ожидают вашего подтверждения");
    await screen.findByText("Просмотр экрана");
    fireEvent.click(screen.getByLabelText("Подтвердить согласие consent-1"));

    await screen.findByText("Согласие подтверждено");
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/requester/consents/consent-1/approve",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("opens requester profile detail from the requester workspace", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/requester/bootstrap") {
        return jsonResponse({
          status: "success",
          data: {
            workspace: "requester",
            profile: {
              person_id: "person-1",
              display_name: "Requester One",
              full_name: "Requester One",
              email: "requester@example.test",
              phone: "1001",
              department_id: "dept-1",
              location_id: "loc-1",
            },
            requester_context: {
              profile: { full_name: "Requester One", department: "IT", location: "HQ / 101", phone: "1001" },
              form_prefill: { department_id: "dept-1", location_id: "loc-1", phone: "1001" },
            },
            devices: [
              {
                device_id: "device-1",
                hostname: "desk-1",
                os: "Windows",
                agent_version: "3.1.61",
                asset_id: "asset-1",
                asset_name: "Desk 1",
              },
            ],
            active_bindings: [],
            pending_registration_claims: [],
            open_ticket_count: 1,
            tickets_requiring_user_action_count: 0,
            pending_consent_count: 0,
            recent_tickets: [],
          },
        });
      }
      if (url === "/api/web/requester/tickets" && init?.method !== "POST") {
        return jsonResponse({ status: "success", data: { tickets: [] } });
      }
      if (url === "/public_api/ticket_forms/current?pack_key=request_forms") {
        return jsonResponse({ status: "ok", pack: { pack_key: "request_forms", version: "test", forms: [] } });
      }
      if (url === "/api/service-catalog/current") {
        return jsonResponse({ status: "ok", catalog_version: "test", services: [] });
      }
      if (url === "/api/web/requester/profile") {
        return jsonResponse({
          status: "success",
          data: {
            profile: {
              person_id: "person-1",
              display_name: "Requester One",
              full_name: "Requester One Full",
              email: "requester@example.test",
              phone: "+7 000 111-22-33",
              status: "active",
            },
            identities: [
              { provider: "ui_login", identifier: "requester@example.test", verified: true, source: "web" },
              { provider: "employee_id", identifier: "EMP-42", verified: true, source: "hr" },
            ],
            devices: [{ device_id: "device-1", hostname: "desk-1", relationship_type: "primary_user", binding_status: "active" }],
            active_bindings: [{ binding_id: "binding-1", device_id: "device-1", relationship_type: "primary_user", status: "active" }],
            pending_registration_claims: [],
            profile_policy: { editable: false, editable_fields: [], change_request_required: true },
          },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    render(<RequesterWorkspacePage />);

    await screen.findByText("Привязано устройств: 1");
    const profileButton = await screen.findByLabelText("Открыть профиль заявителя");
    fireEvent.click(profileButton);

    await screen.findByText("Профиль заявителя");
    await screen.findByText("Requester One Full");
    expect((await screen.findAllByText("requester@example.test")).length).toBeGreaterThan(1);
    await screen.findByText("+7 000 111-22-33");
    await screen.findByText("employee_id");
    await screen.findByText("EMP-42");
    expect((await screen.findAllByText("desk-1")).length).toBeGreaterThan(1);
    await screen.findByText("Данные профиля доступны только для чтения.");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/requester/profile",
      expect.objectContaining({ credentials: "same-origin", cache: "no-store" }),
    );
  });

  it("opens requester device detail from the owned devices list", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/requester/bootstrap") {
        return jsonResponse({
          status: "success",
          data: {
            workspace: "requester",
            profile: { person_id: "person-1", display_name: "Requester One" },
            devices: [{ device_id: "device-1", hostname: "desk-1", os: "Windows", agent_version: "3.1.61" }],
            active_bindings: [],
            pending_registration_claims: [],
            open_ticket_count: 2,
            tickets_requiring_user_action_count: 0,
            pending_consent_count: 0,
            recent_tickets: [],
          },
        });
      }
      if (url === "/api/web/requester/tickets" && init?.method !== "POST") {
        return jsonResponse({ status: "success", data: { tickets: [] } });
      }
      if (url === "/public_api/ticket_forms/current?pack_key=request_forms") {
        return jsonResponse({ status: "ok", pack: { pack_key: "request_forms", version: "test", forms: [] } });
      }
      if (url === "/api/service-catalog/current") {
        return jsonResponse({ status: "ok", catalog_version: "test", services: [] });
      }
      if (url === "/api/web/requester/devices/device-1") {
        return jsonResponse({
          status: "success",
          data: {
            device: {
              device_id: "device-1",
              hostname: "desk-1.corp",
              os: "Windows 11",
              agent_version: "3.1.61",
              relationship_type: "primary_user",
              binding_status: "active",
              online: false,
              asset_name: "Desk one asset",
              open_ticket_count: 2,
              available_actions: { create_ticket: true },
            },
            recent_tickets: [{ ticket_id: "T-1", title: "Device ticket", status: "new" }],
          },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    render(<RequesterWorkspacePage />);

    await waitFor(() => expect(screen.getAllByText("desk-1").length).toBeGreaterThan(0));
    fireEvent.click(screen.getByLabelText("Открыть сведения об устройстве device-1"));

    await screen.findByText("Сведения об устройстве");
    await screen.findByText("desk-1.corp");
    await screen.findByText(/Основной пользователь/);
    await screen.findByText((_, element) => element?.textContent === "Не в сети · Открытые обращения: 2");
    expect(screen.queryByText(/agent/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/unknown/i)).not.toBeInTheDocument();
    await screen.findByText("Device ticket");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/requester/devices/device-1",
      expect.objectContaining({ credentials: "same-origin", cache: "no-store" }),
    );
  });

  it("claims a public ticket and opens it in the requester workspace", async () => {
    let claimed = false;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/requester/bootstrap") {
        return jsonResponse({
          status: "success",
          data: {
            workspace: "requester",
            profile: { person_id: "person-1", display_name: "Requester One" },
            devices: [],
            active_bindings: [],
            pending_registration_claims: [],
            open_ticket_count: 0,
            tickets_requiring_user_action_count: 0,
            pending_consent_count: 0,
            recent_tickets: [],
          },
        });
      }
      if (url === "/api/web/requester/tickets" && init?.method !== "POST") {
        return jsonResponse({
          status: "success",
          data: {
            tickets: claimed ? [{ ticket_id: "T-91", title: "Claimed public ticket", status: "new" }] : [],
          },
        });
      }
      if (url === "/public_api/ticket_forms/current?pack_key=request_forms") {
        return jsonResponse({ status: "ok", pack: { pack_key: "request_forms", version: "test", forms: [] } });
      }
      if (url === "/api/service-catalog/current") {
        return jsonResponse({ status: "ok", catalog_version: "test", services: [] });
      }
      if (url === "/api/web/requester/tickets/claim-public") {
        claimed = true;
        return jsonResponse({
          status: "success",
          data: {
            ticket_id: "T-91",
            claimed: true,
            requester_person_id: "person-1",
            ticket: { ticket_id: "T-91", title: "Claimed public ticket", status: "new" },
          },
        });
      }
      if (url === "/api/web/requester/tickets/T-91") {
        return jsonResponse({
          status: "success",
          data: {
            ticket: {
              ticket_id: "T-91",
              title: "Claimed public ticket",
              description: "Created from public portal",
              status: "new",
            },
            messages: [],
          },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    render(<RequesterWorkspacePage />);

    await screen.findByText("Привязать обращение");
    fireEvent.change(screen.getByLabelText("Номер обращения для привязки"), { target: { value: "T-91" } });
    fireEvent.change(screen.getByLabelText("Код доступа для привязки обращения"), { target: { value: "ABCD12" } });
    fireEvent.click(screen.getByLabelText("Привязать публичное обращение"));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/requester/tickets/claim-public",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ ticket_id: "T-91", code: "ABCD12" }),
        }),
      );
    });
    await screen.findByText("Обращение привязано");
    expect(await screen.findAllByText("Claimed public ticket")).toHaveLength(2);
    await screen.findByText("Created from public portal");
  });

  it("shows identity guidance when public claim requires a linked requester profile", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/requester/bootstrap") {
        return jsonResponse({
          status: "success",
          data: {
            workspace: "requester",
            profile: { person_id: null, display_name: "Requester One" },
            devices: [],
            active_bindings: [],
            pending_registration_claims: [],
            open_ticket_count: 0,
            tickets_requiring_user_action_count: 0,
            pending_consent_count: 0,
            recent_tickets: [],
          },
        });
      }
      if (url === "/api/web/requester/tickets" && init?.method !== "POST") {
        return jsonResponse({ status: "success", data: { tickets: [] } });
      }
      if (url === "/public_api/ticket_forms/current?pack_key=request_forms") {
        return jsonResponse({ status: "ok", pack: { pack_key: "request_forms", version: "test", forms: [] } });
      }
      if (url === "/api/service-catalog/current") {
        return jsonResponse({ status: "ok", catalog_version: "test", services: [] });
      }
      if (url === "/api/web/requester/tickets/claim-public") {
        return jsonResponse(
          {
            status: "error",
            message: "requester identity is required to claim a public ticket",
            error_code: "REQUESTER_IDENTITY_REQUIRED",
          },
          403,
        );
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    render(<RequesterWorkspacePage />);

    await screen.findByText("Привязать обращение");
    fireEvent.change(screen.getByLabelText("Номер обращения для привязки"), { target: { value: "T-91" } });
    fireEvent.change(screen.getByLabelText("Код доступа для привязки обращения"), { target: { value: "ABCD12" } });
    fireEvent.click(screen.getByLabelText("Привязать публичное обращение"));

    await screen.findByText(
      "Для привязки обращения нужен связанный профиль пользователя. Обратитесь к администратору для привязки учетной записи.",
    );
  });

  it("opens owned ticket detail and sends an authenticated requester message", async () => {
    let detailReloadedAfterMessage = false;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/requester/bootstrap") {
        return jsonResponse({
          status: "success",
          data: {
            workspace: "requester",
            profile: { person_id: "person-1", display_name: "Requester One" },
            devices: [],
            active_bindings: [],
            pending_registration_claims: [],
            open_ticket_count: 1,
            tickets_requiring_user_action_count: 1,
            pending_consent_count: 0,
            recent_tickets: [],
          },
        });
      }
      if (url === "/api/web/requester/tickets" && init?.method !== "POST") {
        return jsonResponse({
          status: "success",
          data: {
            tickets: [{ ticket_id: "T-42", title: "Owned ticket", status: "waiting_on_user", requester_status_label: "Waiting" }],
          },
        });
      }
      if (url === "/api/web/requester/tickets/T-42") {
        if (detailReloadedAfterMessage) {
          return jsonResponse({
            status: "success",
            data: {
              ticket: {
                ticket_id: "T-42",
                title: "Owned ticket detail",
                description: "Support asked for more information",
                status: "waiting_on_user",
                requester_status_label: "Waiting",
              },
              messages: [
                {
                  message_id: "m-42",
                  from_role: "user",
                  text: "Here is the requested context",
                  attachments: [
                    {
                      artifact_id: "artifact-42",
                      name: "requester-log.txt",
                      url: "/api/artifacts/artifact-42/download",
                      type: "file",
                    },
                  ],
                },
              ],
            },
          });
        }
        return jsonResponse({
          status: "success",
          data: {
            ticket: {
              ticket_id: "T-42",
              title: "Owned ticket detail",
              description: "Support asked for more information",
              status: "waiting_on_user",
              requester_status_label: "Waiting",
            },
            messages: [],
          },
        });
      }
      if (url === "/api/upload") {
        return jsonResponse({
          status: "success",
          artifact_id: "artifact-42",
          filename: "requester-log.txt",
          url: "/api/artifacts/artifact-42/download",
          size: 18,
          mime_type: "text/plain",
          kind: "file",
        });
      }
      if (url === "/api/web/requester/tickets/T-42/message") {
        detailReloadedAfterMessage = true;
        return jsonResponse({ status: "success", data: { message_id: "m-42", event_id: 12 } });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    render(<RequesterWorkspacePage />);

    await screen.findByText("Owned ticket");
    fireEvent.click(screen.getByText("Owned ticket"));

    await screen.findByText("Owned ticket detail");
    fireEvent.change(screen.getByLabelText("Прикрепить файл к ответу"), {
      target: { files: [new File(["requester evidence"], "requester-log.txt", { type: "text/plain" })] },
    });
    await screen.findByText("requester-log.txt");
    fireEvent.change(screen.getByLabelText("Ответ заявителя"), {
      target: { value: "Here is the requested context" },
    });
    fireEvent.click(screen.getByLabelText("Отправить ответ заявителя"));

    await waitFor(() => {
      const uploadCall = fetchMock.mock.calls.find(([input]) => String(input) === "/api/upload");
      expect(uploadCall?.[1]).toEqual(expect.objectContaining({ method: "POST", body: expect.any(FormData) }));
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/requester/tickets/T-42/message",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ text: "Here is the requested context", attachment_refs: ["artifact-42"] }),
        }),
      );
    });
    await screen.findByRole("link", { name: "requester-log.txt" });
  });

  it("closes, rates, and reopens an owned resolved ticket", async () => {
    let ticketStatus = "resolved";
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/requester/bootstrap") {
        return jsonResponse({
          status: "success",
          data: {
            workspace: "requester",
            profile: { person_id: "person-1", display_name: "Requester One" },
            devices: [],
            active_bindings: [],
            pending_registration_claims: [],
            open_ticket_count: ticketStatus === "in_progress" ? 1 : 0,
            tickets_requiring_user_action_count: ticketStatus === "resolved" ? 1 : 0,
            pending_consent_count: 0,
            recent_tickets: [],
          },
        });
      }
      if (url === "/api/web/requester/tickets" && init?.method !== "POST") {
        return jsonResponse({
          status: "success",
          data: {
            tickets: [{ ticket_id: "T-77", title: "Resolved ticket", status: ticketStatus, requester_status_label: ticketStatus }],
          },
        });
      }
      if (url === "/api/web/requester/tickets/T-77") {
        return jsonResponse({
          status: "success",
          data: {
            ticket: {
              ticket_id: "T-77",
              title: "Resolved ticket detail",
              description: "Please confirm whether the issue is fixed",
              status: ticketStatus,
              requester_status_label: ticketStatus,
            },
            messages: [],
          },
        });
      }
      if (url === "/api/web/requester/tickets/T-77/close") {
        ticketStatus = "closed";
        return jsonResponse({ status: "success", data: { ticket: { ticket_id: "T-77", status: "closed" } } });
      }
      if (url === "/api/web/requester/tickets/T-77/feedback") {
        return jsonResponse({ status: "success", data: { ok: true, feedback_id: "fb-77", reopen_available: true } });
      }
      if (url === "/api/web/requester/tickets/T-77/reopen") {
        ticketStatus = "in_progress";
        return jsonResponse({
          status: "success",
          data: { ok: true, ticket_id: "T-77", ticket_status: "in_progress", reopen_id: "ro-77" },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    render(<RequesterWorkspacePage />);

    await screen.findByText("Resolved ticket");
    fireEvent.click(screen.getByText("Resolved ticket"));
    await screen.findByText("Resolved ticket detail");

    fireEvent.click(screen.getByLabelText("Закрыть обращение заявителя"));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/requester/tickets/T-77/close",
        expect.objectContaining({ method: "POST" }),
      );
    });

    fireEvent.change(screen.getByLabelText("Оценка обращения"), { target: { value: "2" } });
    fireEvent.click(screen.getByLabelText("Проблема решена"));
    fireEvent.click(screen.getByLabelText("Отправить оценку обращения"));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/requester/tickets/T-77/feedback",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"rating":2'),
        }),
      );
    });

    fireEvent.click(screen.getByLabelText("Вернуть обращение в работу"));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/requester/tickets/T-77/reopen",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("creates a requester ticket through catalog form preview", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/requester/bootstrap") {
        return jsonResponse({
          status: "success",
          data: {
            workspace: "requester",
            profile: {
              person_id: "person-1",
              display_name: "Requester One",
              full_name: "Requester One",
              email: "requester@example.test",
              phone: "1001",
              department_id: "dept-1",
              location_id: "loc-1",
            },
            requester_context: {
              profile: { full_name: "Requester One", department: "IT", location: "HQ / 101", phone: "1001" },
              form_prefill: { department_id: "dept-1", location_id: "loc-1", phone: "1001" },
            },
            devices: [
              {
                device_id: "device-1",
                hostname: "desk-1",
                os: "Windows",
                agent_version: "3.1.61",
                asset_id: "asset-1",
                asset_name: "Desk 1",
              },
            ],
            active_bindings: [],
            pending_registration_claims: [],
            open_ticket_count: 0,
            tickets_requiring_user_action_count: 0,
            pending_consent_count: 0,
            recent_tickets: [],
          },
        });
      }
      if (url === "/api/web/requester/tickets" && init?.method !== "POST") {
        return jsonResponse({ status: "success", data: { tickets: [] } });
      }
      if (url === "/public_api/ticket_forms/current?pack_key=request_forms") {
        return jsonResponse({
          status: "ok",
          pack: {
            pack_key: "request_forms",
            version: "2026.06",
            forms: [
              {
                key: "breakage",
                title: "Поломка",
                request_kind: "incident",
                fields: [
                  { key: "department_id", label: "Department", type: "department_picker", required: true },
                  { key: "device_id", label: "Device", type: "device_picker", required: true },
                  { key: "summary", label: "Кратко", type: "text", required: true },
                ],
              },
            ],
          },
        });
      }
      if (url === "/api/registry/options") {
        return jsonResponse({
          status: "success",
          data: {
            departments: [{ value: "dept-1", label: "IT" }],
            locations: [{ value: "loc-1", label: "HQ / 101" }],
          },
        });
      }
      if (url === "/api/service-catalog/current") {
        return jsonResponse({
          status: "ok",
          catalog_version: "runtime",
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
      if (url === "/api/knowledge/suggest") {
        return jsonResponse({
          status: "ok",
          suggestions: [
            {
              item_id: "kb-requester-1",
              version_id: "kb-version-1",
              slug: "laptop-power-check",
              type: "article",
              title: "Проверьте питание ноутбука",
              summary: "Перед созданием обращения проверьте блок питания и индикатор зарядки.",
              snippet: "Отключите зарядку на 10 секунд и подключите снова.",
              quality_label: "Проверено",
              freshness_label: "Свежее",
            },
          ],
          rollout: { enabled: true, show_before_form: true, show_quality_badge: true, show_review_freshness: true },
        });
      }
      if (url === "/api/knowledge/feedback") {
        return jsonResponse({ status: "ok" });
      }
      if (url === "/api/web/requester/tickets/preview") {
        return jsonResponse({
          status: "success",
          data: {
            ok: true,
            service: { code: "workplace", title: "Workplace" },
            offering: { code: "laptop_broken", full_code: "workplace.laptop_broken", title: "Laptop broken" },
            request_type_label: "Incident",
            approval: { required: false, text: "Approval is not required" },
            diagnostics: { required: false, consent_required: false, text: "Diagnostics are not required" },
            warnings: [],
            blockers: [],
            would_create_ticket: false,
            requester_context: {
              summary: [
                { label: "profile", value: "Requester One" },
                { label: "department", value: "IT" },
                { label: "device", value: "desk-1" },
              ],
            },
          },
        });
      }
      if (url === "/api/service-catalog/preview") {
        return jsonResponse({
          status: "ok",
          ok: true,
          service: { code: "workplace", title: "Рабочее место" },
          offering: { code: "laptop_broken", full_code: "workplace.laptop_broken", title: "Сломался ноутбук" },
          request_type_label: "Инцидент",
          approval: { required: false, text: "Согласование не требуется" },
          diagnostics: { required: false, consent_required: false, text: "Диагностика не требуется" },
          warnings: [],
          blockers: [],
          would_create_ticket: false,
        });
      }
      if (url === "/api/web/requester/tickets" && init?.method === "POST") {
        return jsonResponse({
          status: "success",
          data: {
            ticket_id: "T-88",
            ticket: { ticket_id: "T-88", title: "Проверка рабочего места", status: "new" },
          },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    render(<RequesterWorkspacePage />);

    await screen.findByLabelText("Вариант услуги");
    const contextBlock = await screen.findByLabelText("Контекст формы обращения");
    expect(contextBlock).toHaveTextContent("IT");
    await waitFor(() => {
      const suggestCall = fetchMock.mock.calls.find(([input]) => String(input) === "/api/knowledge/suggest");
      expect(suggestCall).toBeTruthy();
      const suggestBody = JSON.parse(String((suggestCall?.[1] as RequestInit).body));
      expect(suggestBody).toMatchObject({
        requester_context: {
          form_prefill: {
            department_id: "dept-1",
            location_id: "loc-1",
            phone: "1001",
          },
        },
        device_metadata: {
          device_id: "device-1",
          hostname: "desk-1",
          asset_id: "asset-1",
          asset_name: "Desk 1",
        },
      });
    });
    await screen.findByText("Проверьте питание ноутбука");
    fireEvent.click(screen.getByLabelText("Открыть рекомендацию из базы знаний"));
    await screen.findByText("Отключите зарядку на 10 секунд и подключите снова.");
    fireEvent.click(screen.getByLabelText("Отметить рекомендацию бесполезной"));
    fireEvent.change(screen.getByLabelText("Поле формы обращения summary"), {
      target: { value: "Ноутбук не включается" },
    });
    fireEvent.change(screen.getByLabelText("Описание"), {
      target: { value: "Ноутбук не загружается после включения" },
    });
    fireEvent.change(screen.getByLabelText("Поле формы обращения summary"), {
      target: { value: "Ноутбук не включается" },
    });
    fireEvent.click(screen.getByLabelText("Проверить обращение перед отправкой"));

    await screen.findByText("Безопасный preview");
    await screen.findByText(/Контекст:/);
    fireEvent.click(screen.getByLabelText("Создать обращение в кабинете пользователя"));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/requester/tickets",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"service_code":"workplace"'),
        }),
      );
    });
    const createCall = fetchMock.mock.calls.find(
      ([input, init]) => String(input) === "/api/web/requester/tickets" && (init as RequestInit | undefined)?.method === "POST",
    );
    const body = JSON.parse(String((createCall?.[1] as RequestInit).body));
    expect(body).toMatchObject({
      device_id: "device-1",
      service_code: "workplace",
      offering_code: "laptop_broken",
      offering_full_code: "workplace.laptop_broken",
      request_template_key: "breakage",
      form_key: "breakage",
      form_pack_key: "request_forms",
      form_pack_version: "2026.06",
      form_payload: {
        department_id: "dept-1",
        device_id: "device-1",
        summary: "Ноутбук не включается",
      },
      ticket_type: "incident",
      knowledge_attempts: expect.arrayContaining([
        expect.objectContaining({
          item_id: "kb-requester-1",
          version_id: "kb-version-1",
          result: "viewed",
          surface: "requester_portal",
        }),
        expect.objectContaining({
          item_id: "kb-requester-1",
          version_id: "kb-version-1",
          result: "not_helpful",
          surface: "requester_portal",
        }),
      ]),
    });
  });

  it("selects an affected employee only when on-behalf policy is enabled", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/requester/bootstrap") {
        return jsonResponse({
          status: "success",
          data: {
            workspace: "requester",
            profile: {
              person_id: "person-requester",
              display_name: "Requester One",
              full_name: "Requester One",
              email: "requester@example.test",
              phone: "1001",
              department_id: "dept-1",
              location_id: "loc-1",
            },
            requester_context: {
              profile: { full_name: "Requester One", department: "IT", location: "HQ / 101", phone: "1001" },
              form_prefill: { phone: "1001" },
            },
            devices: [
              {
                device_id: "device-1",
                hostname: "desk-1",
                os: "Windows",
                agent_version: "3.1.61",
              },
            ],
            active_bindings: [],
            pending_registration_claims: [],
            open_ticket_count: 0,
            tickets_requiring_user_action_count: 0,
            pending_consent_count: 0,
            recent_tickets: [],
          },
        });
      }
      if (url === "/api/web/requester/tickets" && init?.method !== "POST") {
        return jsonResponse({ status: "success", data: { tickets: [] } });
      }
      if (url === "/api/web/requester/consents?status=pending") {
        return jsonResponse({ status: "success", data: { consents: [] } });
      }
      if (url === "/public_api/ticket_forms/current?pack_key=request_forms") {
        return jsonResponse({
          status: "ok",
          pack: {
            pack_key: "request_forms",
            version: "2026.06",
            forms: [
              {
                key: "ordinary",
                title: "Обычная форма",
                request_kind: "incident",
                on_behalf_policy: { allowed: false },
                fields: [],
              },
              {
                key: "breakage",
                title: "Проблема у сотрудника",
                request_kind: "incident",
                on_behalf_policy: {
                  allowed: true,
                  label: "Проблема у другого сотрудника",
                  affected_person_required: true,
                  reason_required: true,
                  allowed_scope: "same_department_or_privileged",
                  no_primary_agent_behavior: "allow_ticket_no_diagnostics",
                },
                fields: [{ key: "summary", label: "Кратко", type: "text", required: true }],
              },
            ],
          },
        });
      }
      if (url === "/api/service-catalog/current") {
        return jsonResponse({
          status: "ok",
          catalog_version: "runtime",
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
      if (url === "/api/knowledge/suggest") {
        return jsonResponse({ status: "ok", suggestions: [], rollout: { enabled: true, show_before_form: true } });
      }
      if (url.startsWith("/api/web/requester/on-behalf/people?")) {
        const parsed = new URL(url, "http://localhost");
        expect(parsed.searchParams.get("form_key")).toBe("breakage");
        expect(parsed.searchParams.get("q")).toBe("Affected");
        return jsonResponse({
          status: "success",
          data: {
            people: [
              {
                person_id: "person-affected",
                display_name: "Affected One",
                department: { name: "IT" },
                location: { display_name: "HQ / 201" },
                primary_agent: { status: "missing" },
              },
            ],
          },
        });
      }
      if (url === "/api/web/requester/tickets/preview") {
        return jsonResponse({
          status: "success",
          data: {
            ok: true,
            service: { code: "workplace", title: "Workplace" },
            offering: { code: "laptop_broken", full_code: "workplace.laptop_broken", title: "Laptop broken" },
            approval: { required: false, text: "Approval is not required" },
            diagnostics: { required: false, consent_required: false, text: "Diagnostics use affected employee primary device" },
            warnings: [],
            blockers: [],
            would_create_ticket: false,
          },
        });
      }
      if (url === "/api/web/requester/tickets" && init?.method === "POST") {
        return jsonResponse({
          status: "success",
          data: {
            ticket_id: "T-ON-BEHALF",
            ticket: { ticket_id: "T-ON-BEHALF", title: "Проблема у сотрудника", status: "new" },
          },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    render(<RequesterWorkspacePage />);

    await screen.findByLabelText("Форма обращения заявителя");
    expect(screen.queryByLabelText("Проблема у другого сотрудника")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Форма обращения заявителя"), { target: { value: "breakage" } });
    fireEvent.click(await screen.findByLabelText("Проблема у другого сотрудника"));
    fireEvent.change(screen.getByLabelText("Поиск сотрудника, у которого проблема"), { target: { value: "Affected" } });
    fireEvent.click(screen.getByRole("button", { name: "Найти сотрудника" }));
    await screen.findByText("Affected One");
    fireEvent.change(screen.getByLabelText("Сотрудник, у которого проблема"), { target: { value: "person-affected" } });
    fireEvent.change(screen.getByLabelText("Причина обращения за другого сотрудника"), { target: { value: "phone call" } });
    expect(screen.getByText("Диагностика будет выполняться по основному устройству выбранного сотрудника.")).toBeInTheDocument();
    expect(screen.getByText("У выбранного сотрудника нет привязанного устройства. Диагностика агента недоступна.")).toBeInTheDocument();
    expect(screen.queryByText("person-affected")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Поле формы обращения summary"), { target: { value: "Не включается" } });
    fireEvent.change(screen.getByLabelText("Описание"), { target: { value: "Ноутбук не загружается" } });
    fireEvent.click(screen.getByLabelText("Проверить обращение перед отправкой"));

    await screen.findByText("Безопасный preview");
    const previewCall = fetchMock.mock.calls.find(([input]) => String(input) === "/api/web/requester/tickets/preview");
    expect(JSON.parse(String((previewCall?.[1] as RequestInit).body))).toMatchObject({
      ticket_context: { affected_person_id: "person-affected", on_behalf_reason: "phone call" },
    });

    fireEvent.click(screen.getByLabelText("Создать обращение в кабинете пользователя"));
    await screen.findByText("Создано обращение T-ON-BEHALF");
    const createCall = fetchMock.mock.calls.find(
      ([input, init]) => String(input) === "/api/web/requester/tickets" && (init as RequestInit | undefined)?.method === "POST",
    );
    expect(JSON.parse(String((createCall?.[1] as RequestInit).body))).toMatchObject({
      ticket_context: { affected_person_id: "person-affected", on_behalf_reason: "phone call" },
    });
    expect(fetchMock.mock.calls.some(([input]) => String(input) === "/api/registry/options")).toBe(false);
  });

  it("creates a requester ticket without a registered device", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/requester/bootstrap") {
        return jsonResponse({
          status: "success",
          data: {
            workspace: "requester",
            profile: { person_id: "person-no-device", display_name: "Requester No Device" },
            devices: [],
            active_bindings: [],
            pending_registration_claims: [],
            open_ticket_count: 0,
            tickets_requiring_user_action_count: 0,
            pending_consent_count: 0,
            recent_tickets: [],
            feature_flags: { requester_no_device_create: true },
            policies: { device_selection_required: false },
          },
        });
      }
      if (url === "/api/web/requester/tickets" && init?.method !== "POST") {
        return jsonResponse({
          status: "success",
          data: { tickets: [] },
        });
      }
      if (url === "/public_api/ticket_forms/current?pack_key=request_forms") {
        return jsonResponse({ status: "ok", pack: { pack_key: "request_forms", version: "test", forms: [] } });
      }
      if (url === "/api/service-catalog/current") {
        return jsonResponse({ status: "ok", catalog_version: "test", services: [] });
      }
      if (url === "/api/web/requester/tickets" && init?.method === "POST") {
        return jsonResponse({
          status: "success",
          data: {
            ticket_id: "T-99",
            ticket: { ticket_id: "T-99", title: "Проверка рабочего места", status: "new" },
          },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    render(<RequesterWorkspacePage />);

    await screen.findByText("Зарегистрированных устройств пока нет.");
    fireEvent.change(screen.getByLabelText("Описание"), {
      target: { value: "Нужна помощь без зарегистрированного устройства" },
    });
    fireEvent.click(screen.getByLabelText("Создать обращение в кабинете пользователя"));

    await screen.findByText("Создано обращение T-99");
    const createCall = fetchMock.mock.calls.find(
      ([input, init]) => String(input) === "/api/web/requester/tickets" && (init as RequestInit | undefined)?.method === "POST",
    );
    expect(createCall).toBeTruthy();
    const body = JSON.parse(String((createCall?.[1] as RequestInit).body));
    expect(body).toMatchObject({
      title: "Проверка рабочего места",
      description: "Нужна помощь без зарегистрированного устройства",
      user_display_name: "Requester No Device",
    });
    expect(body).not.toHaveProperty("device_id");
  });

  it("shows pending device-link requests from legacy registration claims", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/requester/bootstrap") {
        return jsonResponse({
          status: "success",
          data: {
            workspace: "requester",
            profile: { person_id: "person-pending", display_name: "Requester Pending" },
            profile_completion: {
              complete: true,
              status: "complete",
              setup_path: "/app/requester/profile/setup",
              required_fields: [],
              missing_fields: [],
              blocks: {
                ticket_create: false,
                ticket_preview: false,
                device_binding_confirmation: false,
              },
            },
            devices: [],
            active_bindings: [],
            pending_registration_claims: [
              {
                claim_id: "claim-legacy-1",
                device_id: "legacy-device-1",
                status: "pending_admin_review",
                submitted_at: "2026-06-15T10:30:00+05:00",
              },
            ],
            open_ticket_count: 0,
            tickets_requiring_user_action_count: 0,
            pending_consent_count: 0,
            recent_tickets: [],
            feature_flags: { requester_no_device_create: true },
            policies: { device_selection_required: false },
          },
        });
      }
      if (url === "/api/web/requester/tickets" && init?.method !== "POST") {
        return jsonResponse({ status: "success", data: { tickets: [] } });
      }
      if (url === "/api/web/requester/consents?status=pending") {
        return jsonResponse({ status: "success", data: { consents: [] } });
      }
      if (url === "/public_api/ticket_forms/current?pack_key=request_forms") {
        return jsonResponse({ status: "ok", pack: { pack_key: "request_forms", version: "test", forms: [] } });
      }
      if (url === "/api/service-catalog/current") {
        return jsonResponse({ status: "ok", catalog_version: "test", services: [] });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    render(<RequesterWorkspacePage />);

    expect(await screen.findByText("Заявки на привязку")).toBeInTheDocument();
    expect(screen.getByText("Устройство legacy-device-1")).toBeInTheDocument();
    expect(screen.getByText("Ожидает проверки администратора")).toBeInTheDocument();
  });

  it("allows no-device ticket creation when profile completion is not blocking rollout", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/requester/bootstrap") {
        return jsonResponse({
          status: "success",
          data: {
            workspace: "requester",
            profile: null,
            profile_completion: {
              complete: false,
              status: "optional",
              setup_path: "/app/requester/profile/setup",
              required_fields: [{ key: "full_name", label: "ФИО" }],
              missing_fields: [{ key: "full_name", label: "ФИО" }],
              blocks: {
                ticket_create: false,
                ticket_preview: false,
                device_binding_confirmation: false,
              },
            },
            devices: [],
            active_bindings: [],
            pending_registration_claims: [],
            open_ticket_count: 0,
            tickets_requiring_user_action_count: 0,
            pending_consent_count: 0,
            recent_tickets: [],
            feature_flags: { requester_no_device_create: true, requester_ticket_create: true },
            policies: { device_selection_required: false },
          },
        });
      }
      if (url === "/api/web/requester/tickets" && init?.method !== "POST") {
        return jsonResponse({ status: "success", data: { tickets: [] } });
      }
      if (url === "/api/web/requester/consents?status=pending") {
        return jsonResponse({ status: "success", data: { consents: [] } });
      }
      if (url === "/public_api/ticket_forms/current?pack_key=request_forms") {
        return jsonResponse({ status: "ok", pack: { pack_key: "request_forms", version: "test", forms: [] } });
      }
      if (url === "/api/service-catalog/current") {
        return jsonResponse({ status: "ok", catalog_version: "test", services: [] });
      }
      if (url === "/api/web/requester/tickets" && init?.method === "POST") {
        return jsonResponse({
          status: "success",
          data: {
            ticket_id: "T-override",
            ticket: { ticket_id: "T-override", title: "Проверка рабочего места", status: "new" },
          },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    render(<RequesterWorkspacePage />);

    await screen.findByText("Зарегистрированных устройств пока нет.");
    expect(screen.queryByText("Заполните профиль")).not.toBeInTheDocument();
    const createButton = screen.getByLabelText("Создать обращение в кабинете пользователя");
    fireEvent.change(screen.getByLabelText("Описание"), {
      target: { value: "Нужно создать обращение без обязательного профиля" },
    });
    expect(createButton).not.toBeDisabled();
    fireEvent.click(createButton);

    await screen.findByText("Создано обращение T-override");
  });

  it("blocks normal ticket creation while requester profile is incomplete", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/requester/bootstrap") {
        return jsonResponse({
          status: "success",
          data: {
            workspace: "requester",
            profile: null,
            profile_completion: {
              complete: false,
              status: "required",
              setup_path: "/app/requester/profile/setup",
              required_fields: [],
              missing_fields: [
                { key: "full_name", label: "ФИО" },
                { key: "department_id", label: "Подразделение" },
                { key: "location_id", label: "Локация" },
                { key: "phone", label: "Телефон или внутренний номер" },
              ],
            },
            profile_schema: {
              schema_key: "requester_profile",
              fields: [
                {
                  key: "position",
                  label: "Должность",
                  type: "text",
                  required: false,
                  visible: false,
                  custom: false,
                  system: false,
                },
              ],
              custom_fields: [],
              required_fields: [],
            },
            devices: [],
            active_bindings: [],
            pending_registration_claims: [],
            open_ticket_count: 0,
            tickets_requiring_user_action_count: 0,
            pending_consent_count: 0,
            recent_tickets: [],
            feature_flags: { requester_no_device_create: true, requester_ticket_create: false },
          },
        });
      }
      if (url === "/api/web/requester/tickets" && init?.method !== "POST") {
        return jsonResponse({ status: "success", data: { tickets: [] } });
      }
      if (url === "/api/web/requester/consents?status=pending") {
        return jsonResponse({ status: "success", data: { consents: [] } });
      }
      if (url === "/public_api/ticket_forms/current?pack_key=request_forms") {
        return jsonResponse({ status: "ok", pack: { pack_key: "request_forms", version: "test", forms: [] } });
      }
      if (url === "/api/service-catalog/current") {
        return jsonResponse({ status: "ok", catalog_version: "test", services: [] });
      }
      if (url === "/api/registry/options") {
        return jsonResponse({
          status: "success",
          data: {
            departments: [{ value: "dept-1", label: "ИТ" }],
            locations: [{ value: "loc-1", label: "Офис 7 / 701" }],
          },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    render(<RequesterWorkspacePage />);

    expect(await screen.findByText("Заполните профиль")).toBeInTheDocument();
    expect(screen.getByLabelText("Телефон или внутренний номер")).toBeInTheDocument();
    expect(screen.queryByLabelText("Должность")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Создать обращение в кабинете пользователя")).toBeDisabled();
    expect(
      fetchMock.mock.calls.some(([input, init]) => String(input) === "/api/web/requester/tickets" && init?.method === "POST"),
    ).toBe(false);
  });

  it("allows device linking while requester profile is incomplete", async () => {
    const incompleteBootstrap = {
      workspace: "requester",
      profile: null,
      profile_completion: {
        complete: false,
        status: "required",
        setup_path: "/app/requester/profile/setup",
        required_fields: [],
        missing_fields: [{ key: "full_name", label: "ФИО" }],
        blocks: {
          ticket_create: true,
          ticket_preview: true,
          knowledge_requester_actions: true,
          device_binding_confirmation: false,
        },
      },
      profile_schema: {
        schema_key: "requester_profile",
        fields: [],
        custom_fields: [],
        required_fields: [],
      },
      devices: [],
      active_bindings: [],
      pending_registration_claims: [],
      open_ticket_count: 0,
      tickets_requiring_user_action_count: 0,
      pending_consent_count: 0,
      recent_tickets: [],
      feature_flags: { requester_no_device_create: false, requester_ticket_create: false },
      policies: { device_selection_required: false },
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/requester/bootstrap") {
        return jsonResponse({ status: "success", data: incompleteBootstrap });
      }
      if (url === "/api/web/requester/tickets" && init?.method !== "POST") {
        return jsonResponse({ status: "success", data: { tickets: [] } });
      }
      if (url === "/api/web/requester/consents?status=pending") {
        return jsonResponse({ status: "success", data: { consents: [] } });
      }
      if (url === "/public_api/ticket_forms/current?pack_key=request_forms") {
        return jsonResponse({ status: "ok", pack: { pack_key: "request_forms", version: "test", forms: [] } });
      }
      if (url === "/api/service-catalog/current") {
        return jsonResponse({ status: "ok", catalog_version: "test", services: [] });
      }
      if (url === "/api/registry/options") {
        return jsonResponse({ status: "success", data: { departments: [], locations: [] } });
      }
      if (url === "/api/web/registry/browser-pairings/lookup" && init?.method === "POST") {
        return jsonResponse({
          status: "success",
          data: {
            pairing_id: "pair-incomplete-profile",
            purpose: "registration",
            expires_at: "2026-06-18T23:59:59Z",
            next_url: "/app/device/register?pairing_id=pair-incomplete-profile",
          },
        });
      }
      if (url === "/api/web/registry/browser-pairings/pair-incomplete-profile" && !init?.method) {
        return jsonResponse({
          status: "success",
          data: {
            pairing_id: "pair-incomplete-profile",
            purpose: "registration",
            status: "pending",
            device: {
              device_id: "device-incomplete-profile",
              hostname: "WIN-INCOMPLETE",
              os: "Windows",
              agent_version: "3.1.70",
            },
          },
        });
      }
      if (url === "/api/web/registry/browser-pairings/pair-incomplete-profile/registration/confirm" && init?.method === "POST") {
        return jsonResponse({
          status: "success",
          data: {
            pairing_id: "pair-incomplete-profile",
            purpose: "registration",
            status: "confirmed",
            device: {
              device_id: "device-incomplete-profile",
              hostname: "WIN-INCOMPLETE",
              os: "Windows",
              agent_version: "3.1.70",
            },
            registration: { status: "approved", device_id: "device-incomplete-profile" },
          },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    render(<RequesterWorkspacePage />);

    await screen.findByText("Заполните профиль");
    const codeInput = screen.getByLabelText("Код привязки");
    expect(codeInput).not.toBeDisabled();
    fireEvent.change(codeInput, { target: { value: "ABCD-1234" } });
    fireEvent.click(screen.getByRole("button", { name: "Проверить код привязки" }));

    expect(await screen.findByText("WIN-INCOMPLETE")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить привязку устройства" }));

    expect(await screen.findAllByText("Устройство привязано")).not.toHaveLength(0);
    expect(
      fetchMock.mock.calls.some(([input, init]) => String(input) === "/api/web/requester/tickets" && init?.method === "POST"),
    ).toBe(false);
  });

  it("shows only emergency forms when profile and agent context are incomplete", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/requester/bootstrap") {
        return jsonResponse({
          status: "success",
          data: {
            workspace: "requester",
            profile: null,
            profile_completion: {
              complete: false,
              status: "required",
              setup_path: "/app/requester/profile/setup",
              required_fields: [],
              missing_fields: [{ key: "full_name", label: "ФИО" }],
              blocks: {
                ticket_create: true,
                ticket_preview: true,
                device_binding_confirmation: false,
              },
            },
            profile_schema: {
              schema_key: "requester_profile",
              fields: [],
              custom_fields: [],
              required_fields: [],
            },
            devices: [],
            active_bindings: [],
            pending_registration_claims: [],
            open_ticket_count: 0,
            tickets_requiring_user_action_count: 0,
            pending_consent_count: 0,
            recent_tickets: [],
            feature_flags: { requester_no_device_create: false, requester_ticket_create: false },
          },
        });
      }
      if (url === "/api/web/requester/tickets" && init?.method !== "POST") {
        return jsonResponse({ status: "success", data: { tickets: [] } });
      }
      if (url === "/api/web/requester/consents?status=pending") {
        return jsonResponse({ status: "success", data: { consents: [] } });
      }
      if (url === "/public_api/ticket_forms/current?pack_key=request_forms") {
        return jsonResponse({
          status: "ok",
          pack: {
            pack_key: "request_forms",
            version: "pa10",
            forms: [
              {
                key: "profile_completion_help",
                title: "Помощь с заполнением профиля",
                request_kind: "profile_completion_help",
                availability_policy: {
                  available_without_completed_profile: true,
                  available_without_agent_binding: true,
                  requires_manual_triage: true,
                  contact_required: true,
                  allowed_for_anonymous: false,
                },
                fields: [
                  { key: "contact_phone", label: "Телефон для связи", type: "phone", required: true },
                ],
              },
              {
                key: "agent_binding_help",
                title: "Помощь с привязкой агента",
                request_kind: "agent_binding_help",
                availability_policy: {
                  available_without_completed_profile: true,
                  available_without_agent_binding: true,
                  requires_manual_triage: true,
                  contact_required: true,
                  allowed_for_anonymous: false,
                },
                fields: [
                  { key: "contact_phone", label: "Телефон для связи", type: "phone", required: true },
                ],
              },
              {
                key: "normal_access",
                title: "Обычный доступ",
                request_kind: "request",
                availability_policy: {
                  available_without_completed_profile: false,
                  available_without_agent_binding: false,
                  requires_manual_triage: false,
                  contact_required: false,
                  allowed_for_anonymous: false,
                },
                fields: [{ key: "summary", label: "Кратко", type: "text", required: false }],
              },
            ],
          },
        });
      }
      if (url === "/api/service-catalog/current") {
        return jsonResponse({ status: "ok", catalog_version: "test", services: [] });
      }
      if (url === "/api/registry/options") {
        return jsonResponse({ status: "success", data: { departments: [], locations: [] } });
      }
      if (url === "/api/web/requester/tickets" && init?.method === "POST") {
        return jsonResponse({
          status: "success",
          data: {
            ticket_id: "T-EMERGENCY",
            ticket: { ticket_id: "T-EMERGENCY", title: "Помощь с заполнением профиля", status: "new" },
          },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    render(<RequesterWorkspacePage />);

    const formSelect = await screen.findByLabelText("Форма обращения заявителя");
    expect(screen.getByRole("option", { name: "Помощь с заполнением профиля" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Помощь с привязкой агента" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Обычный доступ" })).not.toBeInTheDocument();
    expect(formSelect).toHaveValue("profile_completion_help");
    expect(screen.getByText("Диагностика может быть недоступна, пока поддержка не уточнит профиль и основное устройство.")).toBeInTheDocument();
    expect(screen.getByText("Обращение попадет на ручную обработку поддержки.")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Поле формы обращения contact_phone"), { target: { value: "+7 000 555-55-55" } });
    fireEvent.change(screen.getByLabelText("Описание"), { target: { value: "Не могу войти и заполнить профиль" } });
    const createButton = screen.getByLabelText("Создать обращение в кабинете пользователя");
    expect(createButton).not.toBeDisabled();
    fireEvent.click(createButton);

    await screen.findByText("Создано обращение T-EMERGENCY");
    const createCall = fetchMock.mock.calls.find(
      ([input, init]) => String(input) === "/api/web/requester/tickets" && (init as RequestInit | undefined)?.method === "POST",
    );
    expect(JSON.parse(String((createCall?.[1] as RequestInit).body))).toMatchObject({
      form_key: "profile_completion_help",
      form_payload: { contact_phone: "+7 000 555-55-55" },
    });
  });

  it("shows only agent binding help when the profile is complete but no agent is linked", async () => {
    installSetupAssistanceFormsMock({ profileComplete: true });

    render(<RequesterWorkspacePage />);

    const formSelect = await screen.findByLabelText("Форма обращения заявителя");
    expect(screen.queryByRole("option", { name: "Помощь с заполнением профиля" })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Помощь с привязкой агента" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Обычный доступ" })).not.toBeInTheDocument();
    expect(formSelect).toHaveValue("agent_binding_help");
  });

  it("shows knowledge guidance for setup assistance forms without service catalog offerings", async () => {
    const fetchMock = installSetupAssistanceFormsMock({
      profileComplete: true,
      knowledgeSuggestions: [
        {
          item_id: "kb-agent-binding-help",
          version_id: "kb-agent-binding-help-v1",
          slug: "agent-binding-help",
          type: "article",
          title: "Agent binding setup guide",
          summary: "How to finish binding when the agent cannot confirm automatically.",
          snippet: "Open the agent, copy the pairing code, then confirm it in the requester cabinet.",
        },
      ],
    });

    render(<RequesterWorkspacePage />);

    await screen.findByText("Agent binding setup guide");
    await waitFor(() => {
      const suggestCall = fetchMock.mock.calls.find(([input]) => String(input) === "/api/knowledge/suggest");
      expect(suggestCall).toBeTruthy();
      expect(JSON.parse(String((suggestCall?.[1] as RequestInit).body))).toMatchObject({
        request_template_key: "agent_binding_help",
        surface: "requester_portal",
      });
    });
  });

  it("uses the setup assistance form key for knowledge even when service catalog is loaded", async () => {
    const fetchMock = installSetupAssistanceFormsMock({
      profileComplete: true,
      withServiceCatalog: true,
    });

    render(<RequesterWorkspacePage />);

    await waitFor(() => {
      const suggestCall = fetchMock.mock.calls.find(([input]) => String(input) === "/api/knowledge/suggest");
      expect(suggestCall).toBeTruthy();
      expect(JSON.parse(String((suggestCall?.[1] as RequestInit).body))).toMatchObject({
        request_template_key: "agent_binding_help",
        surface: "requester_portal",
      });
      expect(JSON.parse(String((suggestCall?.[1] as RequestInit).body)).offering_code).toBeUndefined();
      expect(JSON.parse(String((suggestCall?.[1] as RequestInit).body)).service_code).toBeUndefined();
    });
  });

  it("shows only profile completion help when an agent is linked but the profile is incomplete", async () => {
    installSetupAssistanceFormsMock({
      profileComplete: false,
      devices: [{ device_id: "device-linked", hostname: "LINKED-PC", os: "Windows", agent_version: "3.1.71" }],
    });

    render(<RequesterWorkspacePage />);

    const formSelect = await screen.findByLabelText("Форма обращения заявителя");
    expect(screen.getByRole("option", { name: "Помощь с заполнением профиля" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Помощь с привязкой агента" })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Обычный доступ" })).not.toBeInTheDocument();
    expect(formSelect).toHaveValue("profile_completion_help");
  });

  it("saves requester profile from registry pickers and unlocks the workspace", async () => {
    window.history.pushState({}, "", "/app/requester/profile/setup");
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/requester/bootstrap") {
        return jsonResponse({
          status: "success",
          data: {
            workspace: "requester",
            profile: null,
            profile_completion: {
              complete: false,
              status: "required",
              setup_path: "/app/requester/profile/setup",
              required_fields: [],
              missing_fields: [{ key: "full_name", label: "ФИО" }],
            },
            profile_schema: {
              schema_key: "requester_profile",
              fields: [
                {
                  key: "cost_center",
                  label: "Центр затрат",
                  type: "text",
                  required: true,
                  visible: true,
                  custom: true,
                  system: false,
                  storage_target: "registry_people.metadata_json.profile_custom_fields.cost_center",
                  help_text: "Укажите центр затрат из карточки сотрудника",
                },
              ],
              custom_fields: [
                {
                  key: "cost_center",
                  label: "Центр затрат",
                  type: "text",
                  required: true,
                  visible: true,
                  custom: true,
                  system: false,
                  storage_target: "registry_people.metadata_json.profile_custom_fields.cost_center",
                  help_text: "Укажите центр затрат из карточки сотрудника",
                },
              ],
              required_fields: [
                { key: "full_name", label: "ФИО" },
                { key: "cost_center", label: "Центр затрат" },
              ],
            },
            devices: [],
            active_bindings: [],
            pending_registration_claims: [],
            open_ticket_count: 0,
            tickets_requiring_user_action_count: 0,
            pending_consent_count: 0,
            recent_tickets: [],
            feature_flags: { requester_no_device_create: false, requester_ticket_create: false },
          },
        });
      }
      if (url === "/api/web/requester/tickets" && init?.method !== "POST") {
        return jsonResponse({ status: "success", data: { tickets: [] } });
      }
      if (url === "/api/web/requester/consents?status=pending") {
        return jsonResponse({ status: "success", data: { consents: [] } });
      }
      if (url === "/public_api/ticket_forms/current?pack_key=request_forms") {
        return jsonResponse({ status: "ok", pack: { pack_key: "request_forms", version: "test", forms: [] } });
      }
      if (url === "/api/service-catalog/current") {
        return jsonResponse({ status: "ok", catalog_version: "test", services: [] });
      }
      if (url === "/api/registry/options") {
        return jsonResponse({
          status: "success",
          data: {
            departments: [{ value: "dept-1", label: "ИТ" }],
            locations: [{ value: "loc-1", label: "Офис 7 / 701" }],
          },
        });
      }
      if (url === "/api/web/requester/profile" && init?.method === "PUT") {
        return jsonResponse({
          status: "success",
          data: {
            profile: {
              person_id: "person-setup",
              display_name: "Иван Петров",
              full_name: "Иван Петров",
              department_id: "dept-1",
              location_id: "loc-1",
              phone: "1234",
              custom_fields: { cost_center: "CC-10" },
            },
            profile_completion: {
              complete: true,
              status: "complete",
              setup_path: "/app/requester/profile/setup",
              required_fields: [],
              missing_fields: [],
            },
            profile_policy: { editable: true, editable_fields: [], change_request_required: false },
            profile_schema: {
              schema_key: "requester_profile",
              fields: [],
              custom_fields: [],
              required_fields: [],
            },
          },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    render(<RequesterWorkspacePage />);

    const registerLink = await screen.findByRole("link", { name: "Создать аккаунт" });
    expect(registerLink).toHaveAttribute(
      "href",
      "/app/register?switch_account=1&next=%2Fapp%2Frequester%2Fprofile%2Fsetup",
    );

    fireEvent.change(await screen.findByLabelText("ФИО"), { target: { value: "Иван Петров" } });
    fireEvent.change(screen.getByLabelText("Телефон или внутренний номер"), { target: { value: "1234" } });
    await screen.findByRole("option", { name: "ИТ" });
    fireEvent.change(screen.getByLabelText("Подразделение"), { target: { value: "dept-1" } });
    fireEvent.change(screen.getByLabelText("Локация"), { target: { value: "loc-1" } });
    fireEvent.change(screen.getByLabelText("Должность"), { target: { value: "Инженер" } });
    fireEvent.change(screen.getByLabelText(/Центр затрат/), { target: { value: "CC-10" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить профиль" }));

    expect(await screen.findByText("Профиль сохранен. Теперь можно продолжить работу в кабинете пользователя.")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input, init]) => String(input) === "/api/web/requester/profile" && init?.method === "PUT"),
      ).toBe(true),
    );
    const updateCall = fetchMock.mock.calls.find(
      ([input, init]) => String(input) === "/api/web/requester/profile" && init?.method === "PUT",
    );
    expect(JSON.parse(String(updateCall?.[1]?.body))).toMatchObject({
      full_name: "Иван Петров",
      department_id: "dept-1",
      location_id: "loc-1",
      phone: "1234",
      position: "Инженер",
      custom_fields: { cost_center: "CC-10" },
    });
    expect(window.location.pathname).toBe("/app/requester");
  });

  it("looks up a device-link code and sends a registration claim from the requester cabinet", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/requester/bootstrap") {
        return jsonResponse({
          status: "success",
          data: {
            workspace: "requester",
            profile: {
              person_id: "person-complete",
              display_name: "Иван Петров",
              full_name: "Иван Петров",
              phone: "1234",
              department_id: "dept-1",
              location_id: "loc-1",
            },
            profile_completion: {
              complete: true,
              status: "complete",
              setup_path: "/app/requester/profile/setup",
              required_fields: [],
              missing_fields: [],
            },
            devices: [],
            active_bindings: [],
            pending_registration_claims: [],
            open_ticket_count: 0,
            tickets_requiring_user_action_count: 0,
            pending_consent_count: 0,
            recent_tickets: [],
            feature_flags: { requester_no_device_create: true, requester_ticket_create: true },
            policies: { device_selection_required: false },
          },
        });
      }
      if (url === "/api/web/requester/tickets" && init?.method !== "POST") {
        return jsonResponse({ status: "success", data: { tickets: [] } });
      }
      if (url === "/api/web/requester/consents?status=pending") {
        return jsonResponse({ status: "success", data: { consents: [] } });
      }
      if (url === "/public_api/ticket_forms/current?pack_key=request_forms") {
        return jsonResponse({ status: "ok", pack: { pack_key: "request_forms", version: "test", forms: [] } });
      }
      if (url === "/api/service-catalog/current") {
        return jsonResponse({ status: "ok", catalog_version: "test", services: [] });
      }
      if (url === "/api/web/registry/browser-pairings/lookup") {
        expect(init?.method).toBe("POST");
        expect(JSON.parse(String(init?.body))).toEqual({ pairing_code: "ABCD-1234" });
        return jsonResponse({
          status: "success",
          data: {
            pairing_id: "pair-r4",
            purpose: "registration",
            next_url: "/app/device/register?pairing_id=pair-r4",
          },
        });
      }
      if (url === "/api/web/registry/browser-pairings/pair-r4") {
        return jsonResponse({
          status: "success",
          data: {
            pairing_id: "pair-r4",
            purpose: "registration",
            status: "pending",
            device: { device_id: "device-r4", hostname: "R4-PC", os: "Windows", agent_version: "3.1.64" },
          },
        });
      }
      if (url === "/api/web/registry/browser-pairings/pair-r4/registration/confirm") {
        expect(init?.method).toBe("POST");
        return jsonResponse({
          status: "success",
          data: {
            pairing_id: "pair-r4",
            purpose: "registration",
            status: "confirmed",
            claim_id: "claim-r4",
            device: { device_id: "device-r4", hostname: "R4-PC", os: "Windows", agent_version: "3.1.64" },
            registration: { status: "pending_admin_review", device_id: "device-r4" },
          },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    render(<RequesterWorkspacePage />);

    fireEvent.change(await screen.findByLabelText("Код привязки"), { target: { value: "abcd-1234" } });
    fireEvent.click(screen.getByRole("button", { name: "Проверить код привязки" }));

    expect(await screen.findByText("R4-PC")).toBeInTheDocument();
    expect(screen.getByText("Windows · Агент 3.1.64")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Подтвердить привязку устройства" }));

    expect((await screen.findAllByText("Ожидает проверки администратора")).length).toBeGreaterThan(0);
    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(
          ([input, init]) =>
            String(input) === "/api/web/registry/browser-pairings/pair-r4/registration/confirm" &&
            init?.method === "POST",
        ),
      ).toBe(true);
    });
  });

  it("loads a direct requester device-link URL and shows the device before confirmation", async () => {
    window.history.pushState({}, "", "/app/requester/devices?pairing_id=pair-direct");
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/requester/bootstrap") {
        return jsonResponse({
          status: "success",
          data: {
            workspace: "requester",
            profile: {
              person_id: "person-direct",
              display_name: "Иван Петров",
              full_name: "Иван Петров",
              phone: "1234",
              department_id: "dept-1",
              location_id: "loc-1",
            },
            profile_completion: {
              complete: true,
              status: "complete",
              setup_path: "/app/requester/profile/setup",
              required_fields: [],
              missing_fields: [],
            },
            devices: [],
            active_bindings: [],
            pending_registration_claims: [],
            open_ticket_count: 0,
            tickets_requiring_user_action_count: 0,
            pending_consent_count: 0,
            recent_tickets: [],
            feature_flags: { requester_no_device_create: true, requester_ticket_create: true },
          },
        });
      }
      if (url === "/api/web/requester/tickets" && init?.method !== "POST") {
        return jsonResponse({ status: "success", data: { tickets: [] } });
      }
      if (url === "/api/web/requester/consents?status=pending") {
        return jsonResponse({ status: "success", data: { consents: [] } });
      }
      if (url === "/public_api/ticket_forms/current?pack_key=request_forms") {
        return jsonResponse({ status: "ok", pack: { pack_key: "request_forms", version: "test", forms: [] } });
      }
      if (url === "/api/service-catalog/current") {
        return jsonResponse({ status: "ok", catalog_version: "test", services: [] });
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
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    render(<RequesterWorkspacePage />);

    expect(await screen.findByText("DIRECT-PC")).toBeInTheDocument();
    expect(screen.getByText("Проверьте устройство и подтвердите привязку.")).toBeInTheDocument();
  });
});
