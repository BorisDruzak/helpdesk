import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useScenarioEditor } from "./use-scenario-editor";
import type { ScenarioDraftDefinition } from "./scenario-contract";

const sourceMaterial = { asset_id: "original", name: "guide.png", mime_type: "image/png", size_bytes: 20, url: "/api/web/request-scenario-assets/original/download" };
const copiedMaterial = { ...sourceMaterial, asset_id: "copied", url: "/api/web/request-scenario-assets/copied/download" };
const sourceDefinition: ScenarioDraftDefinition = { schema_version: 3, scenario_key: "source", title: "Источник", service_code: "it", offering_full_code: "it.source", process_binding: { request_template_key: "source" }, blocks: [
  { id: "help", kind: "instruction", title: "Помощь", content: { body: "Исходный текст", attachments: [sourceMaterial] } },
  { id: "form", kind: "form_page", title: "Вопрос", fields: [{ key: "details", type: "text", label: "Описание", help_attachments: [sourceMaterial] }] },
] };
function copyHook() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }) { return <QueryClientProvider client={client}>{children}</QueryClientProvider>; }
  const hook = renderHook(useScenarioEditor, { wrapper: Wrapper });
  act(() => hook.result.current.accept({ scenario: { id: "source-id" }, draft: { revision: 1, definition: sourceDefinition } } as Parameters<typeof hook.result.current.accept>[0]));
  act(() => hook.result.current.create(hook.result.current.definition!));
  return hook;
}

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });
it("reports the failed draft field and preserves the local definition", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ status: "error", error_code: "VALIDATION_ERROR", issues: [{ code: "string_too_long", path: "definition.blocks.0.instruction.title", message: "Сократите текст: не более 300 символов." }] }), { status: 400, headers: { "content-type": "application/json" } })));
  const hook = copyHook();
  const before = hook.result.current.definition;
  await act(async () => { await hook.result.current.save.mutateAsync().catch(() => {}); });
  expect(hook.result.current.error).toContain("Помощь");
  expect(hook.result.current.error).toContain("Название шага");
  expect(hook.result.current.error).toContain("не более 300 символов");
  expect(hook.result.current.definition).toBe(before);
  expect(hook.result.current.conflict).toBe(false);
});
it("does not call every HTTP 409 a revision conflict", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ status: "error", error_code: "CONSTRAINT_CONFLICT" }), { status: 409, headers: { "content-type": "application/json" } })));
  const hook = copyHook();
  await act(async () => { await hook.result.current.save.mutateAsync().catch(() => {}); });
  expect(hook.result.current.conflict).toBe(false);
  expect(hook.result.current.error).toContain("связи с каталогом");
});
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

it("retains copied materials and sends source provenance only for creation, including retry after a failure", async () => {
  let failed = false;
  const fetcher = vi.fn(async (_url: unknown, init?: RequestInit) => {
    const body = JSON.parse(String(init?.body));
    if (!failed) { failed = true; return new Response(JSON.stringify({ status: "error" }), { status: 503, headers: { "content-type": "application/json" } }); }
    return new Response(JSON.stringify({ status: "success", data: { scenario: { id: "copy-id" }, draft: { revision: 1, definition: body.definition }, asset_rebindings: { original: copiedMaterial } } }), { headers: { "content-type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetcher);
  const hook = copyHook();
  expect(hook.result.current.definition?.blocks).toEqual(sourceDefinition.blocks);
  expect(hook.result.current.definition).not.toHaveProperty("copy_source_id");
  await act(async () => { await expect(hook.result.current.save.mutateAsync()).rejects.toThrow(); });
  await act(async () => { await hook.result.current.save.mutateAsync(); });
  for (const [, options] of fetcher.mock.calls.slice(0, 2)) expect(JSON.parse(String(options?.body))).toMatchObject({ copy_source_id: "source-id", definition: { blocks: sourceDefinition.blocks } });
  await act(async () => { await hook.result.current.save.mutateAsync(); });
  expect(fetcher.mock.calls[2][1]?.method).toBe("PUT");
  expect(JSON.parse(String(fetcher.mock.calls[2][1]?.body))).not.toHaveProperty("copy_source_id");
});

it("merges copy asset rebindings into edits made while the first save is pending", async () => {
  let finish!: (response: Response) => void;
  vi.stubGlobal("fetch", vi.fn(() => new Promise(resolve => { finish = resolve; })));
  const hook = copyHook();
  const snapshot = hook.result.current.definition!;
  let pending!: Promise<unknown>;
  act(() => { pending = hook.result.current.save.mutateAsync(); });
  await act(async () => { await Promise.resolve(); });
  act(() => hook.result.current.change({ ...snapshot, blocks: snapshot.blocks?.map(block => block.kind === "instruction" ? { ...block, content: { ...block.content, body: "Новый локальный текст" } } : block) }));
  const bound = { ...snapshot, offering_full_code: "it.copy", process_binding: { request_template_key: "copy" } };
  await act(async () => { finish(new Response(JSON.stringify({ status: "success", data: { scenario: { id: "copy-id" }, draft: { revision: 1, definition: bound }, asset_rebindings: { original: copiedMaterial } } }), { headers: { "content-type": "application/json" } })); await pending; });
  expect(hook.result.current.definition?.blocks?.[0]).toMatchObject({ content: { body: "Новый локальный текст", attachments: [copiedMaterial] } });
  expect(hook.result.current.definition?.blocks?.[1]).toMatchObject({ fields: [{ help_attachments: [copiedMaterial] }] });
});

it.each(["blank", "import", "open"])("clears pending copy provenance when switching to %s", async action => {
  const fetcher = vi.fn(async (_url: unknown, init?: RequestInit) => new Response(JSON.stringify({ status: "success", data: { scenario: { id: "other-id" }, draft: { revision: 1, definition: init?.body ? JSON.parse(String(init.body)).definition : sourceDefinition } } }), { headers: { "content-type": "application/json" } }));
  vi.stubGlobal("fetch", fetcher);
  const hook = copyHook();
  if (action === "open") { await act(async () => { await hook.result.current.open("other-id"); }); act(() => hook.result.current.create()); }
  else act(() => action === "import" ? hook.result.current.create({ ...sourceDefinition, blocks: [] }, false) : hook.result.current.create());
  await act(async () => { await hook.result.current.save.mutateAsync(); });
  const request = fetcher.mock.calls.find(([, options]) => options?.method === "POST")!;
  expect(JSON.parse(String(request[1]?.body))).not.toHaveProperty("copy_source_id");
});
