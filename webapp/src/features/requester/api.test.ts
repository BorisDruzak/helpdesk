import { afterEach, describe, expect, it, vi } from "vitest";

import {
  authorizePublicTicket,
  closeRequesterTicket,
  createPublicTicket,
  createRequesterTicket,
  fetchRequesterTicket,
  fetchPublicFormPack,
  fetchPublicTicket,
  reopenRequesterTicket,
  reopenPublicTicket,
  sendRequesterTicketMessage,
  sendPublicTicketMessage,
  submitRequesterTicketFeedback,
  submitPublicTicketFeedback,
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

  it("submits structured CSAT and reopens through public ticket endpoints", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/public_api/tickets/T-1/feedback") {
        return jsonResponse({ status: "ok", ok: true, feedback_id: "fb-1", reopen_available: true });
      }
      if (url === "/public_api/tickets/T-1/reopen") {
        return jsonResponse({ status: "ok", ticket_id: "T-1", ticket_status: "in_progress", reopen_id: "ro-1" });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    const feedback = await submitPublicTicketFeedback("T-1", "public-token", {
      rating: 2,
      problem_resolved: false,
      reason_codes: ["not_resolved"],
      comment: "Still broken",
    });
    const reopen = await reopenPublicTicket("T-1", "public-token", {
      reason_code: "problem_returned",
      reason_comment: "Problem returned",
      linked_feedback_id: feedback.feedback_id,
    });

    expect(feedback.reopen_available).toBe(true);
    expect(reopen.ticket_status).toBe("in_progress");
    expect(fetchMock).toHaveBeenCalledWith(
      "/public_api/tickets/T-1/feedback",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Authorization: "Bearer public-token" }),
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

describe("authenticated requester api", () => {
  it("creates an authenticated requester ticket with catalog form fields", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        status: "success",
        data: {
          ticket_id: "T-52",
          ticket: { ticket_id: "T-52", status: "new" },
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    const result = await createRequesterTicket({
      device_id: "device-1",
      title: "Laptop broken",
      description: "Laptop does not boot",
      user_display_name: "Requester One",
      service_code: "workplace",
      offering_code: "laptop_broken",
      offering_full_code: "workplace.laptop_broken",
      request_template_key: "breakage",
      form_key: "breakage",
      form_pack_key: "request_forms",
      form_pack_version: "2026.06",
      form_payload: { summary: "No boot" },
      ticket_type: "incident",
    });

    expect(result.ticket_id).toBe("T-52");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/requester/tickets",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        body: JSON.stringify({
          device_id: "device-1",
          title: "Laptop broken",
          description: "Laptop does not boot",
          user_display_name: "Requester One",
          service_code: "workplace",
          offering_code: "laptop_broken",
          offering_full_code: "workplace.laptop_broken",
          request_template_key: "breakage",
          form_key: "breakage",
          form_pack_key: "request_forms",
          form_pack_version: "2026.06",
          form_payload: { summary: "No boot" },
          ticket_type: "incident",
        }),
      }),
    );
  });

  it("loads owned ticket detail and sends authenticated message", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/web/requester/tickets/T-42") {
        return jsonResponse({
          status: "success",
          data: {
            ticket: { ticket_id: "T-42", title: "Owned ticket", status: "waiting_on_user" },
          },
        });
      }
      if (url === "/api/web/requester/tickets/T-42/message") {
        return jsonResponse({ status: "success", data: { message_id: "m-42", event_id: 12 } });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    const detail = await fetchRequesterTicket("T-42");
    const sent = await sendRequesterTicketMessage("T-42", "Authenticated follow-up");

    expect(detail.ticket.ticket_id).toBe("T-42");
    expect(sent.message_id).toBe("m-42");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/requester/tickets/T-42",
      expect.objectContaining({ credentials: "same-origin", cache: "no-store" }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/requester/tickets/T-42/message",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        body: JSON.stringify({ text: "Authenticated follow-up" }),
      }),
    );
  });

  it("submits authenticated requester close, feedback, and reopen actions", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/web/requester/tickets/T-42/close") {
        return jsonResponse({
          status: "success",
          data: { ticket: { ticket_id: "T-42", status: "closed" } },
        });
      }
      if (url === "/api/web/requester/tickets/T-42/feedback") {
        return jsonResponse({
          status: "success",
          data: { ok: true, feedback_id: "fb-42", reopen_available: true },
        });
      }
      if (url === "/api/web/requester/tickets/T-42/reopen") {
        return jsonResponse({
          status: "success",
          data: { ok: true, ticket_id: "T-42", ticket_status: "in_progress", reopen_id: "ro-42" },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    const closed = await closeRequesterTicket("T-42");
    const feedback = await submitRequesterTicketFeedback("T-42", {
      rating: 2,
      problem_resolved: false,
      reason_codes: ["not_resolved"],
      comment: "Still broken",
    });
    const reopened = await reopenRequesterTicket("T-42", {
      reason_code: "not_resolved",
      reason_comment: "Still broken",
      linked_feedback_id: feedback.feedback_id,
    });

    expect(closed.ticket.status).toBe("closed");
    expect(feedback.reopen_available).toBe(true);
    expect(reopened.ticket_status).toBe("in_progress");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/requester/tickets/T-42/close",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
      }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/requester/tickets/T-42/feedback",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        body: JSON.stringify({
          rating: 2,
          problem_resolved: false,
          reason_codes: ["not_resolved"],
          comment: "Still broken",
        }),
      }),
    );
  });
});
