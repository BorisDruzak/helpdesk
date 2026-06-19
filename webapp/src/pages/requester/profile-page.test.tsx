import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RequesterProfilePage } from "./profile-page";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderProfilePage(initialEntry = "/app/requester/profile") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
    },
  });

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={[initialEntry]}>
        <QueryClientProvider client={queryClient}>
          <Routes>
            <Route path="/app/requester/profile" element={children} />
            <Route path="/app/requester/profile/setup" element={children} />
            <Route path="/app/requester" element={<p>Главная заявителя</p>} />
          </Routes>
        </QueryClientProvider>
      </MemoryRouter>
    );
  }

  return render(<RequesterProfilePage />, { wrapper: Wrapper });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("RequesterProfilePage", () => {
  it("renders a safe read mode without provider, verified or Registry status details", async () => {
    installProfileMock();
    renderProfilePage();

    expect(await screen.findByRole("heading", { name: "Профиль" })).toBeInTheDocument();
    expect(screen.getAllByText("Иван Петров").length).toBeGreaterThan(0);
    expect(screen.getByText("ИТ")).toBeInTheDocument();
    expect(screen.getByText("Екатеринбург")).toBeInTheDocument();
    expect(screen.getByText("4567")).toBeInTheDocument();
    expect(screen.queryByText(/Registry/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/verified/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/provider/i)).not.toBeInTheDocument();
    expect(screen.queryByText("active")).not.toBeInTheDocument();
  });

  it("renders admin-published custom fields and saves internal extension when phone is blank", async () => {
    const fetchMock = installProfileMock({ complete: false });
    renderProfilePage("/app/requester/profile/setup?next=/app/requester/new");

    expect(await screen.findByRole("heading", { name: "Заполните профиль" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("ФИО"), { target: { value: "Иван Петров" } });
    fireEvent.change(screen.getByLabelText("Телефон"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("Внутренний номер"), { target: { value: "8899" } });
    fireEvent.change(screen.getByLabelText("Подразделение"), { target: { value: "dept-it" } });
    fireEvent.change(screen.getByLabelText("Локация"), { target: { value: "loc-ekb" } });
    fireEvent.change(screen.getByLabelText("Центр затрат"), { target: { value: "CC-42" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить профиль" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/requester/profile",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({
            person_id: "person-1",
            full_name: "Иван Петров",
            department_id: "dept-it",
            location_id: "loc-ekb",
            phone: "",
            internal_extension: "8899",
            custom_fields: { cost_center: "CC-42" },
          }),
        }),
      );
    });
    expect(await screen.findByText("Профиль сохранен")).toBeInTheDocument();
  });

  it("warns before canceling unsaved profile changes", async () => {
    installProfileMock({ complete: false });
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    renderProfilePage("/app/requester/profile/setup");

    fireEvent.change(await screen.findByLabelText("Внутренний номер"), { target: { value: "9999" } });
    fireEvent.click(screen.getByRole("button", { name: "Отменить" }));

    expect(confirmSpy).toHaveBeenCalledWith("Есть несохраненные изменения профиля. Отменить их?");
    expect(screen.getByLabelText("Внутренний номер")).toHaveValue("9999");
  });

  it("focuses the first missing profile field and does not expose technical keys in accessible names", async () => {
    installProfileMock({ complete: false });
    renderProfilePage("/app/requester/profile/setup");

    await screen.findByLabelText("ФИО");
    const department = screen.getByLabelText("Подразделение");
    fireEvent.click(screen.getByRole("button", { name: "Сохранить профиль" }));

    await waitFor(() => expect(department).toHaveFocus());
    expect(screen.getByRole("alert")).toHaveTextContent("Заполните обязательные поля");
    expect(screen.queryByLabelText(/full_name|department_id|location_id|cost_center/i)).not.toBeInTheDocument();
  });
});

function installProfileMock({ complete = true }: { complete?: boolean } = {}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === "/api/web/requester/profile") {
      if (init?.method === "PUT") {
        return jsonResponse({
          status: "success",
          data: {
            profile: {
              person_id: "person-1",
              full_name: "Иван Петров",
              display_name: "Иван Петров",
              phone: null,
              internal_extension: "8899",
              department_id: "dept-it",
              location_id: "loc-ekb",
              custom_fields: { cost_center: "CC-42" },
            },
            profile_completion: {
              complete: true,
              status: "complete",
              setup_path: "/app/requester/profile/setup",
              required_fields: [],
              missing_fields: [],
              blocks: { ticket_create: false, ticket_preview: false },
            },
            profile_policy: { required: true },
            profile_schema: profileSchema,
          },
        });
      }
      return jsonResponse({
        status: "success",
        data: {
          profile: {
            person_id: "person-1",
            full_name: complete ? "Иван Петров" : "",
            display_name: "Иван Петров",
            email: "ivan@example.test",
            phone: complete ? "+7 343 000-00-01" : "",
            internal_extension: complete ? "4567" : "",
            department_id: complete ? "dept-it" : "",
            location_id: complete ? "loc-ekb" : "",
            status: "active",
            custom_fields: complete ? { cost_center: "CC-10" } : {},
          },
          profile_completion: {
            complete,
            status: complete ? "complete" : "required",
            setup_path: "/app/requester/profile/setup",
            required_fields: profileSchema.required_fields,
            missing_fields: complete
              ? []
              : [
                  { key: "full_name", label: "ФИО" },
                  { key: "department_id", label: "Подразделение" },
                  { key: "location_id", label: "Локация" },
                  { key: "phone", label: "Телефон или внутренний номер" },
                  { key: "cost_center", label: "Центр затрат" },
                ],
            blocks: { ticket_create: !complete, ticket_preview: !complete },
          },
          profile_policy: { required: true },
          profile_schema: profileSchema,
        },
      });
    }
    if (url === "/api/registry/options") {
      return jsonResponse({
        status: "success",
        data: {
          departments: [{ value: "dept-it", label: "ИТ" }],
          locations: [{ value: "loc-ekb", label: "Екатеринбург" }],
        },
      });
    }
    throw new Error(`Unexpected profile fetch: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock as typeof fetch);
  return fetchMock;
}

const profileSchema = {
  schema_key: "requester_profile",
  fields: [
    { key: "full_name", label: "ФИО", type: "text", required: true, visible: true, system: true, editable: true },
    {
      key: "department_id",
      label: "Подразделение",
      type: "select",
      required: true,
      visible: true,
      system: true,
      editable: true,
      options: [{ value: "dept-it", label: "ИТ" }],
    },
    {
      key: "location_id",
      label: "Локация",
      type: "select",
      required: true,
      visible: true,
      system: true,
      editable: true,
      options: [{ value: "loc-ekb", label: "Екатеринбург" }],
    },
    { key: "phone", label: "Телефон", type: "phone", required: true, visible: true, system: true, editable: true },
    { key: "internal_extension", label: "Внутренний номер", type: "phone", visible: true, editable: true },
    { key: "cost_center", label: "Центр затрат", type: "text", required: true, visible: true, custom: true, editable: true },
  ],
  custom_fields: [
    { key: "cost_center", label: "Центр затрат", type: "text", required: true, visible: true, custom: true, editable: true },
  ],
  required_fields: [
    { key: "full_name", label: "ФИО" },
    { key: "department_id", label: "Подразделение" },
    { key: "location_id", label: "Локация" },
    { key: "phone", label: "Телефон или внутренний номер" },
    { key: "cost_center", label: "Центр затрат" },
  ],
};
