import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LoginPage } from "./login-page";

vi.mock("./session-provider", () => ({
  useSession: () => ({ status: "anonymous", session: null, login: vi.fn() }),
}));

afterEach(() => vi.unstubAllGlobals());

describe("domain login entry", () => {
  it("offers fixed server SSO navigation while retaining password login", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ status: "success", data: {
      self_registration_enabled: false, sso_enabled: true,
    } }), { headers: { "content-type": "application/json" } })));
    render(<MemoryRouter initialEntries={["/app/login?next=https://untrusted.test"]}><LoginPage /></MemoryRouter>);
    expect(screen.queryByRole("link", { name: "Войти с доменной учётной записью" })).not.toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Войти с доменной учётной записью" })).toHaveAttribute("href", "/api/web/session/oidc/login");
    expect(screen.getByLabelText("Логин")).toBeVisible();
    expect(screen.getByLabelText("Пароль")).toBeVisible();
    expect(screen.getByRole("button", { name: "Войти" })).toBeVisible();
  });

  it.each(["disabled", "unavailable", "legacy"])("hides SSO when policy is %s", async (state) => {
    vi.stubGlobal("fetch", vi.fn(async () => {
      if (state === "unavailable") throw new Error("unavailable");
      return new Response(JSON.stringify({ status: "success", data: {
        self_registration_enabled: false, ...(state === "legacy" ? {} : { sso_enabled: false }),
      } }), { headers: { "content-type": "application/json" } });
    }));
    render(<MemoryRouter><LoginPage /></MemoryRouter>);
    await waitFor(() => expect(screen.queryByText("Проверяем доступность регистрации…")).not.toBeInTheDocument());
    expect(screen.queryByRole("link", { name: "Войти с доменной учётной записью" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Войти" })).toBeVisible();
  });
});
