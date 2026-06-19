import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

function getRegisterCalls(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls.filter(([input]) => String(input) === "/api/web/session/register");
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RegisterPage", () => {
  it("creates an account-only requester user and redirects to the login success notice", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/session/me") {
        return jsonResponse({ status: "error" }, 401);
      }
      if (url === "/api/web/session/register") {
        expect(init?.method).toBe("POST");
        expect(JSON.parse(String(init?.body))).toEqual({
          login: "new.user",
          password: "StrongPass123!",
          password_repeat: "StrongPass123!",
          device_link_code: "ABCD-1234"
        });
        return jsonResponse(
          {
            status: "success",
            data: {
              user_login: "new.user",
              actor_role: "user",
              next_path: "/app/login?registered=1",
              device_link: {
                accepted: true,
                purpose: "registration",
                expires_at: "2026-06-15T12:00:00Z"
              }
            }
          },
          201
        );
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    const { container } = renderRegisterPage("/app/register?device_link_code=ABCD-1234");

    expect(await screen.findByRole("button", { name: /Создать аккаунт/ })).toBeInTheDocument();
    expect(container.textContent ?? "").not.toMatch(/ФИО|Подразделение|Локация|full_name|department|location/i);

    fireEvent.change(screen.getByLabelText("Логин"), { target: { value: " new.user " } });
    fireEvent.change(screen.getByLabelText("Пароль"), { target: { value: "StrongPass123!" } });
    fireEvent.change(screen.getByLabelText("Повторите пароль"), { target: { value: "StrongPass123!" } });
    fireEvent.click(screen.getByRole("button", { name: /Создать аккаунт/ }));

    expect(await screen.findByText("Аккаунт создан. Войдите, чтобы продолжить настройку доступа.")).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent("/app/login?registered=1");
  });

  it("blocks mismatched passwords before calling the registration API", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === "/api/web/session/me") {
        return jsonResponse({ status: "error" }, 401);
      }
      throw new Error(`Unexpected fetch: ${String(input)}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderRegisterPage();

    fireEvent.change(await screen.findByLabelText("Логин"), { target: { value: "new.user" } });
    fireEvent.change(screen.getByLabelText("Пароль"), { target: { value: "StrongPass123!" } });
    fireEvent.change(screen.getByLabelText("Повторите пароль"), { target: { value: "DifferentPass123!" } });
    fireEvent.click(screen.getByRole("button", { name: /Создать аккаунт/ }));

    expect(await screen.findByText("Пароли не совпадают.")).toBeInTheDocument();
    expect(getRegisterCalls(fetchMock)).toHaveLength(0);
  });

  it("shows duplicate-login errors from the server without logging the user in", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/web/session/me") {
        return jsonResponse({ status: "error" }, 401);
      }
      if (url === "/api/web/session/register") {
        return jsonResponse(
          {
            status: "error",
            error: "Пользователь с таким логином уже существует.",
            error_code: "LOGIN_ALREADY_EXISTS"
          },
          409
        );
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderRegisterPage();

    fireEvent.change(await screen.findByLabelText("Логин"), { target: { value: "new.user" } });
    fireEvent.change(screen.getByLabelText("Пароль"), { target: { value: "StrongPass123!" } });
    fireEvent.change(screen.getByLabelText("Повторите пароль"), { target: { value: "StrongPass123!" } });
    fireEvent.click(screen.getByRole("button", { name: /Создать аккаунт/ }));

    expect(await screen.findByText("Пользователь с таким логином уже существует.")).toBeInTheDocument();
    await waitFor(() => expect(getRegisterCalls(fetchMock)).toHaveLength(1));
    expect(screen.getByTestId("location")).toHaveTextContent("/app/register");
  });

  it("preserves the device registration return path after account creation", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/session/me") {
        return jsonResponse({ status: "error" }, 401);
      }
      if (url === "/api/web/session/register") {
        expect(init?.method).toBe("POST");
        return jsonResponse(
          {
            status: "success",
            data: {
              user_login: "new.device.user",
              actor_role: "user",
              next_path: "/app/login?registered=1",
            },
          },
          201
        );
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderRegisterPage("/app/register?next=%2Fapp%2Fdevice%2Fregister%3Fpairing_id%3Dpair-next");

    fireEvent.change(await screen.findByLabelText("Логин"), { target: { value: "new.device.user" } });
    fireEvent.change(screen.getByLabelText("Пароль"), { target: { value: "StrongPass123!" } });
    fireEvent.change(screen.getByLabelText("Повторите пароль"), { target: { value: "StrongPass123!" } });
    fireEvent.click(screen.getByRole("button", { name: /Создать аккаунт/ }));

    await waitFor(() =>
      expect(screen.getByTestId("location")).toHaveTextContent(
        "/app/login?registered=1&next=%2Fapp%2Fdevice%2Fregister%3Fpairing_id%3Dpair-next"
      )
    );
  });

  it("offers account registration from the login page while preserving the return path", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === "/api/web/session/me") {
        return jsonResponse({ status: "error" }, 401);
      }
      throw new Error(`Unexpected fetch: ${String(input)}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderRegisterPage("/app/login?next=%2Fapp%2Fdevice%2Fregister%3Fpairing_id%3Dpair-login");

    const registerLink = await screen.findByRole("link", { name: "Создать аккаунт" });
    expect(registerLink).toHaveAttribute(
      "href",
      "/app/register?next=%2Fapp%2Fdevice%2Fregister%3Fpairing_id%3Dpair-login"
    );
  });

  it("submits a password reset request from the login page", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
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
