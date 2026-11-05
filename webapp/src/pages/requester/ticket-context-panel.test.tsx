import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it } from "vitest";
import { RequesterTicketContext, RequesterTicketContextBrief } from "./ticket-context-panel";
import type { RequesterTicketHandling } from "../../features/requester/types";

afterEach(cleanup);
const handling: RequesterTicketHandling = {
  status: "in_work", status_label: "В работе", next_action_owner: "support",
  assignee: { assigned: true, display_name: "Иван Петров" },
  sla: {
    first_response: { status: "completed", completed_at: "2026-11-05T08:00:00Z", completed_within_target: true },
    resolution: { status: "paused", remaining_seconds: 7200, effective_due_at: "2026-11-05T12:00:00Z" },
  },
  device: { state: "linked", display_name: "PC-205", presence: "unavailable" },
};

it("keeps assignee, paused SLA and unavailable device state visible with no fake offline", () => {
  render(<MemoryRouter><RequesterTicketContext handling={handling} /></MemoryRouter>);
  expect(screen.getByText("Иван Петров")).toBeVisible();
  expect(screen.getByText("Ответ получен")).toBeVisible();
  expect(screen.getByText(/На паузе/)).toBeVisible();
  expect(screen.getByText("PC-205")).toBeVisible();
  expect(screen.getByText("Состояние недоступно")).toBeVisible();
  expect(screen.queryByText("Не в сети")).not.toBeInTheDocument();
});

it("distinguishes waiting for assignment, no device and missing SLA", () => {
  render(<MemoryRouter><RequesterTicketContext handling={{ status_label: "Принято", assignee: { assigned: false }, device: { state: "none" }, sla: { first_response: { status: "unknown" }, resolution: { status: "unknown" } } }} /></MemoryRouter>);
  expect(screen.getByText("Специалист ещё не назначен")).toBeVisible();
  expect(screen.getByText("Устройство не указано")).toBeVisible();
  expect(screen.getAllByText("Срок не назначен")).toHaveLength(2);
});

it("does not recreate server-hidden handling sections", () => {
  render(<MemoryRouter><RequesterTicketContext handling={{ status_label: "В работе" }} /></MemoryRouter>);
  expect(screen.queryByText("Устройство")).not.toBeInTheDocument();
  expect(screen.queryByText("Сроки · SLA")).not.toBeInTheDocument();
});

it("keeps an expired paused SLA overdue instead of showing positive time left", () => {
  render(<MemoryRouter><RequesterTicketContext handling={{ sla: { first_response: { status: "unknown" }, resolution: { status: "paused", remaining_seconds: -1800 } } }} /></MemoryRouter>);
  expect(screen.getByText("На паузе · просрочено на 30 мин")).toBeVisible();
  expect(screen.queryByText(/осталось 30 мин/)).not.toBeInTheDocument();
});

it("renders only the SLA targets allowed by the server policy", () => {
  const partial: RequesterTicketHandling = { sla: { first_response: { status: "completed" } } };
  render(<MemoryRouter><RequesterTicketContext handling={partial} /><RequesterTicketContextBrief handling={partial} /></MemoryRouter>);
  expect(screen.getAllByText(/Ответ получен/)).toHaveLength(2);
  expect(screen.queryByText("Решение")).not.toBeInTheDocument();
  expect(screen.queryByText(/Решение:/)).not.toBeInTheDocument();
});
