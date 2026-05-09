import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { QueryProvider } from "../../app/providers/query-provider";
import { RequesterTicketPage } from "./index";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

function renderRequesterTicket(path: string) {
  render(
    <QueryProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route element={<RequesterTicketPage />} path="/app/ticket/:ticketId" />
          <Route element={<RequesterTicketPage />} path="/app/ticket" />
        </Routes>
      </MemoryRouter>
    </QueryProvider>,
  );
}

afterEach(() => {
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

describe("RequesterTicketPage", () => {
  it("authorizes by code, loads public messages and sends a reply", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/public_api/tickets/T-1/authorize") {
        expect(init?.method).toBe("POST");
        expect(init?.body).toBe(JSON.stringify({ code: "A1B2C3" }));
        return jsonResponse({
          status: "ok",
          ticket_id: "T-1",
          public_token: "token-1",
          public_token_expires_at: "2026-04-27T12:00:00Z",
        });
      }
      if (url === "/api/tickets/T-1") {
        return jsonResponse({
          status: "ok",
          ticket: { ticket_id: "T-1", ticket_code: "HD-1", status: "waiting_on_user" },
          messages: [{ message_id: "m1", text: "Проверьте доступ", from_role: "support" }],
        });
      }
      if (url === "/api/tickets/T-1/message") {
        expect(init?.body).toBe(JSON.stringify({ text: "Проверил, работает", visibility: "public" }));
        return jsonResponse({ status: "ok", message_id: "m2" });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderRequesterTicket("/app/ticket/T-1?code=A1B2C3");

    expect(await screen.findByRole("heading", { name: "HD-1" })).toBeInTheDocument();
    expect(screen.getByText("Проверьте доступ")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Сообщение в поддержку"), {
      target: { value: "Проверил, работает" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Отправить" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/tickets/T-1/message",
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({ Authorization: "Bearer token-1" }),
        }),
      );
    });
    expect(sessionStorage.getItem("public_ticket_token:T-1")).toBe("token-1");
  });

  it("asks for a code when no public token is available", async () => {
    vi.stubGlobal("fetch", vi.fn() as unknown as typeof fetch);

    renderRequesterTicket("/app/ticket/T-2");

    expect(await screen.findByRole("heading", { name: "Вход в тикет" })).toBeInTheDocument();
    expect(screen.getByLabelText("Код доступа")).toBeInTheDocument();
  });

  it("renders requester timeline projection and hides raw system event values", async () => {
    sessionStorage.setItem("public_ticket_token:T-4", "token-4");
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/tickets/T-4") {
        return jsonResponse({
          status: "ok",
          ticket: { ticket_id: "T-4", ticket_code: "HD-4", status: "in_progress" },
          messages: [],
          events: [
            {
              id: 7,
              type: "status_changed",
              event_type: "status_changed",
              status: "unknown",
              requester_timeline_text: "Статус обращения обновлён.",
              requester_timeline_kind: "system_event",
              requester_timeline_payload: {},
              ts: "2026-05-05T09:25:00+05:00",
            },
          ],
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderRequesterTicket("/app/ticket/T-4");

    expect(await screen.findByText("Статус обращения обновлён.")).toBeInTheDocument();
    expect(screen.queryByText("status_changed")).not.toBeInTheDocument();
    expect(screen.queryByText("unknown")).not.toBeInTheDocument();
  });

  it("renders requester resolution actions from confirmation metadata", async () => {
    sessionStorage.setItem("public_ticket_token:T-3", "token-3");
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/tickets/T-3") {
        return jsonResponse({
          status: "ok",
          ticket: {
            ticket_id: "T-3",
            ticket_code: "HD-3",
            status: "resolved",
            resolution_confirmation_pending: true,
          },
          messages: [
            {
              message_id: "m-confirm",
              text: "Проблема решена. Для подтверждения используйте одну из кнопок ниже.",
              from_role: "support",
              metadata: {
                confirmation_request: {
                  request_id: "request-3",
                  options: [
                    { id: "confirm", label: "Подтверждаю" },
                    { id: "reject", label: "Не принято" },
                  ],
                },
              },
            },
          ],
        });
      }
      if (url === "/api/tickets/T-3/message") {
        expect(init?.body).toBe(
          JSON.stringify({
            text: "Подтверждаю решение",
            visibility: "public",
            metadata: {
              confirmation_response: {
                request_id: "request-3",
                option_id: "confirm",
              },
            },
          }),
        );
        return jsonResponse({ status: "ok", message_id: "m-confirm-response" });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderRequesterTicket("/app/ticket/T-3");

    expect(await screen.findByRole("button", { name: "Подтвердить и закрыть" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Отклонить решение" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Подтвердить и закрыть" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/tickets/T-3/message",
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({ Authorization: "Bearer token-3" }),
        }),
      );
    });
  });
});
