import { QueryClient, QueryClientProvider, focusManager } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { useRequesterBootstrapQuery } from "./queries";

afterEach(() => { focusManager.setFocused(undefined); vi.useRealTimers(); vi.unstubAllGlobals(); });

it("stops automatically retrying and polling a denied bootstrap", async () => {
  vi.useFakeTimers();
  focusManager.setFocused(true);
  const fetchMock = vi.fn(async () => new Response(JSON.stringify({ status: "error", error_code: "FORBIDDEN" }),
    { status: 403, headers: { "Content-Type": "application/json" } }));
  vi.stubGlobal("fetch", fetchMock);
  const client = new QueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  const hook = renderHook(useRequesterBootstrapQuery, { wrapper });
  try {
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(hook.result.current.isError).toBe(true);
    await act(async () => { await vi.advanceTimersByTimeAsync(30_000); });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  } finally { hook.unmount(); client.clear(); }
});
