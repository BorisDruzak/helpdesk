import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi } from "vitest";
import { AdminCenterPage } from "./index";
vi.mock("../../features/auth/session-provider", () => ({useSession: () => ({session: {permissions: []}})}));
describe("AdminCenterPage", () => { it("shows the canonical admin center without a legacy device workspace", () => {
  render(<MemoryRouter><AdminCenterPage/></MemoryRouter>);
  expect(screen.getByRole("heading", {name: "Центр администрирования"})).toBeInTheDocument();
}); });
