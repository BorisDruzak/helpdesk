import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { ScenarioPolicyAttachmentEditor } from "./scenario-policy-attachments";
import { fetchHelpdeskModelRegistry } from "../forms-builder/api";
import { ScenarioRequesterPreview } from "./scenario-requester-preview";
import { summarizeTerminalSla } from "./scenario-terminal-sla-model";
const draft = (): ScenarioDraftDefinition => ({ schema_version: 4, scenario_key: "test", title: "Карта", service_code: "it", offering_full_code: "it.test", process_binding: { request_template_key: "test" }, entry_block_id: "end", blocks: [
 { id: "end", kind: "submit_ticket", title: "Обращение" }, { id: "sla", kind: "sla_attachment", title: "SLA" }, { id: "route", kind: "routing_attachment", title: "Маршрут" },
], processing: { defaults: { route: "desk", sla_profile: "normal" }, routes: { desk: { title: "Поддержка", queue_code: "support" } }, sla_profiles: { normal: { title: "Рабочий SLA", first_response_minutes: 15, resolution_minutes: 240, time_basis: "business", calendar_id: 3 } } } });
vi.mock("../forms-builder/api", () => ({ fetchHelpdeskModelRegistry: vi.fn(async () => ({ policies: { sla: [{ code: "sla", title: "Опубликованный SLA", is_active: true, published_at: "now" }], routing: [{ code: "route", title: "Опубликованный маршрут", is_active: true, published_at: "now" }, { code: "draft", title: "Черновик маршрута", is_active: true }] } })) }));
vi.mock("../settings/api",()=>({fetchWebSettingsPayload:vi.fn(async()=>({queues:[{code:"support",name:"Поддержка",is_active:true}],calendars:[{id:3,name:"Рабочая неделя",is_active:true}]}))}));
it("keeps service-wide defaults off the per-block route editor",async()=>{
 const definition=draft(); definition.processing!.defaults.route="";
 const change=vi.fn();
 render(<ScenarioPolicyAttachmentEditor block={{...definition.blocks![2],kind:"routing_attachment",route:"desk"}} definition={definition} disabled={false} onChange={change}/>);
 expect(change).not.toHaveBeenCalled();
 expect(screen.queryByRole("button",{name:"Использовать направление по умолчанию"})).not.toBeInTheDocument();
 expect(change).not.toHaveBeenCalled();
 await waitFor(()=>expect(screen.getByLabelText("Очередь Helpdesk")).toBeEnabled());
});
it("edits the selected SLA in its attachment without route settings", async()=>{
 const definition=draft(),change=vi.fn();
 render(<ScenarioPolicyAttachmentEditor block={{...definition.blocks![1],kind:"sla_attachment",sla_profile:"normal"}} definition={definition} disabled={false} onChange={change}/>);
 expect(screen.getByLabelText("Первый ответ")).toHaveValue(15);
 expect(screen.queryByLabelText("Очередь Helpdesk")).not.toBeInTheDocument();
 fireEvent.change(screen.getByLabelText("Срок решения"),{target:{value:"300"}});
 expect(change.mock.lastCall![0].processing.sla_profiles.normal.resolution_minutes).toBe(300);
 await screen.findByRole("option",{name:"Рабочая неделя"});
});
it("edits the selected route in its attachment without SLA settings", async()=>{
 const definition=draft(),change=vi.fn();
 render(<ScenarioPolicyAttachmentEditor block={{...definition.blocks![2],kind:"routing_attachment",route:"desk"}} definition={definition} disabled={false} onChange={change}/>);
 await waitFor(()=>expect(screen.getByLabelText("Очередь Helpdesk")).toBeEnabled());
 expect(screen.queryByLabelText("Первый ответ")).not.toBeInTheDocument();
 fireEvent.change(screen.getByLabelText("Название направления"),{target:{value:"Дежурная поддержка"}});
 expect(change.mock.lastCall![0].processing.routes.desk.title).toBe("Дежурная поддержка");
});
it("chooses a target and an existing SLA profile without creating duration defaults", () => {
 const definition = draft(), change = vi.fn();
 render(<ScenarioPolicyAttachmentEditor block={definition.blocks![1]} definition={definition} disabled={false} onChange={change} />);
 expect(change).not.toHaveBeenCalled();
 expect(screen.getByRole("option",{name:"Не менять ранее выбранные сроки"})).toBeInTheDocument();
 fireEvent.change(screen.getByLabelText("Применять к блоку"), { target: { value: "end" } });
 expect(change.mock.lastCall![0].blocks[1]).toMatchObject({ attached_to: "end" });
 fireEvent.change(screen.getByLabelText("Профиль SLA"), { target: { value: "normal" } });
 expect(change.mock.lastCall![0].blocks[1]).toMatchObject({ sla_profile: "normal" });
 expect(change.mock.lastCall![0].processing).toEqual(definition.processing);
 expect(screen.queryByRole("option", { name: "Маршрут" })).not.toBeInTheDocument();
});
it("clears only the attachment override and retains a manual profile assigned earlier on the path", async () => {
 const definition = draft(), change = vi.fn();
 definition.entry_block_id = "earlier";
 definition.processing!.defaults.sla_profile = "";
 definition.blocks!.unshift({ id: "earlier", title: "Ранее выбранные сроки", kind: "sla", sla_profile: "normal", transitions: [{ to: "end" }] });
 const attachment = { ...definition.blocks![2], kind: "sla_attachment" as const, attached_to: "end", sla_profile: "normal" };
 definition.blocks![2] = attachment;
 render(<ScenarioPolicyAttachmentEditor block={attachment} definition={definition} disabled={false} onChange={change} />);
 fireEvent.change(screen.getByLabelText("Профиль SLA"), { target: { value: "" } });
 const next = change.mock.lastCall![0] as ScenarioDraftDefinition;
 expect(next.processing).toEqual(definition.processing);
 expect(next.blocks![0]).toEqual(definition.blocks![0]);
 expect(next.blocks![2]).not.toHaveProperty("sla_profile");
 expect(summarizeTerminalSla(next, "end").alternatives[0].selection).toMatchObject({ kind: "profile", key: "normal" });
 expect(screen.getByText(/Пустой выбор сохраняет ранее назначенный профиль/)).toBeVisible();
 await screen.findByRole("option", { name: "Рабочая неделя" });
});
it("does not render attachment cards as employee steps", () => {
 const definition = draft();
 render(<ScenarioRequesterPreview block={definition.blocks![1]} definition={definition} />);
 expect(screen.getByText(/не показывается сотруднику/)).toBeInTheDocument(); expect(screen.queryByLabelText("Блок глазами сотрудника")).not.toBeInTheDocument();
});
it("chooses existing map routes and shows their actual queue", () => {
 const definition = draft(), change = vi.fn();
 render(<ScenarioPolicyAttachmentEditor block={{ ...definition.blocks![2], kind: "routing_attachment", route: "desk" }} definition={definition} disabled={false} onChange={change} />);
 expect(screen.getByText(/Очередь: support/)).toBeInTheDocument();
 fireEvent.change(screen.getByLabelText("Маршрут обработки"), { target: { value: "" } });
 expect(change.mock.lastCall![0].blocks[2]).not.toHaveProperty("route");
});
it("shows only published active routing policies and preserves an unavailable selection", async () => {
 const definition = draft(); definition.processing = null; const change = vi.fn();
 render(<ScenarioPolicyAttachmentEditor block={{ ...definition.blocks![2], kind: "routing_attachment", policy_ref: "missing" }} definition={definition} disabled={false} onChange={change} />);
 await waitFor(() => expect(screen.getByRole("option", { name: "Опубликованный маршрут" })).toBeInTheDocument());
 expect(screen.queryByRole("option", { name: "Черновик маршрута" })).not.toBeInTheDocument();
 expect(screen.getByRole("option", { name: /Сохранённое правило недоступно/ })).toHaveValue("missing");
 expect(change).not.toHaveBeenCalled();
 fireEvent.change(screen.getByLabelText("Правило маршрутизации"), { target: { value: "route" } });
 expect(change.mock.lastCall![0].blocks[2]).toMatchObject({ policy_ref: "route" });
});
it("reports target conflicts instead of overwriting another setting", () => {
 const definition = draft(); definition.blocks!.push({ id: "other", kind: "sla_attachment", title: "Другой SLA", attached_to: "end" });
 const change = vi.fn();
 render(<ScenarioPolicyAttachmentEditor block={definition.blocks![1]} definition={definition} disabled={false} onChange={change} />);
 fireEvent.change(screen.getByLabelText("Применять к блоку"), { target: { value: "end" } });
 expect(screen.getByRole("alert")).toHaveTextContent(/уже есть/); expect(change).not.toHaveBeenCalled();
});
it("offers retry on registry failure without clearing saved policy", async () => {
 vi.mocked(fetchHelpdeskModelRegistry).mockRejectedValueOnce(new Error("offline"));
 const definition = draft(); definition.processing = null;
 render(<ScenarioPolicyAttachmentEditor block={{ ...definition.blocks![1], kind: "sla_attachment", policy_ref: "saved" }} definition={definition} disabled={false} onChange={vi.fn()} />);
 await waitFor(() => expect(screen.getByRole("button", { name: "Повторить загрузку правил" })).toBeInTheDocument());
 fireEvent.click(screen.getByRole("button", { name: "Повторить загрузку правил" }));
 await waitFor(() => expect(screen.getByRole("option", { name: "Опубликованный SLA" })).toBeInTheDocument());
 expect(screen.getByRole("combobox", { name: "Правило SLA" })).toHaveValue("saved");
});
