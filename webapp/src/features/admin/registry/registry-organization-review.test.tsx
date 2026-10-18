import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { RegistryOrganizationReview } from "./registry-organization-review";
import { updateAdminRegistryPerson } from "../api";

vi.mock("../api", () => ({ updateAdminRegistryPerson: vi.fn(async () => {}) }));

it("reviews the exact pending change with an explicit reason", async () => {
  render(<QueryClientProvider client={new QueryClient()}><RegistryOrganizationReview personId="p" fields={[
    { key: "department_id", label: "Подразделение", state: "confirmed", value: "old", currentLabel: "Прежний отдел", pending: { proposal_id: "proposal-1", value: "new" }, pendingLabel: "Новый отдел" },
  ]} /></QueryClientProvider>);
  expect(screen.getByText("Прежний отдел")).toBeInTheDocument();
  expect(screen.getByText(/Новый отдел/)).toBeInTheDocument();
  const approve = screen.getByRole("button", { name: "Подтвердить изменение подразделения" });
  expect(approve).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Причина решения"), { target: { value: "Проверено организацией" } });
  fireEvent.click(approve);
  await waitFor(() => expect(updateAdminRegistryPerson).toHaveBeenCalledWith("p", {
    reason: "Проверено организацией", organization_review: { field: "department_id", proposal_id: "proposal-1", decision: "approve" },
  }));
});
