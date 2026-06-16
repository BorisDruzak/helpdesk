import { afterEach, describe, expect, it, vi } from "vitest";

import {
  authorizePublicTicket,
  approveRequesterConsent,
  claimPublicRequesterTicket,
  closeRequesterTicket,
  createPublicTicket,
  createRequesterTicket,
  denyRequesterConsent,
  fetchRequesterConsents,
  fetchRequesterDevice,
  fetchRequesterProfile,
  fetchRequesterTicket,
  fetchPublicFormPack,
  fetchPublicTicket,
  previewRequesterTicket,
  reopenRequesterTicket,
  reopenPublicTicket,
  searchRequesterOnBehalfPeople,
  sendRequesterTicketMessage,
  sendPublicTicketMessage,
  submitRequesterTicketFeedback,
  submitPublicTicketFeedback,
  uploadRequesterTicketAttachment,
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
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
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
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
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
  it("loads and decides requester consents through the requester boundary", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/requester/consents?status=pending") {
        return jsonResponse({
          status: "success",
          data: {
            consents: [
              {
                consent_id: "consent-1",
                subject_type: "remote_assist",
                subject_id: "remote-1",
                status: "pending",
                title: "Remote Assist",
              },
            ],
          },
        });
      }
      if (url === "/api/web/requester/consents/consent-1/approve") {
        return jsonResponse({
          status: "success",
          data: { consent: { consent_id: "consent-1", status: "approved", subject_type: "remote_assist", subject_id: "remote-1" } },
        });
      }
      if (url === "/api/web/requester/consents/consent-2/deny") {
        return jsonResponse({
          status: "success",
          data: { consent: { consent_id: "consent-2", status: "denied", subject_type: "operation", subject_id: "op-1" } },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    const consents = await fetchRequesterConsents();
    const approved = await approveRequesterConsent("consent-1");
    const denied = await denyRequesterConsent("consent-2", "no");

    expect(consents[0]?.consent_id).toBe("consent-1");
    expect(approved.consent.status).toBe("approved");
    expect(denied.consent.status).toBe("denied");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/requester/consents/consent-2/deny",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        body: JSON.stringify({ reason: "no" }),
      }),
    );
  });

  it("loads authenticated requester profile through the requester boundary", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        status: "success",
        data: {
          profile: { person_id: "person-1", display_name: "Requester One", email: "requester@example.test" },
          identities: [{ provider: "ui_login", identifier: "requester@example.test", verified: true }],
          devices: [{ device_id: "device-1", hostname: "desk-1" }],
          active_bindings: [{ binding_id: "binding-1", device_id: "device-1", status: "active" }],
          pending_registration_claims: [],
          profile_policy: { editable: false, editable_fields: [], change_request_required: true },
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    const result = await fetchRequesterProfile();

    expect(result.profile?.person_id).toBe("person-1");
    expect(result.identities[0]?.provider).toBe("ui_login");
    expect(result.profile_policy.editable).toBe(false);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/requester/profile",
      expect.objectContaining({ credentials: "same-origin", cache: "no-store" }),
    );
  });

  it("loads authenticated requester device detail through the requester boundary", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        status: "success",
        data: {
          device: {
            device_id: "device-1",
            hostname: "desk-1",
            relationship_type: "primary_user",
            binding_status: "active",
            open_ticket_count: 2,
            available_actions: { create_ticket: true },
          },
          recent_tickets: [{ ticket_id: "T-1", title: "Device ticket" }],
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    const result = await fetchRequesterDevice("device-1");

    expect(result.device.device_id).toBe("device-1");
    expect(result.device.open_ticket_count).toBe(2);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/requester/devices/device-1",
      expect.objectContaining({ credentials: "same-origin", cache: "no-store" }),
    );
  });

  it("previews an authenticated requester ticket through the requester boundary", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        status: "success",
        data: {
          ok: true,
          service: { code: "workplace", title: "Workplace" },
          offering: { code: "laptop_broken", full_code: "workplace.laptop_broken", title: "Laptop broken" },
          warnings: [],
          blockers: [],
          would_create_ticket: false,
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    const result = await previewRequesterTicket({
      device_id: "device-1",
      service_code: "workplace",
      offering_code: "laptop_broken",
      offering_full_code: "workplace.laptop_broken",
      request_template_key: "breakage",
      form_key: "breakage",
      form_payload: { summary: "No boot" },
      ticket_context: { affected_person_id: "person-affected", on_behalf_reason: "phone call" },
      description: "Laptop does not boot",
    });

    expect(result.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/requester/tickets/preview",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        body: JSON.stringify({
          device_id: "device-1",
          service_code: "workplace",
          offering_code: "laptop_broken",
          offering_full_code: "workplace.laptop_broken",
          request_template_key: "breakage",
          form_key: "breakage",
          form_payload: { summary: "No boot" },
          ticket_context: { affected_person_id: "person-affected", on_behalf_reason: "phone call" },
          description: "Laptop does not boot",
        }),
      }),
    );
  });

  it("searches on-behalf people through the requester boundary", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
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
      }),
    );
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    const result = await searchRequesterOnBehalfPeople({ form_key: "breakage", q: "Affected" });

    expect(result.people[0].display_name).toBe("Affected One");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/requester/on-behalf/people?form_key=breakage&q=Affected",
      expect.objectContaining({ credentials: "same-origin", cache: "no-store" }),
    );
  });

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
      ticket_context: { affected_person_id: "person-affected", on_behalf_reason: "phone call" },
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
          ticket_context: { affected_person_id: "person-affected", on_behalf_reason: "phone call" },
          ticket_type: "incident",
        }),
      }),
    );
  });

  it("claims a public ticket into the authenticated requester workspace", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        status: "success",
        data: {
          ticket_id: "T-91",
          claimed: true,
          requester_person_id: "person-91",
          ticket: { ticket_id: "T-91", status: "new" },
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    const result = await claimPublicRequesterTicket("T-91", "ABCD12");

    expect(result.claimed).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/requester/tickets/claim-public",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        body: JSON.stringify({ ticket_id: "T-91", code: "ABCD12" }),
      }),
    );
  });

  it("loads owned ticket detail, uploads an attachment, and sends authenticated message refs", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/requester/tickets/T-42") {
        return jsonResponse({
          status: "success",
          data: {
            ticket: { ticket_id: "T-42", title: "Owned ticket", status: "waiting_on_user" },
          },
        });
      }
      if (url === "/api/upload") {
        return jsonResponse({
          status: "success",
          artifact_id: "artifact-42",
          filename: "requester-log.txt",
          url: "/api/artifacts/artifact-42/download",
          size: 19,
          mime_type: "text/plain",
          kind: "file",
        });
      }
      if (url === "/api/web/requester/tickets/T-42/message") {
        return jsonResponse({ status: "success", data: { message_id: "m-42", event_id: 12, attachments_count: 1 } });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    const detail = await fetchRequesterTicket("T-42");
    const uploaded = await uploadRequesterTicketAttachment("T-42", new File(["requester evidence"], "requester-log.txt", { type: "text/plain" }));
    const sent = await sendRequesterTicketMessage("T-42", "Authenticated follow-up", [uploaded.artifact_id]);

    expect(detail.ticket.ticket_id).toBe("T-42");
    expect(uploaded.artifact_id).toBe("artifact-42");
    expect(sent.message_id).toBe("m-42");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/requester/tickets/T-42",
      expect.objectContaining({ credentials: "same-origin", cache: "no-store" }),
    );
    const uploadCall = fetchMock.mock.calls.find(([input]) => String(input) === "/api/upload");
    expect(uploadCall?.[1]).toEqual(
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        body: expect.any(FormData),
      }),
    );
    const uploadBody = (uploadCall?.[1] as RequestInit).body as FormData;
    expect(uploadBody.get("ticket_id")).toBe("T-42");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/requester/tickets/T-42/message",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        body: JSON.stringify({ text: "Authenticated follow-up", attachment_refs: ["artifact-42"] }),
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
