import { useState } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { ScenarioMapProcessing } from "./scenario-map-processing";
import { conditionFieldAvailability } from "./scenario-builder-model";
import { fetchWebSettingsPayload } from "../settings/api";

vi.mock("../settings/api", () => ({ fetchWebSettingsPayload: vi.fn(async () => ({ queues: [{ code: "support", name: "Поддержка", is_active: true }, { code: "disabled", name: "Отключена", is_active: false }], calendars: [{ id: 8, name: "Рабочая неделя", is_active: true }] })) }));
const draft: ScenarioDraftDefinition = { schema_version: 3, scenario_key: "s", title: "Карта", service_code: "it", offering_full_code: "it.map", process_binding: { request_template_key: "map" }, processing: { routes: {}, sla_profiles: {}, defaults: { route: "", sla_profile: "" } } };
it("keeps an imported queue reference visible when registry loading fails and supports retry", async () => {
 vi.mocked(fetchWebSettingsPayload).mockRejectedValueOnce(new Error("offline"));
 const change = vi.fn();
 render(<ScenarioMapProcessing definition={{ ...draft, processing: { routes: { support: { title: "Поддержка", queue_code: "retired" } }, sla_profiles: {}, defaults: { route: "support", sla_profile: "" } } }} disabled={false} onChange={change} />);
 expect(await screen.findByText("Не удалось загрузить очереди и рабочие календари.")).toBeVisible();
 expect(screen.getByLabelText("Очередь Helpdesk")).toHaveValue("retired");
 expect(screen.getByLabelText("Очередь Helpdesk")).toBeDisabled();
 expect(change).not.toHaveBeenCalled();
 fireEvent.click(screen.getByRole("button", { name: "Повторить загрузку справочников" }));
 await waitFor(() => expect(screen.getByLabelText("Очередь Helpdesk")).toBeEnabled());
 expect(screen.getByRole("option", { name: "Выбранная очередь недоступна" })).toBeVisible();
});
it("edits map-local durations and chooses trusted queues/calendars without creating global policies", async () => {
 function Harness() { const [value, setValue] = useState(draft); return <><ScenarioMapProcessing definition={value} disabled={false} onChange={setValue} /><output data-testid="definition">{JSON.stringify(value)}</output></>; }
 render(<Harness />);
 await waitFor(() => expect(screen.getByRole("button", { name: "Добавить направление" })).toBeEnabled());
 fireEvent.click(screen.getByRole("button", { name: "Добавить направление" }));
 expect(screen.queryByRole("option", { name: "Отключена" })).not.toBeInTheDocument();
 fireEvent.change(screen.getByLabelText("Очередь Helpdesk"), { target: { value: "support" } });
 fireEvent.click(screen.getByRole("button", { name: "Добавить профиль SLA" }));
 fireEvent.change(screen.getByLabelText("Название профиля"), { target: { value: "Срочный" } });
 fireEvent.change(screen.getByLabelText("Первый ответ"), { target: { value: "30" } });
 fireEvent.change(screen.getByLabelText("Единица срока решения"), { target: { value: "60" } });
 fireEvent.change(screen.getByLabelText("Срок решения"), { target: { value: "2" } });
 fireEvent.change(screen.getByLabelText("Учёт времени"), { target: { value: "business" } });
 fireEvent.change(screen.getByLabelText("Рабочий календарь"), { target: { value: "8" } });
 const saved = JSON.parse(screen.getByTestId("definition").textContent!);
 expect(Object.values(saved.processing.routes)).toEqual([{ title: "Новое направление", queue_code: "support" }]);
 expect(Object.values(saved.processing.sla_profiles)).toEqual([{ title: "Срочный", first_response_minutes: 30, resolution_minutes: 120, time_basis: "business", calendar_id: 8 }]);
 expect(saved.processing.defaults).toEqual({ route: "", sla_profile: "" });
});
it("lists all upstream questions and marks questions bypassed by a specialized entry", () => {
 const definition: ScenarioDraftDefinition = { ...draft, entry_block_id: "q1", entry_points: [{ key: "special", title: "Быстрый вход", target_block_id: "q3" }], blocks: [
 { id: "q1", kind: "form_page", title: "Первый", fields: [{ key: "a", type: "text", label: "Что не работает?", required: true }], transitions: [{ to: "q2" }] },
 { id: "q2", kind: "form_page", title: "Второй", fields: [{ key: "b", type: "text", label: "Масштаб", required: true }], transitions: [{ to: "q3" }] },
 { id: "q3", kind: "form_page", title: "Третий", fields: [{ key: "c", type: "text", label: "Можно работать?", required: true }], transitions: [{ to: "logic" }] },
 { id: "logic", kind: "decision", title: "Условие" } ] };
 expect(conditionFieldAvailability(definition, "logic").map(item => [item.field.key, item.mayBeMissing])).toEqual([["a", true], ["b", true], ["c", false]]);
});
