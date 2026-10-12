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
