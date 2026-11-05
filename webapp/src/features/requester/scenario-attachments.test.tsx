import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioStepContent } from "./scenario-step-content";
import { ScenarioFieldEditor } from "../request-template-studio/scenario-field-editor";
import { ScenarioAuthorAttachmentProvider } from "../request-template-studio/scenario-author-attachments";
import { ScenarioAttachmentEditor } from "./scenario-attachments";
import type { ScenarioDraftDefinition } from "../request-template-studio/scenario-contract";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const image = { asset_id: "image", name: "screen.png", mime_type: "image/png", size_bytes: 20, url: "/api/web/request-scenario-assets/image/download" };
const document = { ...image, asset_id: "document", name: "report.pdf", mime_type: "application/pdf", url: "/api/web/request-scenario-assets/document/download" };
it("shows instruction images inline and supplementary files as downloads", () => {
  render(<ScenarioStepContent block={{ id: "i", kind: "instruction", title: "Помощь", content: { body: "Шаги", format: "plain", attachments: [image, document] } }} values={{}} acknowledged={false} onAcknowledged={vi.fn()} onValue={vi.fn()} />);
  expect(screen.getByRole("img", { name: "Миниатюра: screen.png" })).toHaveAttribute("src", image.url);
  expect(screen.getByRole("link", { name: "report.pdf" })).toHaveAttribute("href", document.url);
});
it("offers attachments alongside text field help without enabling the generic file field", () => {
  render(<ScenarioFieldEditor field={{ key: "details", label: "Описание", type: "textarea", help_attachments: [document] }} definition={{ scenario_key: "a", title: "A", service_code: "it", offering_full_code: "it.a", process_binding: { request_template_key: "a" } }} disabled={false} onChange={vi.fn()} />);
  expect(screen.getByRole("link", { name: "report.pdf" })).toBeVisible();
  expect(screen.getByRole("option", { name: /Вложение/ })).toBeDisabled();
  expect(screen.getByText(/Сохраните сценарий.*прикреп/)).toBeVisible();
});

it("merges a completed author upload into the current unsaved help text", async () => {
  let finish!: (value: Response) => void;
  vi.stubGlobal("fetch", vi.fn(() => new Promise(resolve => { finish = resolve; })));
  function Author() {
    const [definition, change] = useState<ScenarioDraftDefinition>({ scenario_key: "a", title: "A", service_code: "it", offering_full_code: "it.a", process_binding: { request_template_key: "a" }, blocks: [{ id: "q", kind: "form_page", title: "Вопрос", fields: [{ key: "details", type: "text", label: "Описание", help_text: "Начало" }] }] });
    const page = definition.blocks![0];
    if (page.kind !== "form_page") return null;
    return <ScenarioAuthorAttachmentProvider id="draft" definition={definition} onChange={change}><ScenarioFieldEditor field={page.fields[0]} definition={definition} disabled={false} onChange={field => change({ ...definition, blocks: [{ ...page, fields: [field] }] })} /></ScenarioAuthorAttachmentProvider>;
  }
  render(<Author />);
  fireEvent.change(screen.getByLabelText("Прикрепить скриншоты или файлы"), { target: { files: [new File(["file"], "report.pdf", { type: "application/pdf" })] } });
  fireEvent.change(screen.getByLabelText("Подсказка"), { target: { value: "Отредактированная подсказка" } });
  await act(async () => finish(new Response(JSON.stringify({ status: "success", data: document }), { headers: { "content-type": "application/json" } })));
  expect(screen.getByLabelText("Подсказка")).toHaveValue("Отредактированная подсказка");
  expect(screen.getByRole("link", { name: "report.pdf" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Убрать вложение report.pdf" }));
  await waitFor(() => expect(screen.queryByRole("link", { name: "report.pdf" })).not.toBeInTheDocument());
  expect(screen.getByLabelText("Подсказка")).toHaveValue("Отредактированная подсказка");
});

it("rejects oversized selections before uploading", () => {
  const upload = vi.fn();
  render(<ScenarioAttachmentEditor scope="size" onUpload={upload} />);
  const file = new File(["x"], "large.txt"); Object.defineProperty(file, "size", { value: 201 * 1024 * 1024 });
  fireEvent.change(screen.getByLabelText("Прикрепить скриншоты или файлы"), { target: { files: [file] } });
  expect(upload).not.toHaveBeenCalled(); expect(screen.getByRole("alert")).toHaveTextContent(/200/);
});

it("accepts native screenshot paste and local file drops while ignoring pasted HTML image URLs", async () => {
  const upload = vi.fn().mockResolvedValue(undefined);
  const { container } = render(<ScenarioAttachmentEditor scope="paste" onUpload={upload}><textarea aria-label="Текст" /></ScenarioAttachmentEditor>);
  const textarea = screen.getByLabelText("Текст");
  fireEvent.paste(textarea, { clipboardData: { items: [], files: [], getData: (type: string) => type === "text/html" ? '<img src="https://outside.invalid/tracker.png">' : "" } });
  expect(upload).not.toHaveBeenCalled();
  const screenshot = new File(["png"], "screen.png", { type: "image/png" });
  fireEvent.paste(textarea, { clipboardData: { items: [{ kind: "file", getAsFile: () => screenshot }], files: [screenshot], getData: () => "" } });
  await waitFor(() => expect(upload).toHaveBeenCalledTimes(1));
  await waitFor(() => expect(screen.getByRole("button", { name: "Прикрепить скриншоты или файлы" })).toBeEnabled());
  const file = new File(["text"], "notes.txt", { type: "text/plain" });
  fireEvent.drop(container.firstChild!, { dataTransfer: { types: ["Files"], files: [file], items: [{ kind: "file", getAsFile: () => file }] } });
  await waitFor(() => expect(upload).toHaveBeenCalledTimes(2));
  expect(upload.mock.calls[1][0]).toBe(file);
});

it("never embeds external, query-bearing or SVG attachments as images", () => {
  render(<ScenarioStepContent block={{ id: "i", kind: "instruction", title: "Помощь", content: { body: "Шаги", format: "plain", attachments: [
    { ...image, asset_id: "external", url: "https://outside.invalid/screen.png" },
    { ...image, asset_id: "query", url: `${image.url}?token=secret` },
    { ...image, asset_id: "svg", name: "diagram.svg", mime_type: "image/svg+xml", url: "/api/web/request-scenario-assets/svg/download" },
  ] } }} values={{}} acknowledged={false} onAcknowledged={vi.fn()} onValue={vi.fn()} />);
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "diagram.svg" })).toHaveAttribute("download", "diagram.svg");
});
