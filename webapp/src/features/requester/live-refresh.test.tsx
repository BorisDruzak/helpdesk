import { QueryClient, QueryClientProvider, focusManager } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useRequesterTicketDetailQuery, useRequesterTicketsQuery } from "./queries";

let status = "in_progress";
let message = "Первое сообщение";
vi.mock("./api", () => ({
  fetchRequesterTickets: async () => [{ ticket_id: "ticket-1", ticket_code: "T-1", status }],
  fetchRequesterTicket: async () => ({ ticket: { ticket_id: "ticket-1", ticket_code: "T-1", status }, messages: [{ text: message }] }),
}));

afterEach(() => { focusManager.setFocused(undefined); vi.useRealTimers(); });

describe("requester external updates", () => {
  it("receives operator messages and status without a requester mutation or reload", async () => {
    vi.useFakeTimers();
    focusManager.setFocused(true);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } } });
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
    const hook = renderHook(() => ({ list: useRequesterTicketsQuery(), detail: useRequesterTicketDetailQuery("T-1") }), { wrapper });
    try {
      await act(async () => { await vi.advanceTimersByTimeAsync(1); });
      expect(hook.result.current.detail.data?.ticket.status).toBe("in_progress");
      status = "waiting_on_user";
      message = "Оператор ждёт ваш ответ";
      await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
      expect(hook.result.current.detail.data?.messages?.[0]?.text).toBe(message);
      expect(hook.result.current.detail.data?.ticket.status).toBe(status);
      expect(hook.result.current.list.data?.[0].status).toBe(status);
    } finally { hook.unmount(); client.clear(); status = "in_progress"; message = "Первое сообщение"; }
  });
});
