import { StrictMode, type ReactNode } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { act, cleanup, fireEvent, render as renderComponent, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioSession } from "./scenario-session";

function TicketDestination() {
  const location = useLocation();
  return <h1>Открыто обращение: {location.pathname}</h1>;
}
function render(ui: ReactNode) {
  return renderComponent(ui, { wrapper: ({ children }) => <MemoryRouter><Routes>
    <Route path="/" element={children} />
    <Route path="/app/requester/tickets/:ticketId" element={<TicketDestination />} />
  </Routes></MemoryRouter> });
}

it("starts the selected entrance instead of resuming another entrance", async () => {
  sessionStorage.setItem("pc_client.scenario.session:user:workplace.printer", "legacy-session");
  const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "success", data: { id: "new-session", revision: 1, state: "active", back_targets: [], block: { id: "paper", kind: "instruction", title: "Paper" } } }), { headers: { "content-type": "application/json" } }));
  vi.stubGlobal("fetch", fetcher);
  render(<ScenarioSession offering="workplace.printer" owner="user" entryPointKey="paper" />);
  await screen.findByText("Paper");
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({ offering_full_code: "workplace.printer", entry_point_key: "paper" });
});

afterEach(() => { cleanup(); vi.unstubAllGlobals(); sessionStorage.clear(); });

it("automatically previews processing and opens the ticket after one explicit submission", async () => {
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
  await screen.findByText("до 4 ч");
  expect(screen.queryByRole("button", { name: "Проверить обработку" })).not.toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([url]) => url.endsWith("/submit"))).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "Создать обращение" }));
  await screen.findByRole("heading", { name: "Открыто обращение: /app/requester/tickets/ticket-id" });
  expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/submit"))).toHaveLength(1);
  expect(screen.queryByRole("button", { name: "Создать обращение" })).not.toBeInTheDocument();
});

it("keeps ticket creation blocked when canonical preview has blockers", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => response(url.endsWith("/ticket-preview")
    ? { ok: false, blockers: ["Маршрут недоступен"], warnings: [] }
    : { id: "session", revision: 3, state: "active", back_targets: [], block: { id: "submit", kind: "submit_ticket", title: "Отправка" } })));
  render(<ScenarioSession offering="workplace.printer" />);
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
  fireEvent.click(await screen.findByRole("button", { name: "Создать обращение" }));
  await screen.findByRole("heading", { name: "Открыто обращение: /app/requester/tickets/ticket" });
});

function response(data: unknown, status = 200) {
  return new Response(JSON.stringify({ status: "success", data }), { status, headers: { "Content-Type": "application/json" } });
}

it.each([undefined, false, true])("offers instruction escape only when the server grants it (%s)", async allowed => {
  const step = { id: "session", revision: 2, state: "active", back_targets: [], block: {
    id: "instruction", kind: "instruction", title: "Проверьте питание", acknowledgment_required: true,
    can_request_ticket: allowed, content: { body: "Проверьте кабель", format: "plain" },
  } };
  const fetchMock = vi.fn(async (url: string, _options?: RequestInit) => response(url.endsWith("/advance")
    ? { ...step, revision: 3, block: { id: "review", kind: "review", title: "Проверьте ответы", answers: [] } }
    : step));
  vi.stubGlobal("fetch", fetchMock);
  render(<ScenarioSession offering="workplace.printer" />);
  await screen.findByRole("heading", { name: "Проверьте питание" });
  expect(screen.getByRole("button", { name: "Продолжить" })).toBeDisabled();
  const escape = screen.queryByRole("button", { name: "Нужна помощь поддержки" });
  if (!allowed) { expect(escape).not.toBeInTheDocument(); return; }
  fireEvent.click(escape!);
  await screen.findByRole("heading", { name: "Проверьте ответы" });
  const advances = fetchMock.mock.calls.filter(([url]) => url.endsWith("/advance"));
  expect(advances).toHaveLength(1);
  // Inspect outside mocked fetch so request error handling cannot swallow failures.
  expect(JSON.parse(String(advances[0]?.[1]?.body))).toEqual({ expected_block_id: "instruction", revision: 2, current_result: "request_ticket" });
  expect(fetchMock.mock.calls.some(([url]) => url.endsWith("/submit") || url.endsWith("/ticket-preview"))).toBe(false);
});

it("renders server-projected sections with human group names and unchanged fields", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => response({ id: "session", revision: 1, state: "active", back_targets: [], block: {
    id: "questions", kind: "form_page", title: "Что происходит", layout: "section", fields: [
      { key: "printer", type: "text", label: "Модель принтера", group: "printer_details", group_title: "Устройство" },
      { key: "issue", type: "textarea", label: "Описание проблемы", group: "problem_details", group_title: "Проблема" },
    ],
  } })));
  render(<ScenarioSession offering="workplace.printer" />);
  await screen.findByRole("group", { name: "Устройство" });
  expect(screen.getByRole("group", { name: "Проблема" })).toBeInTheDocument();
  expect(screen.getByRole("textbox", { name: /Модель принтера/ })).toBeInTheDocument();
  expect(screen.queryByText("printer_details")).not.toBeInTheDocument();
});

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

it("reactively reveals Other fields while typing another answer without blur or Continue and clears them on Known", async () => {
  const fields = [
    { key: "subject", type: "radio", label: "Область", value: "known", options: [{ value: "known", label: "Известная область" }, { value: "other", label: "Другая область" }] },
    { key: "description", type: "textarea", label: "Описание", value: "" },
  ];
  const extra = { key: "subject_other", type: "text", label: "Уточните другую область", required: true };
  const step = { id: "session", revision: 1, state: "active", back_targets: [], block: { id: "questions", kind: "form_page", title: "Вопросы", has_dynamic_fields: true, fields } };
  let resolveOld!: (response: Response) => void;
  const fetchMock = vi.fn(async (url: string, options?: RequestInit) => {
    if (!url.endsWith("/step-preview")) return response(step);
    const { answers } = JSON.parse(String(options?.body));
    if (answers.subject === "other" && !answers.description) return await new Promise<Response>(resolve => { resolveOld = resolve; });
    return response({ ...step, block: { ...step.block, fields: [...fields, ...(answers.subject === "other" ? [extra] : [])] } });
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<ScenarioSession offering="other" owner="user" />);
  const other = await screen.findByRole("radio", { name: "Другая область" });
  fireEvent.click(other);
  fireEvent.blur(other);
  fireEvent.change(screen.getByRole("textbox", { name: "Описание" }), { target: { value: "Проблема с рабочим профилем" } });
  const conditional = await screen.findByRole("textbox", { name: /Уточните другую область/ });
  fireEvent.change(conditional, { target: { value: "Служебная область" } });
  fireEvent.click(screen.getByRole("radio", { name: "Известная область" }));
  await waitFor(() => expect(screen.queryByRole("textbox", { name: /Уточните другую область/ })).not.toBeInTheDocument());
  fireEvent.change(screen.getByRole("textbox", { name: "Описание" }), { target: { value: "Известная проблема" } });
  await waitFor(() => {
    const requests = fetchMock.mock.calls.filter(([url]) => url.endsWith("/step-preview"));
    const last = JSON.parse(String(requests.at(-1)?.[1]?.body));
    expect(last.answers).toEqual({ subject: "known", description: "Известная проблема" });
  });
  await act(async () => { resolveOld(response({ ...step, block: { ...step.block, fields: [...fields, extra] } })); });
  expect(screen.queryByRole("textbox", { name: /Уточните другую область/ })).not.toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([url]) => url.endsWith("/answer"))).toBe(false);
});

it.each(["scheduled", "inflight"])("ignores an old owner's reactive conditional projection (%s)", async phase => {
  const initial = { id: "old-session", revision: 1, state: "active", back_targets: [], block: { id: "old-question", kind: "form_page", title: "Старые вопросы", has_dynamic_fields: true, fields: [{ key: "description", type: "textarea", label: "Описание" }] } };
  let resolveOld!: (response: Response) => void;
  let oldSignal: AbortSignal | undefined;
  const fetchMock = vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith("/step-preview")) {
      oldSignal = options?.signal as AbortSignal;
      return await new Promise<Response>(resolve => { resolveOld = resolve; });
    }
    const body = JSON.parse(String(options?.body));
    return response(body.offering_full_code === "new" ? { ...initial, id: "new-session", block: { id: "new-question", kind: "form_page", title: "Новые вопросы", fields: [] } } : initial);
  });
  vi.stubGlobal("fetch", fetchMock);
  const view = render(<ScenarioSession offering="old" owner="old-user" />);
  fireEvent.change(await screen.findByRole("textbox", { name: "Описание" }), { target: { value: "Старый ответ" } });
  if (phase === "inflight") await waitFor(() => expect(resolveOld).toBeDefined());
  view.rerender(<ScenarioSession offering="new" owner="new-user" />);
  await screen.findByRole("heading", { name: "Новые вопросы" });
  if (phase === "inflight") {
    expect(oldSignal?.aborted).toBe(true);
    await act(async () => { resolveOld(response({ ...initial, block: { ...initial.block, fields: [{ key: "old", type: "text", label: "Старое условное поле" }] } })); });
  } else {
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 220)); });
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith("/step-preview"))).toBe(false);
  }
  expect(screen.queryByRole("textbox", { name: "Старое условное поле" })).not.toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Новые вопросы" })).toBeInTheDocument();
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


const submitStep = { id: "session", revision: 3, state: "active", back_targets: [], block: { id: "submit", kind: "submit_ticket", title: "Отправка" } };

it("keeps the final preview and submission actions in normal flow after all answers", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => response(url.endsWith("/ticket-preview")
    ? { ok: true, blockers: [], warnings: [], expected_first_response: "до 2 ч", expected_resolution: "до 5 ч" }
    : { ...submitStep, back_targets: [{ id: "question", title: "Описание" }], block: { ...submitStep.block, answers: [{ key: "summary", label: "Проблема", type: "textarea", value: "Описание", display_value: "Полное описание проблемы" }] } })));
  render(<ScenarioSession offering="other" owner="user" />);
  await screen.findByRole("button", { name: "Создать обращение" });
  expect(screen.getByRole("group", { name: "Действия шага" })).not.toHaveClass("sticky");
  expect(screen.getByText("Полное описание проблемы")).toBeInTheDocument();
  expect(screen.getByText("Первый ответ: до 2 ч")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Вернуться: Описание" })).toBeInTheDocument();
});

it("keeps long question forms and five back controls in normal flow while sending the contact answer", async () => {
  const step = { id: "session", revision: 6, state: "active", back_targets: Array.from({ length: 5 }, (_, index) => ({ id: `back-${index}`, title: `Шаг ${index + 1}` })), block: { id: "contact", kind: "form_page", title: "Описание для поддержки", fields: [
    { key: "description", type: "textarea", label: "Описание", value: "", required: true },
    { key: "phone", type: "text", label: "Телефон", value: "", required: true },
  ] } };
  const fetchMock = vi.fn(async (url: string) => response(url.endsWith("/answer")
    ? { ...step, revision: 7, back_targets: [], block: { id: "review", kind: "review", title: "Проверьте контакт", answers: [] } }
    : step));
  vi.stubGlobal("fetch", fetchMock);
  render(<ScenarioSession offering="workplace.printer" owner="user" />);
  const phone = await screen.findByRole("textbox", { name: /Телефон/ });
  expect(screen.getByRole("group", { name: "Действия шага" })).not.toHaveClass("sticky");
  expect(screen.getAllByRole("button", { name: /Вернуться: Шаг/ })).toHaveLength(5);
  fireEvent.change(screen.getByRole("textbox", { name: /Описание/ }), { target: { value: "Не работает синхронизация профиля" } });
  fireEvent.change(phone, { target: { value: "222-33" } });
  fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));
  await screen.findByRole("heading", { name: "Проверьте контакт" });
  const answerCalls = fetchMock.mock.calls.filter(([url]) => url.endsWith("/answer")) as unknown as [string, RequestInit][];
  expect(answerCalls).toHaveLength(1);
  expect(JSON.parse(String(answerCalls[0][1].body))).toEqual({ expected_block_id: "contact", revision: 6, answers: { description: "Не работает синхронизация профиля", phone: "222-33" } });
});

it("starts a new request for the same entrance after acknowledged ticket creation", async () => {
  const key = "pc_client.scenario.session:user:other:entry:other";
  let created = false;
  const terminal = { ...submitStep, state: "ticket_created", linked_ticket_id: "first-ticket" };
  const fetchMock = vi.fn(async (url: string) => {
    if (url.endsWith("/ticket-preview")) return response({ ok: true, blockers: [], warnings: [] });
    if (url.endsWith("/submit")) { created = true; return response(terminal); }
    if (url.endsWith("/session")) return response(terminal);
    return response(created ? { ...submitStep, id: "next-session", block: { id: "question", kind: "form_page", title: "Новое обращение", fields: [] } } : submitStep);
  });
  vi.stubGlobal("fetch", fetchMock);
  const view = render(<ScenarioSession offering="other" owner="user" entryPointKey="other" />);
  fireEvent.click(await screen.findByRole("button", { name: "Создать обращение" }));
  await screen.findByRole("heading", { name: "Открыто обращение: /app/requester/tickets/first-ticket" });
  expect(sessionStorage.getItem(key)).toBeNull();
  view.unmount();
  render(<ScenarioSession offering="other" owner="user" entryPointKey="other" />);
  await screen.findByRole("heading", { name: "Новое обращение" });
  expect(sessionStorage.getItem(key)).toBe("next-session");
  expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/submit"))).toHaveLength(1);
  expect(fetchMock.mock.calls.filter(([url]) => url === "/api/web/requester/request-scenarios/sessions")).toHaveLength(2);
});

it("forgets an acknowledged self-service completion while preserving a different entrance", async () => {
  const key = "pc_client.scenario.session:user:other";
  sessionStorage.setItem(key, "self-service");
  sessionStorage.setItem(`${key}:entry:another`, "another-session");
  vi.stubGlobal("fetch", vi.fn(async () => response({ ...submitStep, id: "self-service", state: "completed_self_service", block: { id: "done", kind: "finish", title: "Проблема решена самостоятельно" } })));
  render(<ScenarioSession offering="other" owner="user" />);
  await screen.findByRole("heading", { name: "Проблема решена самостоятельно" });
  expect(sessionStorage.getItem(key)).toBeNull();
  expect(sessionStorage.getItem(`${key}:entry:another`)).toBe("another-session");
});

it("retries a blocked preview explicitly without submitting until it clears", async () => {
  let previews = 0;
  const fetchMock = vi.fn(async (url: string) => response(url.endsWith("/ticket-preview")
    ? { ok: ++previews > 1, blockers: previews === 1 ? ["Маршрут недоступен"] : [], warnings: [], expected_resolution: "до 4 ч" }
    : submitStep));
  vi.stubGlobal("fetch", fetchMock);
  render(<ScenarioSession offering="workplace.printer" />);
  await screen.findByText("Маршрут недоступен");
  expect(screen.queryByRole("button", { name: "Создать обращение" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Повторить обработку" }));
  await screen.findByRole("button", { name: "Создать обращение" });
  expect(screen.queryByText("Маршрут недоступен")).not.toBeInTheDocument();
  expect(previews).toBe(2);
  expect(fetchMock.mock.calls.some(([url]) => url.endsWith("/submit"))).toBe(false);
});

it("resumes a created session directly into its ticket without preview or submit", async () => {
  sessionStorage.setItem("pc_client.scenario.session:user:workplace.printer", "session");
  const fetchMock = vi.fn(async (_url: string) => response({ ...submitStep, state: "ticket_created", linked_ticket_id: "existing-ticket" }));
  vi.stubGlobal("fetch", fetchMock);
  render(<ScenarioSession offering="workplace.printer" owner="user" />);
  await screen.findByRole("heading", { name: "Открыто обращение: /app/requester/tickets/existing-ticket" });
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(fetchMock.mock.calls[0][0]).toBe("/api/web/requester/request-scenarios/sessions/session");
  expect(sessionStorage.getItem("pc_client.scenario.session:user:workplace.printer")).toBeNull();
});

it("shows processing and ignores duplicate clicks while submission is pending", async () => {
  let resolveSubmit!: (response: Response) => void;
  const fetchMock = vi.fn(async (url: string) => {
    if (url.endsWith("/ticket-preview")) return response({ ok: true, blockers: [], warnings: [] });
    if (url.endsWith("/submit")) return await new Promise<Response>(resolve => { resolveSubmit = resolve; });
    return response(submitStep);
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<StrictMode><ScenarioSession offering="workplace.printer" /></StrictMode>);
  const submit = await screen.findByRole("button", { name: "Создать обращение" });
  act(() => { submit.click(); submit.click(); });
  expect(await screen.findByRole("status")).toHaveTextContent("Создаём обращение");
  expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/submit"))).toHaveLength(1);
  expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/ticket-preview"))).toHaveLength(1);
  await act(async () => { resolveSubmit(response({ ...submitStep, state: "ticket_created", linked_ticket_id: "ticket" })); });
  await screen.findByRole("heading", { name: "Открыто обращение: /app/requester/tickets/ticket" });
});

it.each(["preview", "terminal-preview", "submit"])("aborts and ignores an old owner's pending %s result", async phase => {
  let resolvePending!: (response: Response) => void;
  let pendingSignal: AbortSignal | undefined;
  const fetchMock = vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith(phase === "submit" ? "/submit" : "/ticket-preview")) {
      pendingSignal = options?.signal as AbortSignal;
      return await new Promise<Response>(resolve => { resolvePending = resolve; });
    }
    if (url.endsWith("/ticket-preview")) return response({ ok: true, blockers: [], warnings: [] });
    const body = options?.body ? JSON.parse(String(options.body)) : {};
    return response(body.offering_full_code === "other" ? { ...submitStep, id: "new", block: { id: "new", kind: "form_page", title: "Новый пользователь", fields: [] } } : submitStep);
  });
  vi.stubGlobal("fetch", fetchMock);
  const view = render(<ScenarioSession offering="workplace.printer" owner="old-user" />);
  if (phase === "submit") fireEvent.click(await screen.findByRole("button", { name: "Создать обращение" }));
  await waitFor(() => expect(resolvePending).toBeDefined());
  view.rerender(<ScenarioSession offering="other" owner="new-user" />);
  await screen.findByRole("heading", { name: "Новый пользователь" });
  expect(pendingSignal?.aborted).toBe(true);
  await act(async () => { resolvePending(response(phase === "preview" ? { ok: true, blockers: [], warnings: [] } : { ...submitStep, state: "ticket_created", linked_ticket_id: "old-ticket" })); });
  expect(screen.getByRole("heading", { name: "Новый пользователь" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Создать обращение" })).not.toBeInTheDocument();
  expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/submit"))).toHaveLength(phase === "submit" ? 1 : 0);
});

it("reloads server state after an uncertain submit instead of automatically submitting again", async () => {
  let reads = 0;
  const fetchMock = vi.fn(async (url: string) => {
    if (url.endsWith("/ticket-preview")) return response({ ok: true, blockers: [], warnings: [] });
    if (url.endsWith("/submit")) throw new Error("connection lost");
    return response(++reads === 1 ? submitStep : { ...submitStep, state: "ticket_created", linked_ticket_id: "created-on-server" });
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<ScenarioSession offering="workplace.printer" owner="user" />);
  fireEvent.click(await screen.findByRole("button", { name: "Создать обращение" }));
  expect(sessionStorage.getItem("pc_client.scenario.session:user:workplace.printer")).toBe("session");
  fireEvent.click(await screen.findByRole("button", { name: "Загрузить сохранённый шаг" }));
  await screen.findByRole("heading", { name: "Открыто обращение: /app/requester/tickets/created-on-server" });
  expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/submit"))).toHaveLength(1);
  expect(sessionStorage.getItem("pc_client.scenario.session:user:workplace.printer")).toBeNull();
});


it("starts processing the new revision after review and waits for its canonical preview", async () => {
  let resolvePreview!: (response: Response) => void;
  const fetchMock = vi.fn(async (url: string, _options?: RequestInit) => {
    if (url.endsWith("/ticket-preview")) return await new Promise<Response>(resolve => { resolvePreview = resolve; });
    if (url.endsWith("/advance")) return response({ ...submitStep, revision: 8 });
    return response({ ...submitStep, revision: 7, block: { id: "review", kind: "review", title: "Проверьте ответы", answers: [] } });
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<ScenarioSession offering="workplace.printer" />);
  fireEvent.click(await screen.findByRole("button", { name: "Продолжить" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Проверяем обработку обращения");
  expect(screen.queryByRole("button", { name: "Создать обращение" })).not.toBeInTheDocument();
  const previews = fetchMock.mock.calls.filter(([url]) => url.endsWith("/ticket-preview"));
  expect(previews).toHaveLength(1);
  expect(JSON.parse(String(previews[0][1]?.body))).toEqual({ revision: 8 });
  await act(async () => { resolvePreview(response({ ok: true, blockers: [], warnings: ["Требуется доступ к устройству"], expected_first_response: "15 минут", expected_resolution: "до 4 ч" })); });
  await screen.findByRole("button", { name: "Создать обращение" });
  expect(screen.getByText("Первый ответ: 15 минут")).toBeInTheDocument();
  expect(screen.getByText("до 4 ч")).toBeInTheDocument();
  expect(screen.getByText("Требуется доступ к устройству")).toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([url]) => url.endsWith("/submit"))).toBe(false);
});

it("keeps server-side submit validation authoritative and requires a reload after a revision conflict", async () => {
  const fetchMock = vi.fn(async (url: string) => {
    if (url.endsWith("/ticket-preview")) return response({ ok: true, blockers: [], warnings: [] });
    if (url.endsWith("/submit")) return new Response(JSON.stringify({ status: "error", error_code: "REVISION_CONFLICT" }), { status: 409 });
    return response(submitStep);
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<ScenarioSession offering="workplace.printer" />);
  fireEvent.click(await screen.findByRole("button", { name: "Создать обращение" }));
  await screen.findByText("Сценарий изменился в другом окне. Загрузите сохранённый шаг.");
  expect(screen.getByRole("button", { name: "Загрузить сохранённый шаг" })).toBeEnabled();
  expect(screen.queryByRole("button", { name: "Создать обращение" })).not.toBeInTheDocument();
  expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/submit"))).toHaveLength(1);
  expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/ticket-preview"))).toHaveLength(1);
});


it("opens the existing ticket when automatic processing returns a session completed in another window", async () => {
  const fetchMock = vi.fn(async (url: string) => response(url.endsWith("/ticket-preview")
    ? { ...submitStep, revision: 4, state: "ticket_created", linked_ticket_id: "completed-in-another-window" }
    : submitStep));
  vi.stubGlobal("fetch", fetchMock);
  render(<ScenarioSession offering="workplace.printer" owner="user" />);
  await screen.findByRole("heading", { name: "Открыто обращение: /app/requester/tickets/completed-in-another-window" });
  expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/ticket-preview"))).toHaveLength(1);
  expect(fetchMock.mock.calls.some(([url]) => url.endsWith("/submit"))).toBe(false);
  expect(sessionStorage.getItem("pc_client.scenario.session:user:workplace.printer")).toBeNull();
});
