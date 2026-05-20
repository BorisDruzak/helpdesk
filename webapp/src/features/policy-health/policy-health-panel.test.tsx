import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PolicyHealthPanel } from "./policy-health-panel";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

function policyHealthPayload() {
  const okCheck = { status: "ok", reference: "default" };
  return {
    status: "ok",
    summary: {
      total: 1,
      ok: 1,
      warning: 0,
      error: 0,
    },
    templates: [
      {
        template_id: "tpl-1",
        template_code: "mailbox",
        template_name: "Mail box",
        version: "1.0.0",
        status: "published",
        owner: "support",
        health_status: "ok",
        health_score: 100,
        conflict_count: 0,
        issue_count: 0,
        issues_by_severity: {
          critical: 0,
          error: 0,
          warning: 0,
          info: 0,
        },
        checks: {
          routing: okCheck,
          sla: okCheck,
          ola: okCheck,
          approval: okCheck,
          closure: okCheck,
          visibility: okCheck,
          notification: okCheck,
          diagnostic: okCheck,
          reporting: okCheck,
        },
        issues: [],
        last_checked_at: "2026-05-20T09:00:00+05:00",
      },
    ],
  };
}

function renderPanel(initialEntry: string) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <PolicyHealthPanel />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("PolicyHealthPanel", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("sends service and offering query context as top-level simulation fields", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === "/api/web/admin/helpdesk/policy-health" && !init?.method) {
        return jsonResponse(policyHealthPayload());
      }
      if (url === "/api/web/admin/helpdesk/policy-health/simulate" && init?.method === "POST") {
        return jsonResponse({
          template_code: "mailbox",
          routing: {},
          priority: {},
          sla: {},
          ola: {},
          approval: {},
          closure: {},
          visibility: {},
          diagnostic: {},
          warnings: [],
          would_create_ticket: false,
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });

    renderPanel("/app/admin/policy-health?service=mail&offering=mail.new_box&template=mailbox");

    await screen.findAllByText("mailbox");
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/admin/helpdesk/policy-health/simulate",
        expect.objectContaining({ method: "POST" }),
      );
    });
    const simulateCall = fetchMock.mock.calls.find(([url]) => String(url) === "/api/web/admin/helpdesk/policy-health/simulate");
    const body = JSON.parse(String(simulateCall?.[1]?.body));
    expect(body).toMatchObject({
      template_code: "mailbox",
      service_code: "mail",
      offering_code: "new_box",
      offering_full_code: "mail.new_box",
    });
  });
});
