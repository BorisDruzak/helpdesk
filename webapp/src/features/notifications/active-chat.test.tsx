import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { useActiveChatNotifications, visibleChatTicket } from "./use-active-chat-notifications";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it("requires a loaded conversation, focus, visibility and no modal", () => {
  const marker = render(<section data-helpdesk-active-chat="t77" />);
  vi.spyOn(document, "hasFocus").mockReturnValue(true);
  vi.spyOn(document, "visibilityState", "get").mockReturnValue("visible");
  expect(visibleChatTicket()).toBe("t77");
  vi.mocked(document.hasFocus).mockReturnValue(false);
  expect(visibleChatTicket()).toBeNull();
  vi.mocked(document.hasFocus).mockReturnValue(true);
  vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
  expect(visibleChatTicket()).toBeNull();
  vi.spyOn(document, "visibilityState", "get").mockReturnValue("visible");
  const modal = render(<dialog open />);
  expect(visibleChatTicket()).toBeNull();
  modal.unmount();
  const resolution = render(<section role="dialog" aria-modal="true" />);
  expect(visibleChatTicket()).toBeNull();
  resolution.unmount(); marker.unmount();
  expect(visibleChatTicket()).toBeNull();
});

function Probe() { useActiveChatNotifications("employee"); return <section data-helpdesk-active-chat="t77" />; }

it("reads only the viewed ticket without push opt-in and checks the actor on worker probes", async () => {
  vi.spyOn(document, "hasFocus").mockReturnValue(true);
  vi.spyOn(document, "visibilityState", "get").mockReturnValue("visible");
  const serviceWorker = new EventTarget();
  vi.stubGlobal("navigator", { serviceWorker });
  const fetch = vi.fn(async () => Response.json({ status: "ok", updated: 0 }));
  vi.stubGlobal("fetch", fetch);
  const client = new QueryClient();
  const view = render(<MemoryRouter initialEntries={["/app/requester/tickets/t77"]}><QueryClientProvider client={client}><Probe /></QueryClientProvider></MemoryRouter>);
  await waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/web/notifications/read_ticket", expect.objectContaining({ body: JSON.stringify({ ticket_id: "t77", expected_actor_id: "employee" }) })));
  for (const [actor, ticket, expected] of [["employee", "t77", true], ["other", "t77", false], ["employee", "t78", false]] as const) {
    const reply = vi.fn();
    const event = new MessageEvent("message", { data: { type: "helpdesk-is-chat-visible", actor_id: actor, ticket_id: ticket } });
    Object.defineProperty(event, "ports", { value: [{ postMessage: reply, close: vi.fn() }] });
    serviceWorker.dispatchEvent(event);
    expect(reply).toHaveBeenCalledWith({ active: expected });
  }
  view.unmount(); client.clear();
});
