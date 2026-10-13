import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useScenarioEditor } from "./use-scenario-editor";

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });
it("does not mark a round-trip definition dirty when only object key order changes", () => {
  const client = new QueryClient();
  function Wrapper({ children }: { children: ReactNode }) { return <QueryClientProvider client={client}>{children}</QueryClientProvider>; }
  const hook = renderHook(useScenarioEditor, { wrapper: Wrapper });
  act(() => hook.result.current.create());
  const definition = hook.result.current.definition!;
  act(() => hook.result.current.accept({ scenario: { id: "s1" }, draft: { revision: 1, definition } } as Parameters<typeof hook.result.current.accept>[0]));
  act(() => hook.result.current.change(Object.fromEntries(Object.entries(definition).reverse()) as typeof definition));
  expect(hook.result.current.dirty).toBe(false);
});
it("merges server bindings into edits made during first creation and saves the next revision", async () => {
  let resolve!: (value: Response) => void;
  const fetcher = vi.fn((_url: unknown, init?: RequestInit) => init?.method === "POST"
    ? new Promise<Response>(done => { resolve = done; })
    : Promise.resolve(new Response(JSON.stringify({ status: "success", data: { scenario: { id: "s1" }, draft: { revision: 2, definition: JSON.parse(String(init?.body)).definition } } }), { headers: { "content-type": "application/json" } })));
  vi.stubGlobal("fetch", fetcher);
  const client = new QueryClient();
  function Wrapper({ children }: { children: ReactNode }) { return <QueryClientProvider client={client}>{children}</QueryClientProvider>; }
  const hook = renderHook(useScenarioEditor, { wrapper: Wrapper });
  act(() => hook.result.current.create());
  const snapshot = hook.result.current.definition!;
  let saving!: Promise<unknown>;
  act(() => { saving = hook.result.current.save.mutateAsync(); });
  await act(async () => { await Promise.resolve(); });
  act(() => hook.result.current.change({ ...snapshot, title: "Edited while saving" }));
  const bound = { ...snapshot, schema_version: 2 as const, publish_offering: true, offering_full_code: "it.generated", process_binding: { request_template_key: "printer" } };
  await act(async () => { resolve(new Response(JSON.stringify({ status: "success", data: { scenario: { id: "s1" }, draft: { revision: 1, definition: bound } } }), { headers: { "content-type": "application/json" } })); await saving; });
  expect(hook.result.current.definition).toMatchObject({ title: "Edited while saving", publish_offering: true, schema_version: 2, offering_full_code: "it.generated", process_binding: { request_template_key: "printer" } });
  await act(async () => { await hook.result.current.save.mutateAsync(); });
  expect(JSON.parse(String(fetcher.mock.calls[1][1]?.body))).toMatchObject({ revision: 1, definition: { title: "Edited while saving", offering_full_code: "it.generated" } });
  expect(hook.result.current.dirty).toBe(false);
});
it("debounces autosave and sends the last local edit with the known server revision", async () => {
  vi.useFakeTimers();
  const fetcher = vi.fn(async (_url: unknown, init?: RequestInit) => new Response(JSON.stringify({ status: "success", data: { scenario: { id: "s1" }, draft: { revision: 8, definition: JSON.parse(String(init?.body)).definition } } }), { headers: { "content-type": "application/json" } }));
  vi.stubGlobal("fetch", fetcher);
  function Wrapper({ children }: { children: ReactNode }) { return <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>; }
  const hook = renderHook(() => useScenarioEditor(true), { wrapper: Wrapper });
  act(() => hook.result.current.create());
  const definition = { ...hook.result.current.definition!, offering_full_code: "it.print", service_code: "it" };
  act(() => hook.result.current.accept({ scenario: { id: "s1" }, draft: { revision: 7, definition } } as Parameters<typeof hook.result.current.accept>[0]));
  act(() => hook.result.current.change({ ...definition, title: "First" }));
  await act(async () => { await vi.advanceTimersByTimeAsync(900); });
  act(() => hook.result.current.change({ ...definition, title: "Last" }));
  await act(async () => { await vi.advanceTimersByTimeAsync(900); });
  expect(fetcher).not.toHaveBeenCalled();
  await act(async () => { await vi.advanceTimersByTimeAsync(300); });
  expect(JSON.parse(String(fetcher.mock.calls[0][1]?.body))).toMatchObject({ revision: 7, definition: { title: "Last" } });
  expect(hook.result.current.dirty).toBe(false);
});
it("preserves newer local edits when an older save completes", async () => {
  let resolve!: (value: Response) => void;
  vi.stubGlobal("fetch", () => new Promise<Response>(done => { resolve = done; }));
  const client = new QueryClient();
  function Wrapper({ children }: { children: ReactNode }) { return <QueryClientProvider client={client}>{children}</QueryClientProvider>; }
  const hook = renderHook(useScenarioEditor, { wrapper: Wrapper });
  act(() => hook.result.current.create());
  const snapshot = hook.result.current.definition!;
  let saving!: Promise<unknown>;
  act(() => { saving = hook.result.current.save.mutateAsync(); });
  await act(async () => { await Promise.resolve(); });
  act(() => hook.result.current.change({ ...snapshot, title: "Newer edit" }));
  await act(async () => { resolve(new Response(JSON.stringify({ status: "success", data: { scenario: { id: "s1" }, draft: { revision: 1, definition: snapshot } } }), { headers: { "content-type": "application/json" } })); await saving; });
  expect(hook.result.current.definition?.title).toBe("Newer edit");
  expect(hook.result.current.detail?.draft.revision).toBe(1);
  expect(hook.result.current.dirty).toBe(true);
});
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
