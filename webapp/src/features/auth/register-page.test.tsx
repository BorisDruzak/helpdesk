import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LoginPage } from "./login-page";
import { RegisterPage } from "./register-page";
import { SessionProvider } from "./session-provider";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json"
    }
  });
}

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{`${location.pathname}${location.search}`}</span>;
}

function renderRegisterPage(initialEntry = "/app/register") {
  return render(
    <SessionProvider>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route
            element={
              <>
                <RegisterPage />
                <LocationProbe />
              </>
            }
            path="/app/register"
          />
          <Route
            element={
              <>
                <LoginPage />
                <LocationProbe />
              </>
            }
            path="/app/login"
          />
          <Route element={<LocationProbe />} path="/app" />
        </Routes>
      </MemoryRouter>
    </SessionProvider>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("RegisterPage", () => {
  it("preserves the app return path when an existing user returns to login", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === "/api/web/session/capabilities") {
        return jsonResponse({ status: "success", data: { self_registration_enabled: true } });
      }
      return jsonResponse({ status: "error" }, 401);
    }));
    renderRegisterPage("/app/register?next=%2Fapp%2Frequester%2Fdevices%2Flink");
    await screen.findByRole("link", { name: "Войти" });
    expect(screen.getByRole("link", { name: "Войти" })).toHaveAttribute(
      "href", "/app/login?next=%2Fapp%2Frequester%2Fdevices%2Flink"
    );
  });

  it("offers account registration from the login page while preserving the return path", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === "/api/web/session/capabilities") {
        return jsonResponse({ status: "success", data: { self_registration_enabled: true } });
      }
      if (String(input) === "/api/web/session/me") {
        return jsonResponse({ status: "error" }, 401);
      }
      throw new Error(`Unexpected fetch: ${String(input)}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderRegisterPage("/app/login?next=%2Fapp%2Frequester%2Fdevices%2Flink");

    const registerLink = await screen.findByRole("link", { name: "Создать аккаунт" });
    expect(registerLink).toHaveAttribute(
      "href",
      "/app/register?next=%2Fapp%2Frequester%2Fdevices%2Flink"
    );
  });

  it("submits a password reset request from the login page", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/session/capabilities") {
        return jsonResponse({ status: "success", data: { self_registration_enabled: true } });
      }
      if (url === "/api/web/session/me") {
        return jsonResponse({ status: "error" }, 401);
      }
      if (url === "/api/web/session/password-reset-requests") {
        expect(init?.method).toBe("POST");
        expect(JSON.parse(String(init?.body))).toEqual({ login: "ivan@example.test" });
        return jsonResponse({ status: "success", data: { accepted: true } });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderRegisterPage("/app/login?forgot_password=1");

    fireEvent.change(await screen.findByLabelText("Логин для восстановления"), {
      target: { value: " ivan@example.test " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Отправить заявку" }));

    expect(await screen.findByText("Заявка отправлена администратору.")).toBeInTheDocument();
  });
});


describe("server registration policy", () => {
  it.each([false, "unavailable"])("fails closed when registration policy is %s", async (enabled) => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === "/api/web/session/me") return jsonResponse({ status: "error" }, 401);
      if (String(input) === "/api/web/session/capabilities") {
        if (enabled === "unavailable") throw new Error("Unavailable");
        return jsonResponse({ status: "success", data: { self_registration_enabled: enabled } });
      }
      throw new Error("Unexpected request");
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);
    const login = renderRegisterPage("/app/login");
    expect(await screen.findByText(/Самостоятельная регистрация недоступна/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Создать аккаунт" })).not.toBeInTheDocument();
    login.unmount();
    renderRegisterPage();
    expect(await screen.findByText(/Самостоятельная регистрация недоступна/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Пароль")).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([input]) => String(input).includes("/register-requester"))).toHaveLength(0);
  });
});
