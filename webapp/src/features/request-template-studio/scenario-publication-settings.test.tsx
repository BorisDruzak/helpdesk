import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioPublicationSettings } from "./scenario-publication-settings";
import type { ScenarioDraftDefinition } from "./scenario-contract";
vi.mock("../settings/api", () => ({ fetchWebSettingsPayload: vi.fn(async () => ({ queues: [{ code: "common", name: "Общая поддержка", is_active: true }], calendars: [], ticket_settings: { operational_flags: { queue_mode: "unified", take_queue_common_code: "common" } } })) }));
vi.mock("./scenario-processing", () => ({ ScenarioProcessing: () => <p>Политики услуги</p> }));
afterEach(cleanup);
const definition: ScenarioDraftDefinition = { schema_version: 4, scenario_key: "service", service_code: "it", offering_full_code: "it.service", title: "Услуга", process_binding: { request_template_key: "service" }, blocks: [], processing: { routes: { desk: { title: "Поддержка", queue_code: "" } }, sla_profiles: {}, defaults: { route: "desk", sla_profile: "" } } };
it("keeps fallbacks optional and does not duplicate profile editors or mutate on opening", async () => {
 const change = vi.fn();
 render(<ScenarioPublicationSettings definition={definition} disabled={false} onChange={change} requestId={1} focus="sla" />);
 expect(screen.getByLabelText("Резервный профиль SLA")).toHaveFocus();
 expect(screen.getByLabelText("Резервный профиль SLA")).toHaveValue("");
 expect(screen.getAllByRole("option", { name: "Рассчитать по правилам услуги/пройденному пути" })).toHaveLength(2);
 expect(screen.queryByRole("button", { name: "Добавить профиль SLA" })).not.toBeInTheDocument();
 await screen.findByRole("button", { name: "Использовать общую очередь «Общая поддержка»" });
 expect(change).not.toHaveBeenCalled();
});
it("repairs a selected direction with the configured common queue only on explicit action", async () => {
 const change = vi.fn();
 render(<ScenarioPublicationSettings definition={definition} disabled={false} onChange={change} requestId={0} />);
 fireEvent.click(await screen.findByRole("button", { name: "Использовать общую очередь «Общая поддержка»" }));
 expect(change).toHaveBeenCalledWith({ ...definition, processing: { ...definition.processing, routes: { desk: { title: "Поддержка", queue_code: "common" } } } });
});

it("manages v3 route and SLA definitions on publication without upgrading or changing defaults", async () => {
 const initial = { ...definition, schema_version: 3 as const, processing: { ...definition.processing!, sla_profiles: { standard: { title: "Стандартный", first_response_minutes: 10, resolution_minutes: 90, time_basis: "calendar" as const } }, defaults: { route: "desk", sla_profile: "standard" } } };
 function Harness() { const [value, setValue] = useState<ScenarioDraftDefinition>(initial); return <><ScenarioPublicationSettings definition={value} disabled={false} onChange={setValue} requestId={0} /><output data-testid="draft">{JSON.stringify(value)}</output></>; }
 render(<Harness />);
 fireEvent.click(screen.getByRole("button", { name: "Настроить направления и профили карты" }));
 const queue = await screen.findByLabelText("Очередь Helpdesk");
 fireEvent.change(queue, { target: { value: "common" } });
 fireEvent.click(screen.getByRole("button", { name: "Профили SLA карты" }));
 fireEvent.change(screen.getByLabelText("Срок решения"), { target: { value: "125" } });
 fireEvent.click(screen.getByRole("button", { name: "Добавить профиль SLA" }));
 fireEvent.change(screen.getByLabelText("Название профиля"), { target: { value: "Для отдельной ветви" } });
 const saved = JSON.parse(screen.getByTestId("draft").textContent!);
 expect(saved.schema_version).toBe(3);
 expect(saved.processing.routes.desk.queue_code).toBe("common");
 expect(saved.processing.sla_profiles.standard.resolution_minutes).toBe(125);
 expect(Object.values(saved.processing.sla_profiles)).toContainEqual(expect.objectContaining({ title: "Для отдельной ветви" }));
 expect(saved.processing.defaults).toEqual(initial.processing.defaults);
});
it("edits an unbound v4 profile without creating or changing fallback assignments", async () => {
 const change = vi.fn();
 const value = { ...definition, processing: { ...definition.processing!, sla_profiles: { branch: { title: "Из перехода", first_response_minutes: 10, resolution_minutes: 90, time_basis: "calendar" as const } } } };
 render(<ScenarioPublicationSettings definition={value} disabled={false} onChange={change} requestId={0} />);
 fireEvent.click(screen.getByRole("button", { name: "Настроить направления и профили карты" }));
 fireEvent.click(screen.getByRole("button", { name: "Профили SLA карты" }));
 fireEvent.change(screen.getByLabelText("Срок решения"), { target: { value: "140" } });
 expect(change).toHaveBeenLastCalledWith({ ...value, processing: { ...value.processing, sla_profiles: { branch: { ...value.processing.sla_profiles.branch, resolution_minutes: 140 } } } });
});
