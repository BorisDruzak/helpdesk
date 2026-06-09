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
  vi.unstubAllGlobals();
});

describe("RequesterWorkspacePage", () => {
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

    await screen.findByText("desk-1");
    fireEvent.click(screen.getByLabelText("Open requester device detail device-1"));

    await screen.findByText("Сведения об устройстве");
    await screen.findByText("desk-1.corp");
    await screen.findByText(/Основной пользователь/);
    await screen.findByText((_, element) => element?.textContent === "offline · Открытые обращения: 2");
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
    fireEvent.change(screen.getByLabelText("Public ticket id to claim"), { target: { value: "T-91" } });
    fireEvent.change(screen.getByLabelText("Public ticket access code to claim"), { target: { value: "ABCD12" } });
    fireEvent.click(screen.getByLabelText("Claim public requester ticket"));

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
    fireEvent.change(screen.getByLabelText("Attach requester file"), {
      target: { files: [new File(["requester evidence"], "requester-log.txt", { type: "text/plain" })] },
    });
    await screen.findByText("requester-log.txt");
    fireEvent.change(screen.getByLabelText("Requester message"), {
      target: { value: "Here is the requested context" },
    });
    fireEvent.click(screen.getByLabelText("Send requester message"));

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

    fireEvent.click(screen.getByLabelText("Close requester ticket"));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/requester/tickets/T-77/close",
        expect.objectContaining({ method: "POST" }),
      );
    });

    fireEvent.change(screen.getByLabelText("Requester feedback rating"), { target: { value: "2" } });
    fireEvent.click(screen.getByLabelText("Requester problem resolved"));
    fireEvent.click(screen.getByLabelText("Submit requester feedback"));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/requester/tickets/T-77/feedback",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"rating":2'),
        }),
      );
    });

    fireEvent.click(screen.getByLabelText("Reopen requester ticket"));
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
            profile: { person_id: "person-1", display_name: "Requester One", email: "requester@example.test" },
            devices: [{ device_id: "device-1", hostname: "desk-1", os: "Windows", agent_version: "3.1.61" }],
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

    await screen.findByLabelText("Requester offering");
    await screen.findByText("Проверьте питание ноутбука");
    fireEvent.click(screen.getByLabelText("Open requester knowledge suggestion"));
    await screen.findByText("Отключите зарядку на 10 секунд и подключите снова.");
    fireEvent.click(screen.getByLabelText("Mark requester knowledge suggestion not helpful"));
    fireEvent.change(screen.getByLabelText("Requester form field summary"), {
      target: { value: "Ноутбук не включается" },
    });
    fireEvent.change(screen.getByLabelText("Описание"), {
      target: { value: "Ноутбук не загружается после включения" },
    });
    fireEvent.change(screen.getByLabelText("Requester form field summary"), {
      target: { value: "Ноутбук не включается" },
    });
    fireEvent.click(screen.getByLabelText("Preview requester ticket"));

    await screen.findByText("Безопасный preview");
    fireEvent.click(screen.getByLabelText("Create requester ticket"));

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
      form_payload: { summary: "Ноутбук не включается" },
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
    fireEvent.click(screen.getByLabelText("Create requester ticket"));

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
});
