import { afterEach, describe, expect, it, vi } from "vitest";

import {
  authorizePublicTicket,
  createPublicTicket,
  fetchPublicFormPack,
  fetchPublicTicket,
  sendPublicTicketMessage,
} from "./api";

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

describe("requester public api", () => {
  it("loads current request form pack", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        status: "ok",
        pack: {
          pack_key: "request_forms",
          version: "1.0.0",
          forms: [{ key: "incident", title: "Инцидент", fields: [] }],
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    const pack = await fetchPublicFormPack();

    expect(fetchMock).toHaveBeenCalledWith(
      "/public_api/ticket_forms/current?pack_key=request_forms",
      expect.objectContaining({ cache: "no-store" }),
    );
    expect(pack.forms[0]?.key).toBe("incident");
  });

  it("creates a public ticket using the existing public endpoint", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        status: "ok",
        ticket: { ticket_id: "T-1", ticket_code: "HD-1", status: "new" },
        public_access_code: "ABCD12",
        public_token: "public-token",
      }),
    );
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    const result = await createPublicTicket({
      title: "Заявка",
      description: "Не открывается сайт",
      user_display_name: "Иван",
      urgency: false,
      importance: false,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/public_api/tickets/create",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          title: "Заявка",
          description: "Не открывается сайт",
          user_display_name: "Иван",
          urgency: false,
          importance: false,
        }),
      }),
    );
    expect(result.public_access_code).toBe("ABCD12");
    expect(result.public_token).toBe("public-token");
  });

  it("exchanges an access code for a public ticket token", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        status: "ok",
        ticket_id: "T-1",
        public_token: "public-token",
        public_token_expires_at: "2026-04-27T12:00:00Z",
      }),
    );
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    const result = await authorizePublicTicket("T-1", "abcd12");

    expect(fetchMock).toHaveBeenCalledWith(
      "/public_api/tickets/T-1/authorize",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ code: "abcd12" }),
      }),
    );
    expect(result.public_token).toBe("public-token");
  });

  it("loads and writes ticket chat with bearer token", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/tickets/T-1") {
        return jsonResponse({
          status: "ok",
          ticket: { ticket_id: "T-1", ticket_code: "HD-1", status: "new" },
          messages: [{ message_id: "m1", text: "Здравствуйте", from_role: "support" }],
        });
      }
      if (url === "/api/tickets/T-1/message") {
        return jsonResponse({ status: "ok", message_id: "m2" });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    const ticket = await fetchPublicTicket("T-1", "public-token");
    await sendPublicTicketMessage("T-1", "public-token", "Спасибо");

    expect(ticket.messages[0]?.text).toBe("Здравствуйте");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/tickets/T-1",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer public-token" }),
      }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/tickets/T-1/message",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ text: "Спасибо", visibility: "public" }),
      }),
    );
  });

  it("throws a readable error for non-json failures", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("not json", { status: 503, headers: { "Content-Type": "text/plain" } })) as typeof fetch,
    );

    await expect(fetchPublicFormPack()).rejects.toThrow("Не удалось загрузить форму заявки");
  });
});
