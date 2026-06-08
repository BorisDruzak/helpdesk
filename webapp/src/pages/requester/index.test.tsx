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
  it("opens owned ticket detail and sends an authenticated requester message", async () => {
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
          },
        });
      }
      if (url === "/api/web/requester/tickets/T-42/message") {
        return jsonResponse({ status: "success", data: { message_id: "m-42", event_id: 12 } });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    render(<RequesterWorkspacePage />);

    await screen.findByText("Owned ticket");
    fireEvent.click(screen.getByText("Owned ticket"));

    await screen.findByText("Owned ticket detail");
    fireEvent.change(screen.getByLabelText("Requester message"), {
      target: { value: "Here is the requested context" },
    });
    fireEvent.click(screen.getByLabelText("Send requester message"));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/requester/tickets/T-42/message",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ text: "Here is the requested context" }),
        }),
      );
    });
  });
});
