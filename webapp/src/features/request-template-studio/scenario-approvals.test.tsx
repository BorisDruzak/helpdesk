import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioApprovals } from "./scenario-approvals";
afterEach(() => vi.unstubAllGlobals());
it("requires confirmation and preserves unfamiliar source configuration in a new version", async () => {
  const policy = { code: "manager", title: "Manager", kind: "approval", scope_level: "service", scope_ref: "it", is_active: true, published_at: "now", config: { required: true, approval_mode: "all", approver_source: { type: "requester_manager", fallback: "queue_lead" }, timeout: { reminder_after: "4h" }, custom: { preserved: true } } };
  const fetcher = vi.fn(async (_url: unknown, init?: RequestInit) => new Response(JSON.stringify({ status: "success", data: init?.method === "POST" ? { policy } : { policies: { approval: [policy] } } }), { headers: { "content-type": "application/json" } }));
  vi.stubGlobal("fetch", fetcher);
  const onChange = vi.fn();
  render(<QueryClientProvider client={new QueryClient()}><ScenarioApprovals definition={{ scenario_key: "s", title: "S", service_code: "it", offering_full_code: "it.print", process_binding: { request_template_key: "t", policy_refs: { approval: "manager" } } }} disabled={false} onChange={onChange} /></QueryClientProvider>);
  fireEvent.click(await screen.findByRole("button", { name: "Новая версия схемы" }));
  fireEvent.click(screen.getByLabelText("Разрешить подтверждённого руководителя подразделения, если персональный не указан"));
  fireEvent.change(screen.getByLabelText("Режим согласования"), { target: { value: "sequential" } });
  fireEvent.click(screen.getByRole("button", { name: "Опубликовать схему" }));
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
  fireEvent.click(screen.getByRole("button", { name: "Подтвердить публикацию схемы" }));
  await screen.findByRole("button", { name: "Создать схему согласования" });
  const call = fetcher.mock.calls.find(([, init]) => init?.method === "POST");
  expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({ scope_level: "service", scope_ref: "it", config: { approval_mode: "sequential", custom: { preserved: true }, timeout: { reminder_after: "4h" }, approver_source: { fallback: "queue_lead", allow_department_fallback: true } } });
});

it("publishes authoritative account logins selected by human-readable names", async () => {
  const fetcher = vi.fn(async (url: unknown, init?: RequestInit) => new Response(JSON.stringify({ status: "success", data: String(url).endsWith("/registry") ? { ui_users: [
    { user_login: "support-choice", linked_person_name: "Анна Согласующая", actor_role: "support", is_active: true },
    { user_login: "inactive", linked_person_name: "Неактивный", actor_role: "support", is_active: false },
    { user_login: "requester", linked_person_name: "Сотрудник", actor_role: "user", is_active: true },
  ] } : init?.method === "POST" ? { policy: { code: "selected" } } : { policies: {} } }), { headers: { "content-type": "application/json" } }));
  vi.stubGlobal("fetch", fetcher);
  render(<QueryClientProvider client={new QueryClient()}><ScenarioApprovals definition={{ scenario_key: "s", title: "S", service_code: "it", offering_full_code: "it.print", process_binding: { request_template_key: "t" } }} disabled={false} onChange={vi.fn()} /></QueryClientProvider>);
  fireEvent.click(await screen.findByRole("button", { name: "Создать схему согласования" }));
  fireEvent.change(screen.getByLabelText("Источник согласующего"), { target: { value: "explicit_users" } });
  expect(screen.getByRole("button", { name: "Опубликовать схему" })).toBeDisabled();
  fireEvent.click(await screen.findByLabelText("Анна Согласующая"));
  expect(screen.queryByLabelText("Неактивный")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Сотрудник")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Опубликовать схему" }));
  fireEvent.click(screen.getByRole("button", { name: "Подтвердить публикацию схемы" }));
  await screen.findByRole("button", { name: "Создать схему согласования" });
  const call = fetcher.mock.calls.find(([, init]) => init?.method === "POST");
  expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({ config: { approver_source: { type: "explicit_users", user_ids: ["support-choice"] } } });
});

it.each([false, true])("does not overwrite newer graph or mutate an unmounted editor after deferred publication (unmount=%s)", async unmount => {
  let resolvePublish!: (response: Response) => void;
  vi.stubGlobal("fetch", vi.fn((_url: unknown, init?: RequestInit) => init?.method === "POST" ? new Promise<Response>(resolve => { resolvePublish = resolve; }) : Promise.resolve(new Response(JSON.stringify({ status: "success", data: { policies: {} } }), { headers: { "content-type": "application/json" } }))));
  const onChange = vi.fn();
  const client = new QueryClient();
  const initial = { scenario_key: "s", title: "Original", service_code: "it", offering_full_code: "it.print", blocks: [], process_binding: { request_template_key: "t" } };
  const view = render(<QueryClientProvider client={client}><ScenarioApprovals definition={initial} disabled={false} onChange={onChange} /></QueryClientProvider>);
  fireEvent.click(await screen.findByRole("button", { name: "Создать схему согласования" }));
  fireEvent.click(screen.getByRole("button", { name: "Опубликовать схему" }));
  fireEvent.click(screen.getByRole("button", { name: "Подтвердить публикацию схемы" }));
  const newer = { ...initial, title: "New graph", blocks: [{ id: "instruction", kind: "instruction" as const, title: "New instruction", content: { body: "Preserve me" } }] };
  if (unmount) view.unmount();
  else view.rerender(<QueryClientProvider client={client}><ScenarioApprovals definition={newer} disabled={false} onChange={onChange} /></QueryClientProvider>);
  await act(async () => { resolvePublish(new Response(JSON.stringify({ status: "success", data: { policy: { code: "published" } } }), { headers: { "content-type": "application/json" } })); await Promise.resolve(); });
  if (unmount) expect(onChange).not.toHaveBeenCalled();
  else await waitFor(() => expect(onChange).toHaveBeenCalledWith({ ...newer, process_binding: { ...newer.process_binding, policy_refs: { approval: "published" } } }));
});
