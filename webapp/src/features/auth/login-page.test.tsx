import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LoginPage } from "./login-page";

vi.mock("./session-provider", () => ({
  useSession: () => ({ status: "anonymous", session: null, login: vi.fn() }),
}));

afterEach(() => vi.unstubAllGlobals());

describe("domain login entry", () => {
  it.each([
    ["identity_unlinked", "Доменная учётная запись пока не связана с профилем Helpdesk. Обратитесь к администратору для проверки связи с вашим существующим профилем."],
    ["identity_unavailable", "Вход с этой доменной учётной записью недоступен. Обратитесь к администратору."],
    ["oidc_unavailable", "Сервис доменного входа временно недоступен. Повторите попытку позже или войдите по логину и паролю."],
    ["oidc_authentication_failed", "Не удалось завершить доменный вход. Повторите попытку или войдите по логину и паролю."],
    ["rate_limited", "Слишком много попыток доменного входа. Подождите минуту и повторите попытку."],
    ["oidc_disabled", "Доменный вход сейчас недоступен. Используйте логин и пароль."],
  ])("shows safe Russian recovery for %s", async (code, message) => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ status: "success", data: {
      self_registration_enabled: false, sso_enabled: true,
    } }), { headers: { "content-type": "application/json" } })));
    render(<MemoryRouter initialEntries={[`/app/login?sso_error=${code}&error_description=private-provider-message&next=https://evil.test`]}><LoginPage /></MemoryRouter>);
    expect(screen.getByRole("alert")).toHaveTextContent(message);
    expect(screen.queryByText(/private-provider-message/)).not.toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Войти через AD" })).toHaveAttribute("href", "/api/web/session/oidc/login");
    expect(screen.getByRole("button", { name: "Войти" })).toBeVisible();
  });

  it.each(["https://evil.test", "__proto__", "private-provider-message"])("ignores unrecognized SSO message %s", (code) => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("offline"); }));
    render(<MemoryRouter initialEntries={[`/app/login?sso_error=${encodeURIComponent(code)}`]}><LoginPage /></MemoryRouter>);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("offers fixed server SSO navigation while retaining password login", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ status: "success", data: {
      self_registration_enabled: false, sso_enabled: true,
    } }), { headers: { "content-type": "application/json" } })));
    render(<MemoryRouter initialEntries={["/app/login?next=https://untrusted.test"]}><LoginPage /></MemoryRouter>);
    expect(screen.queryByRole("link", { name: "Войти через AD" })).not.toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Войти через AD" })).toHaveAttribute("href", "/api/web/session/oidc/login");
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
    expect(screen.queryByRole("link", { name: "Войти через AD" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Войти" })).toBeVisible();
  });
});
