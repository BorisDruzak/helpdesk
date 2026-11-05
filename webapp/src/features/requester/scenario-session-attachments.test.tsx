import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioSession } from "./scenario-session";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); sessionStorage.clear(); });
const image = { asset_id: "image", name: "screen.png", mime_type: "image/png", size_bytes: 20, url: "/api/web/request-scenario-assets/image/download" };
const document = { ...image, asset_id: "document", name: "notes.txt", mime_type: "text/plain", url: "/api/web/request-scenario-assets/document/download" };
const step = { id: "session", revision: 1, state: "active", back_targets: [], block: { id: "question", kind: "form_page", title: "Опишите проблему", fields: [{ key: "details", type: "textarea", label: "Описание", value: "" }] } };
function response(data: unknown) { return new Response(JSON.stringify({ status: "success", data }), { headers: { "content-type": "application/json" } }); }
function mount(offering = "it.problem") { return render(<MemoryRouter><ScenarioSession offering={offering} /></MemoryRouter>); }

it("uploads image and ordinary file serially, keeps text, blocks continue until completion and sends scalar answers unchanged", async () => {
  let finish!: (value: Response) => void;
  const fetcher = vi.fn(async (url: string, options?: RequestInit): Promise<Response> => {
    if (url.endsWith("/attachments")) {
      const file = (options?.body as FormData).get("file") as File;
      if (file.name === "screen.png") return new Promise(resolve => { finish = resolve; });
      return response(document);
    }
    return response(step);
  });
  vi.stubGlobal("fetch", fetcher); mount();
  fireEvent.change(await screen.findByLabelText("Описание"), { target: { value: "Текст остаётся" } });
  fireEvent.change(screen.getByLabelText("Прикрепить скриншоты или файлы"), { target: { files: [new File(["png"], "screen.png", { type: "image/png" }), new File(["hello"], "notes.txt", { type: "text/plain" })] } });
  await waitFor(() => expect(fetcher.mock.calls.filter(([url]) => url.endsWith("/attachments"))).toHaveLength(1));
  expect(screen.getByRole("button", { name: "Продолжить" })).toBeDisabled();
  expect(screen.getByLabelText("Описание")).toBeEnabled();
  fireEvent.change(screen.getByLabelText("Описание"), { target: { value: "Текст остаётся и дополняется" } });
  await act(async () => finish(response(image)));
  await screen.findByRole("link", { name: "notes.txt" });
  expect(screen.getByLabelText("Описание")).toHaveValue("Текст остаётся и дополняется");
  expect(screen.getByRole("img", { name: "Миниатюра: screen.png" })).toHaveAttribute("src", image.url);
  fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));
  await waitFor(() => expect(fetcher.mock.calls.some(([url]) => url.endsWith("/answer"))).toBe(true));
  const upload = fetcher.mock.calls.find(([url]) => url.endsWith("/attachments"))![1]!.body as FormData;
  expect(upload.get("field_key")).toBe("details"); expect(upload.get("expected_block_id")).toBe("question"); expect(upload.get("revision")).toBe("1"); expect(JSON.parse(String(upload.get("answers")))).toEqual({ details: "Текст остаётся" });
  const answer = fetcher.mock.calls.find(([url]) => url.endsWith("/answer"))![1]!.body;
  expect(JSON.parse(String(answer)).answers).toEqual({ details: "Текст остаётся и дополняется" });
});

it("resumes dynamic visibility preview with the latest text after uploads finish", async () => {
  let finish!: (value: Response) => void;
  const dynamic = { ...step, block: { ...step.block, has_dynamic_fields: true } };
  const fetcher = vi.fn(async (url: string, _options?: RequestInit): Promise<Response> => {
    if (url.endsWith("/attachments")) return new Promise(resolve => { finish = resolve; });
    return response(dynamic);
  });
  vi.stubGlobal("fetch", fetcher); mount();
  fireEvent.change(await screen.findByLabelText("Прикрепить скриншоты или файлы"), { target: { files: [new File(["png"], "screen.png", { type: "image/png" })] } });
  fireEvent.change(screen.getByLabelText("Описание"), { target: { value: "Вставленный текст" } });
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 200)); });
  expect(fetcher.mock.calls.some(([url]) => url.endsWith("/step-preview"))).toBe(false);
  await act(async () => finish(response(image)));
  await waitFor(() => expect(fetcher.mock.calls.some(([url]) => url.endsWith("/step-preview"))).toBe(true));
  const preview = fetcher.mock.calls.find(([url]) => url.endsWith("/step-preview"))!;
  expect(JSON.parse(String(preview[1]?.body)).answers).toEqual({ details: "Вставленный текст" });
  expect(screen.getByLabelText("Описание")).toHaveValue("Вставленный текст");
});

it("removes a persisted supplementary file through the session API without erasing text", async () => {
  const fetcher = vi.fn(async (_url: string, options?: RequestInit) => response(options?.method === "DELETE" ? { removed: true } : { ...step, block: { ...step.block, fields: [{ ...step.block.fields[0], value: "Сохранённый ответ", answer_attachments: [document] }] } }));
  vi.stubGlobal("fetch", fetcher); mount();
  fireEvent.click(await screen.findByRole("button", { name: "Убрать вложение notes.txt" }));
  await waitFor(() => expect(screen.queryByRole("link", { name: "notes.txt" })).not.toBeInTheDocument());
  expect(screen.getByLabelText("Описание")).toHaveValue("Сохранённый ответ");
  const removal = fetcher.mock.calls.find(([, options]) => options?.method === "DELETE")!;
  expect(removal[0]).toBe("/api/web/requester/request-scenarios/sessions/session/attachments/document");
  expect(JSON.parse(String(removal[1]?.body))).toEqual({ expected_block_id: "question", revision: 1 });
});

it("ignores and aborts an upload completed after the offering context changes", async () => {
  let finish!: (value: Response) => void;
  let uploadSignal: AbortSignal | null = null;
  const fetcher = vi.fn(async (url: string, options?: RequestInit): Promise<Response> => {
    if (url.endsWith("/attachments")) { uploadSignal = options?.signal as AbortSignal; return new Promise(resolve => { finish = resolve; }); }
    return response(step);
  });
  vi.stubGlobal("fetch", fetcher);
  const view = mount();
  fireEvent.change(await screen.findByLabelText("Прикрепить скриншоты или файлы"), { target: { files: [new File(["file"], "notes.txt")] } });
  view.rerender(<MemoryRouter><ScenarioSession offering="it.other" /></MemoryRouter>);
  await screen.findByRole("heading", { name: "Опишите проблему" });
  await act(async () => finish(response(document)));
  expect(uploadSignal!.aborted).toBe(true);
  expect(screen.queryByRole("link", { name: "notes.txt" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Продолжить" })).toBeEnabled();
});

it("retains successful files when a later file fails and allows retry without altering the answer", async () => {
  const fetcher = vi.fn(async (url: string, options?: RequestInit): Promise<Response> => {
    if (url.endsWith("/attachments")) return (options?.body as FormData).get("file") instanceof File && ((options?.body as FormData).get("file") as File).name === "screen.png" ? response(image) : new Response(JSON.stringify({ status: "error", error_code: "FILE_REJECTED" }), { status: 400 });
    return response(step);
  });
  vi.stubGlobal("fetch", fetcher); mount();
  fireEvent.change(await screen.findByLabelText("Описание"), { target: { value: "Сохранить текст" } });
  fireEvent.change(screen.getByLabelText("Прикрепить скриншоты или файлы"), { target: { files: [new File(["png"], "screen.png", { type: "image/png" }), new File(["file"], "notes.txt")] } });
  await screen.findByRole("alert");
  expect(screen.getByRole("img", { name: "Миниатюра: screen.png" })).toBeVisible();
  expect(screen.getByLabelText("Описание")).toHaveValue("Сохранить текст");
  expect(screen.getByRole("button", { name: "Продолжить" })).toBeEnabled();
});
