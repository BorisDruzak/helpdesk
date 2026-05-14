import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { QueryProvider } from "../../app/providers/query-provider";
import { HelpPage } from "./index";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

function renderHelpPage() {
  render(
    <QueryProvider>
      <MemoryRouter>
        <HelpPage />
      </MemoryRouter>
    </QueryProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("HelpPage", () => {
  it("creates a public ticket from the selected request form", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/public_api/ticket_forms/current?pack_key=request_forms") {
        return jsonResponse({
          status: "ok",
          pack: {
            pack_key: "request_forms",
            version: "1.2.0",
            forms: [
              {
                key: "site_down",
                title: "Сайт не открывается",
                request_kind: "site_down",
                fields: [
                  {
                    key: "url",
                    label: "Адрес сайта",
                    type: "text",
                    required: true,
                    placeholder: "https://example.com",
                  },
                ],
              },
            ],
          },
        });
      }
      if (url === "/public_api/tickets/create") {
        expect(init?.method).toBe("POST");
        expect(JSON.parse(String(init?.body))).toMatchObject({
          title: "Заявка: Сайт не открывается",
          description: "Не открывается портал",
          user_display_name: "Иван",
          form_key: "site_down",
          form_pack_key: "request_forms",
          form_pack_version: "1.2.0",
          form_payload: {
            url: "https://intranet.local",
          },
          ticket_type: "site_down",
          urgency: false,
          importance: false,
          urgency_reason: "requester_did_not_mark_urgent",
          importance_reason: "requester_did_not_mark_important",
        });
        return jsonResponse({
          status: "ok",
          ticket: { ticket_id: "T-100", ticket_code: "HD-100", status: "new" },
          public_access_code: "A1B2C3",
          public_token: "token-100",
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderHelpPage();

    expect(await screen.findByRole("heading", { name: "Создать заявку" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Как к вам обращаться"), { target: { value: "Иван" } });
    fireEvent.change(screen.getByLabelText("Описание проблемы"), { target: { value: "Не открывается портал" } });

    fireEvent.click(screen.getByRole("button", { name: "Создать заявку" }));
    expect(await screen.findByText(/Заполните обязательные поля: Адрес сайта/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Адрес сайта *"), { target: { value: "https://intranet.local" } });
    fireEvent.click(screen.getByRole("button", { name: "Создать заявку" }));

    expect(await screen.findByText("Код доступа: A1B2C3")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Открыть тикет" })).toHaveAttribute(
      "href",
      "/app/ticket/T-100?code=A1B2C3",
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  });
});
