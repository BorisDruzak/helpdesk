import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { OfferingDetails } from "./offering-details";
import type { ScenarioCatalog } from "./scenario-api";

it("keeps archived scenarios inside history and offers creation without replacing the plain form", () => {
  const offering = { full_code: "it.print", service_code: "it", public_title: "Печать", request_template_key: "printer" };
  const archive = { id: "old", title: "Старый сценарий", status: "archived", archived: true };
  const data = { offerings: [offering], services: [], categories: [], entries: [{ offering, active_mode: "form", category_ids: [], scenarios: [archive] }] } as unknown as ScenarioCatalog;
  const create = vi.fn(), open = vi.fn();
  render(<MemoryRouter><OfferingDetails code={offering.full_code} data={data} canEdit onCreate={create} onOpen={open} /></MemoryRouter>);
  expect(screen.getByRole("link", { name: "Настройки услуги" })).toHaveAttribute("href", "/app/admin/service-catalog/offerings/it.print");
  expect(screen.getByRole("link", { name: "Открыть обычную форму" })).toHaveAttribute("href", "/app/admin/forms?template=printer");
  expect(document.querySelector("details")).not.toHaveAttribute("open");
  fireEvent.click(screen.getByRole("button", { name: "Создать сценарий для услуги" }));
  expect(create).toHaveBeenCalledWith(offering);
});

it("does not describe an unavailable offering as a form employees can use", () => {
  const offering = { full_code: "it.hidden", service_code: "it", public_title: "Закрытая услуга", request_template_key: "printer" };
  const data = { offerings: [offering], services: [], categories: [], entries: [{ offering, active_mode: "form", requester_available: false, category_ids: [], scenarios: [] }] } as unknown as ScenarioCatalog;
  render(<MemoryRouter><OfferingDetails code={offering.full_code} data={data} canEdit onCreate={vi.fn()} onOpen={vi.fn()} /></MemoryRouter>);
  expect(screen.queryByText("Сценарий не настроен. Сотрудники используют обычную форму.")).not.toBeInTheDocument();
});
