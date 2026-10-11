import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioSession } from "./scenario-session";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); sessionStorage.clear(); });

it("previews processing before submitting only the session revision and confirmation", async () => {
  const step = { id: "session", revision: 3, state: "active", back_targets: [], block: { id: "submit", kind: "submit_ticket", title: "Отправка" } };
  const fetchMock = vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith("/ticket-preview")) {
      expect(JSON.parse(String(options?.body))).toEqual({ revision: 3 });
      return response({ ok: true, approval: { text: "Согласование не требуется" }, expected_resolution: "до 4 ч", blockers: [], warnings: [] });
    }
    if (url.endsWith("/submit")) {
      expect(JSON.parse(String(options?.body))).toEqual({ revision: 3, confirm: true });
      return response({ ...step, revision: 4, state: "ticket_created", linked_ticket_id: "ticket-id" });
    }
    return response(step);
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<ScenarioSession offering="workplace.printer" />);
  fireEvent.click(await screen.findByRole("button", { name: "Проверить обработку" }));
  await screen.findByText("до 4 ч");
  fireEvent.click(screen.getByRole("button", { name: "Создать обращение" }));
  expect(await screen.findByRole("link", { name: "Открыть обращение" })).toHaveAttribute("href", "/app/requester/tickets/ticket-id");
  expect(screen.queryByRole("button", { name: "Создать обращение" })).not.toBeInTheDocument();
});

it("keeps ticket creation blocked when canonical preview has blockers", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => response(url.endsWith("/ticket-preview")
    ? { ok: false, blockers: ["Маршрут недоступен"], warnings: [] }
    : { id: "session", revision: 3, state: "active", back_targets: [], block: { id: "submit", kind: "submit_ticket", title: "Отправка" } })));
  render(<ScenarioSession offering="workplace.printer" />);
  fireEvent.click(await screen.findByRole("button", { name: "Проверить обработку" }));
  await screen.findByText("Маршрут недоступен");
  expect(screen.queryByRole("button", { name: "Создать обращение" })).not.toBeInTheDocument();
});

it.each(["", "owned-computer"])("uses the selected computer context in preview and submit (%s)", async deviceId => {
  const step = { id: "session", revision: 3, state: "active", back_targets: [], block: { id: "submit", kind: "submit_ticket", title: "Отправка" } };
  const context = deviceId ? { device_id: deviceId } : { device_scope: "none" };
  vi.stubGlobal("fetch", vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith("/ticket-preview")) {
      expect(JSON.parse(String(options?.body))).toEqual({ revision: 3, ...context });
      return response({ ok: true, blockers: [], warnings: [] });
    }
    if (url.endsWith("/submit")) {
      expect(JSON.parse(String(options?.body))).toEqual({ revision: 3, confirm: true, ...context });
      return response({ ...step, state: "ticket_created", linked_ticket_id: "ticket" });
    }
    return response(step);
  }));
  render(<ScenarioSession offering="workplace.printer" deviceId={deviceId} />);
  fireEvent.click(await screen.findByRole("button", { name: "Проверить обработку" }));
  fireEvent.click(await screen.findByRole("button", { name: "Создать обращение" }));
  await screen.findByRole("link", { name: "Открыть обращение" });
});

function response(data: unknown, status = 200) {
  return new Response(JSON.stringify({ status: "success", data }), { status, headers: { "Content-Type": "application/json" } });
}

it("renders only the server step and sends typed answer with revision", async () => {
  const step = { id: "session", revision: 1, state: "active", back_targets: [],
    block: { id: "question", kind: "form_page", title: "Проблема", fields: [
      { key: "summary", type: "text", label: "Описание", required: true, value: null },
    ] } };
  const fetchMock = vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith("/answer")) {
      expect(JSON.parse(String(options?.body))).toEqual({ expected_block_id: "question", revision: 1, answers: { summary: "Не печатает" } });
      return response({ ...step, revision: 2, state: "completed_self_service", block: { id: "done", kind: "finish", title: "Решено", message: "Проблема решена" } });
    }
    return response(step);
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<ScenarioSession offering="workplace.printer" />);
  await screen.findByRole("heading", { name: "Проблема" });
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Не печатает" } });
  fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));
  await screen.findByText("Проблема решена");
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
});

it("reveals a conditional required field before displaying answer errors", async () => {
  const field = { key: "summary", type: "text", label: "Описание", required: true };
  const step = { id: "session", revision: 1, state: "active", back_targets: [],
    block: { id: "question", kind: "form_page", title: "Проблема", has_dynamic_fields: true, fields: [field] } };
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url.endsWith("/step-preview")) return response({ ...step, block: { ...step.block, fields: [field, { key: "details", type: "text", label: "Подробности", required: true }] } });
    if (url.endsWith("/answer")) return new Response(JSON.stringify({ status: "error", error_code: "INVALID_ANSWERS", errors: { details: "Field is required" } }), { status: 400 });
    return response(step);
  }));
  render(<ScenarioSession offering="workplace.printer" />);
  await screen.findByRole("heading", { name: "Проблема" });
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "other" } });
  fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));
  await screen.findByText("Field is required");
  expect(screen.getAllByRole("textbox")).toHaveLength(2);
});

it.each([true, false])("supports required or optional acknowledgment (%s) and sends the explicit result", async required => {
  const fetchMock = vi.fn(async () => response({ id: "session", revision: 3, state: "active", back_targets: [],
    block: { id: "instruction", kind: "instruction", title: "Проверьте питание", content: { body: "Подключите кабель", format: "plain" }, acknowledgment_required: required } }));
  vi.stubGlobal("fetch", fetchMock);
  render(<ScenarioSession offering="workplace.printer" />);
  await screen.findByText("Подключите кабель");
  if (required) expect(screen.getByRole("button", { name: "Продолжить" })).toBeDisabled();
  else expect(screen.getByRole("button", { name: "Продолжить" })).toBeEnabled();
  fireEvent.click(screen.getByRole("checkbox", { name: "Инструкция выполнена" }));
  fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  const calls = fetchMock.mock.calls as unknown as [string, RequestInit][];
  expect(JSON.parse(String(calls[1][1].body))).toEqual({ expected_block_id: "instruction", revision: 3, current_result: "acknowledged" });
});

it("does not accept an old owner's pending command after owner changes", async () => {
  const initial = { id: "old", revision: 1, state: "active", back_targets: [], block: { id: "question", kind: "form_page", title: "Old owner", fields: [] } };
  let resolveAnswer!: (value: Response) => void;
  let starts = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url.endsWith("/answer")) return await new Promise<Response>(resolve => { resolveAnswer = resolve; });
    return response(++starts === 1 ? initial : { ...initial, id: "new", block: { ...initial.block, title: "New owner" } });
  }));
  const view = render(<ScenarioSession offering="workplace.printer" owner="old-user" />);
  await screen.findByRole("heading", { name: "Old owner" });
  fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));
  view.rerender(<ScenarioSession offering="workplace.printer" owner="new-user" />);
  await screen.findByRole("heading", { name: "New owner" });
  resolveAnswer(response({ ...initial, block: { ...initial.block, title: "Leaked old answer" } }));
  await waitFor(() => expect(screen.queryByText("Leaked old answer")).not.toBeInTheDocument());
  expect(screen.getByRole("heading", { name: "New owner" })).toBeInTheDocument();
});

it("preserves stored explicit unknown on resume", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => response({ id: "session", revision: 1, state: "active", back_targets: [],
    block: { id: "questions", kind: "form_page", title: "Question", fields: [{ key: "summary", label: "Summary", type: "text", required: true, allow_unknown: true, value: null }] } })));
  render(<ScenarioSession offering="workplace.printer" />);
  expect(await screen.findByRole("checkbox", { name: "Не знаю" })).toBeChecked();
});

it("allows restarting a stale opaque session handle", async () => {
  sessionStorage.setItem("pc_client.scenario.session:user:workplace.printer", "deleted");
  const fetchMock = vi.fn(async (url: string) => {
    if (url.endsWith("/deleted")) return new Response(JSON.stringify({ status: "error", error_code: "SESSION_NOT_FOUND" }), { status: 404 });
    return response({ id: "new", revision: 1, state: "active", back_targets: [], block: { id: "question", kind: "form_page", title: "New session", fields: [] } });
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<ScenarioSession offering="workplace.printer" owner="user" />);
  fireEvent.click(await screen.findByRole("button", { name: "Начать заново" }));
  await screen.findByRole("heading", { name: "New session" });
  expect(sessionStorage.getItem("pc_client.scenario.session:user:workplace.printer")).toBe("new");
});

it("ignores a pending preview after explicit unknown changes", async () => {
  const step = { id: "session", revision: 1, state: "active", back_targets: [], block: { id: "questions", kind: "form_page", title: "Question", has_dynamic_fields: true, fields: [{ key: "summary", label: "Summary", type: "text", allow_unknown: true }] } };
  let resolvePreview!: (value: Response) => void;
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url.endsWith("/step-preview")) return await new Promise<Response>(resolve => { resolvePreview = resolve; });
    return response(step);
  }));
  render(<ScenarioSession offering="workplace.printer" />);
  const textbox = await screen.findByRole("textbox");
  fireEvent.change(textbox, { target: { value: "old" } });
  fireEvent.blur(textbox);
  fireEvent.click(screen.getByRole("checkbox", { name: "Не знаю" }));
  resolvePreview(response({ ...step, block: { ...step.block, fields: [] } }));
  await waitFor(() => expect(screen.getByRole("checkbox", { name: "Не знаю" })).toBeChecked());
});

it("shows human summary labels instead of stored entity identifiers", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => response({ id: "session", revision: 2, state: "active", back_targets: [], block: {
    id: "review", kind: "review", title: "Проверьте ответы", answers: [{ key: "computer", label: "Компьютер", type: "device_picker", value: "opaque-device-id", display_value: "Рабочий компьютер" }],
  } })));
  render(<ScenarioSession offering="workplace.printer" />);
  await screen.findByText("Рабочий компьютер");
  expect(screen.queryByText("opaque-device-id")).not.toBeInTheDocument();
});
