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
});
