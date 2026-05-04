import { render, screen } from "@testing-library/react";
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
        </Routes>
      </MemoryRouter>
    </QueryProvider>,
  );
}

afterEach(() => {
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

describe("RequesterTicketPage public status", () => {
  it("renders requester-safe public status instead of the raw internal status", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/public_api/tickets/T-3/authorize") {
        expect(init?.method).toBe("POST");
        return jsonResponse({
          status: "ok",
          ticket_id: "T-3",
          public_token: "token-3",
          public_token_expires_at: "2026-05-04T12:00:00Z",
        });
      }
      if (url === "/api/tickets/T-3") {
        return jsonResponse({
          status: "ok",
          ticket: {
            ticket_id: "T-3",
            ticket_code: "HD-3",
            title: "Visibility check",
            status: "waiting_on_internal_team",
            public_status_label: "Requester safe status",
            requester_status_label: "Requester fallback status",
          },
          messages: [],
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderRequesterTicket("/app/ticket/T-3?code=CODE3");

    expect(await screen.findByRole("heading", { name: "HD-3" })).toBeInTheDocument();
    expect(screen.getByText("Requester safe status")).toBeInTheDocument();
    expect(screen.getByText("Статус: Requester safe status")).toBeInTheDocument();
    expect(screen.queryByText("waiting_on_internal_team")).not.toBeInTheDocument();
  });
});
