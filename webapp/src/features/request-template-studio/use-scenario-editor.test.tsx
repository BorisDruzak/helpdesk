import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useScenarioEditor } from "./use-scenario-editor";

afterEach(() => vi.unstubAllGlobals());
it("cancels a pending open without leaving loading stuck or overwriting a new draft", async () => {
  let resolve!: (value: Response) => void;
  vi.stubGlobal("fetch", () => new Promise<Response>(done => { resolve = done; }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }) { return <QueryClientProvider client={client}>{children}</QueryClientProvider>; }
  const hook = renderHook(useScenarioEditor, { wrapper: Wrapper });
  let pending!: Promise<void>;
  act(() => { pending = hook.result.current.open("old"); });
  expect(hook.result.current.busy).toBe(true);
  act(() => hook.result.current.create());
  expect(hook.result.current.busy).toBe(false);
  const key = hook.result.current.definition!.scenario_key;
  await act(async () => { resolve(new Response(JSON.stringify({ status: "success", data: { scenario: { id: "old" }, draft: { revision: 1, definition: { scenario_key: "old" } } } }), { headers: { "content-type": "application/json" } })); await pending; });
  expect(hook.result.current.definition?.scenario_key).toBe(key);
  expect(hook.result.current.detail).toBeNull();
  expect(hook.result.current.busy).toBe(false);
});
