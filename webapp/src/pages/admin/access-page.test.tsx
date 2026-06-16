import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AdminAccessPage } from "./access-page";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    headers: {
      "Content-Type": "application/json",
    },
    status,
  });
}

function renderAccessPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        refetchOnWindowFocus: false,
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <AdminAccessPage />
    </QueryClientProvider>,
  );
}

const catalogPayload = {
  version: "rbac-test",
  roles: [
    {
      code: "admin",
      label: "Администратор",
      permissions: ["workspace.admin.view", "workspace.support.view", "admin.access.view", "admin.forms.publish"],
    },
    {
      code: "support",
      label: "Поддержка",
      permissions: ["workspace.support.view", "ticket.queue.view", "ticket.status.change"],
    },
    {
      code: "auditor",
      label: "Аудитор",
      permissions: ["ticket.queue.view"],
    },
    {
      code: "user",
      label: "Пользователь",
      permissions: ["workspace.requester.view"],
    },
    {
      code: "agent",
      label: "Агент",
      permissions: [],
    },
    {
      code: "system",
      label: "Система",
      permissions: [],
    },
  ],
  groups: [
    {
      code: "workspaces",
      label: "Рабочие области",
      permissions: [
        {
          code: "workspace.admin.view",
          description: "Доступ к административной рабочей области.",
          label: "Открывать администрирование",
          risk: "normal",
        },
        {
          code: "workspace.support.view",
          description: "Доступ к рабочей области поддержки.",
          label: "Открывать поддержку",
          risk: "normal",
        },
      ],
    },
    {
      code: "tickets",
      label: "Тикеты",
      permissions: [
        {
          code: "ticket.queue.view",
          description: "Просмотр очереди заявок.",
          label: "Видеть очередь тикетов",
          risk: "normal",
        },
        {
          code: "ticket.status.change",
          description: "Запуск разрешенных переходов статуса.",
          label: "Менять статус тикета",
          risk: "normal",
        },
      ],
    },
    {
      code: "automation",
      label: "Автоматизация",
      permissions: [
        {
          code: "admin.forms.publish",
          description: "Публикация каталога форм заявок.",
          label: "Публиковать формы",
          risk: "high",
        },
      ],
    },
  ],
};

const summaryPayload = {
  access_groups: [
    {
      code: "support_l2",
      description: "Вторая линия поддержки",
      group_id: 10,
      is_active: true,
      members: ["support1"],
      name: "Support L2",
      permissions: ["workspace.support.view"],
      queue_grants: [
        {
          queue_code: "helpdesk",
          queue_id: 7,
          queue_name: "Helpdesk L1",
          role_in_queue: "lead",
        },
      ],
    },
    {
      code: "empty_group",
      description: "Нет участников",
      group_id: 11,
      is_active: true,
      members: [],
      name: "Пустая группа",
      permissions: [],
      queue_grants: [],
    },
  ],
  notes: ["Access groups are enabled; effective access is role defaults + group grants + direct queue membership."],
  queues: [
    {
      is_active: true,
      members_count: 1,
      queue_code: "helpdesk",
      queue_id: 7,
      queue_name: "Helpdesk L1",
    },
    {
      is_active: false,
      members_count: 0,
      queue_code: "archive",
      queue_id: 8,
      queue_name: "Archive",
    },
  ],
  users: [
    {
      actor_role: "admin",
      groups: [],
      is_active: true,
      queue_count: 0,
      role_label: "Администратор",
      user_login: "admin1",
    },
    {
      actor_role: "support",
      groups: ["support_l2"],
      is_active: true,
      queue_count: 1,
      role_label: "Поддержка",
      user_login: "support1",
    },
    {
      actor_role: "support",
      groups: ["support_l2"],
      is_active: false,
      queue_count: 1,
      role_label: "Поддержка",
      user_login: "disabled1",
    },
  ],
  version: "rbac-test",
};

const effectivePayloads: Record<string, unknown> = {
  admin1: {
    actor_id: "admin1",
    actor_role: "admin",
    groups: [],
    permissions: ["workspace.admin.view", "workspace.support.view", "admin.access.view", "admin.forms.publish"],
    queues: [],
    role_label: "Администратор",
    sources: { groups: [], queues: [], role: "admin" },
    workspaces: ["admin", "support"],
  },
  disabled1: {
    actor_id: "disabled1",
    actor_role: "support",
    groups: ["support_l2"],
    permissions: ["workspace.support.view", "ticket.queue.view", "ticket.status.change"],
    queues: [
      {
        queue_code: "helpdesk",
        queue_id: 7,
        queue_name: "Helpdesk L1",
        role_in_queue: "lead",
      },
    ],
    role_label: "Поддержка",
    sources: { groups: ["support_l2"], queues: ["helpdesk"], role: "support" },
    workspaces: ["support"],
  },
  support1: {
    actor_id: "support1",
    actor_role: "support",
    groups: ["support_l2"],
    permissions: ["workspace.support.view", "ticket.queue.view", "ticket.status.change"],
    queues: [
      {
        queue_code: "helpdesk",
        queue_id: 7,
        queue_name: "Helpdesk L1",
        role_in_queue: "lead",
      },
    ],
    role_label: "Поддержка",
    sources: { groups: ["support_l2"], queues: ["helpdesk"], role: "support" },
    workspaces: ["support"],
  },
};

function installAccessFetchMock() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url === "/api/web/admin/access/catalog") {
      return jsonResponse({ data: catalogPayload, status: "success" });
    }

    if (url === "/api/web/admin/access/summary") {
      return jsonResponse({ data: summaryPayload, status: "success" });
    }

    if (url.startsWith("/api/web/admin/access/effective")) {
      const parsed = new URL(url, "https://pc-client.local");
      const actorId = parsed.searchParams.get("actor_id") ?? "admin1";
      return jsonResponse({ data: effectivePayloads[actorId], status: "success" });
    }

    if (url === "/api/web/admin/access/audit") {
      return jsonResponse({
        data: {
          items: [
            {
              action: "permissions_updated",
              actor_id: "admin1",
              actor_role: "admin",
              after_json: { permissions: ["workspace.support.view"] },
              before_json: { permissions: [] },
              created_at: "2026-06-14T10:00:00",
              entity_id: "10",
              entity_type: "access_group",
              id: 1,
            },
          ],
        },
        status: "success",
      });
    }

    if (url === "/api/web/admin/access/groups/10/permissions" && init?.method === "PUT") {
      return jsonResponse({
        data: {
          ...summaryPayload.access_groups[0],
          permissions: ["admin.forms.publish", "workspace.support.view"],
        },
        status: "success",
      });
    }

    if (url === "/api/web/admin/access/groups/10/members" && init?.method === "PUT") {
      return jsonResponse({
        data: summaryPayload.access_groups[0],
        status: "success",
      });
    }

    if (url === "/api/web/admin/access/groups/10/queues" && init?.method === "PUT") {
      return jsonResponse({
        data: summaryPayload.access_groups[0],
        status: "success",
      });
    }

    if (url === "/api/web/admin/access/users/support1/password" && init?.method === "POST") {
      return jsonResponse({ data: { updated: true }, status: "success" });
    }

    return jsonResponse({ error: `Unhandled ${url}`, status: "error" }, 500);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("AdminAccessPage", () => {
  it("renders a Russian task-oriented workspace with internal navigation and overview audit cards", async () => {
    installAccessFetchMock();

    renderAccessPage();

    expect(await screen.findByRole("heading", { name: "Контроль доступа" })).toBeInTheDocument();
    expect(screen.getByText("Базовая роль + группы доступа + прямое членство в очередях = итоговый доступ")).toBeInTheDocument();
    expect(screen.getByText("rbac-test")).toBeInTheDocument();
    expect(screen.getByText("Отключённые пользователи с доступом")).toBeInTheDocument();
    expect(screen.getByText("Группы без участников")).toBeInTheDocument();
    expect(screen.getByText("Очереди без участников")).toBeInTheDocument();

    for (const tab of ["Обзор", "Пользователи", "Группы", "Очереди", "Роли", "Каталог прав", "Аудит"]) {
      expect(screen.getByRole("button", { name: new RegExp(tab) })).toBeInTheDocument();
    }

    fireEvent.click(screen.getByRole("button", { name: /Пользователи/ }));
    expect(await screen.findByRole("heading", { name: "Пользователи" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Роли/ }));
    expect(await screen.findByRole("heading", { name: "Матрица ролей" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Аудит/ }));
    expect(await screen.findByRole("heading", { name: "Аудит и журнал изменений" })).toBeInTheDocument();
  });

  it("searches users, opens effective access and shows permission source with technical codes second", async () => {
    const fetchMock = installAccessFetchMock();

    renderAccessPage();

    fireEvent.click(await screen.findByRole("button", { name: /Пользователи/ }));
    fireEvent.change(screen.getByPlaceholderText("Логин, имя, email или роль"), { target: { value: "support1" } });

    expect(screen.getAllByText("support1").length).toBeGreaterThan(0);
    expect(screen.queryByText("admin1")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Открыть доступ support1/ }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/admin/access/effective?actor_id=support1&actor_role=support",
        expect.objectContaining({ credentials: "same-origin" }),
      );
    });

    expect(await screen.findByRole("heading", { name: "Эффективный доступ" })).toBeInTheDocument();
    expect(screen.getByText("Почему есть доступ")).toBeInTheDocument();
    expect(screen.getByText((_, element) => element?.textContent === "Роль: Поддержка")).toBeInTheDocument();
    expect(screen.getByText((_, element) => element?.textContent === "Группа: support_l2")).toBeInTheDocument();
    expect(screen.getByText("Открывать поддержку")).toBeInTheDocument();
    expect(screen.getByText("workspace.support.view")).toBeInTheDocument();
    expect(screen.getByText("Источник: роль + группа")).toBeInTheDocument();
  });

  it("changes a user password without requesting or showing the current password", async () => {
    const fetchMock = installAccessFetchMock();

    renderAccessPage();

    fireEvent.click(await screen.findByRole("button", { name: /Пользователи/ }));
    fireEvent.change(screen.getByPlaceholderText("Логин, имя, email или роль"), { target: { value: "support1" } });
    fireEvent.click(screen.getByRole("button", { name: "Сменить пароль support1" }));

    const dialog = await screen.findByRole("dialog", { name: "Сменить пароль" });
    expect(within(dialog).getByText("support1")).toBeInTheDocument();
    expect(within(dialog).queryByLabelText(/Текущий пароль/i)).not.toBeInTheDocument();
    expect(within(dialog).queryByText(/Текущий пароль/i)).not.toBeInTheDocument();

    fireEvent.change(within(dialog).getByLabelText("Новый пароль"), { target: { value: "StrongReset123!" } });
    fireEvent.change(within(dialog).getByLabelText("Повторите пароль"), { target: { value: "StrongReset123!" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Сохранить пароль" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/admin/access/users/support1/password",
        expect.objectContaining({
          body: JSON.stringify({ password: "StrongReset123!" }),
          credentials: "same-origin",
          method: "POST",
        }),
      );
    });

    const passwordRequest = fetchMock.mock.calls.find(([url]) => String(url) === "/api/web/admin/access/users/support1/password");
    expect(String(passwordRequest?.[1]?.body ?? "")).not.toContain("current_password");
    expect(await screen.findByText("Пароль обновлён")).toBeInTheDocument();
  });

  it("groups permissions, tracks pending group edits, previews diff and requires high-risk confirmation before save", async () => {
    const fetchMock = installAccessFetchMock();

    renderAccessPage();

    fireEvent.click(await screen.findByRole("button", { name: /Группы/ }));
    expect(await screen.findByRole("heading", { name: "Группы доступа" })).toBeInTheDocument();
    expect(screen.getByText("Автоматизация")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText(/Публиковать формы/));
    expect(screen.getByText("Есть несохранённые изменения")).toBeInTheDocument();
    expect(screen.getByText("admin.forms.publish")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Отменить" }));
    expect(screen.queryByText("Есть несохранённые изменения")).not.toBeInTheDocument();
    expect(screen.getByLabelText(/Публиковать формы/)).not.toBeChecked();

    fireEvent.click(screen.getByLabelText(/Публиковать формы/));
    fireEvent.click(screen.getByRole("button", { name: "Сохранить изменения" }));

    expect(await screen.findByRole("dialog", { name: "Проверка изменений" })).toBeInTheDocument();
    expect(screen.getByText("Будет добавлено")).toBeInTheDocument();
    expect(screen.getByText("Требуется подтверждение риска")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Применить изменения" })).toBeDisabled();

    fireEvent.click(screen.getByLabelText("Подтверждаю добавление высокорисковых прав"));
    fireEvent.click(screen.getByRole("button", { name: "Применить изменения" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/admin/access/groups/10/permissions",
        expect.objectContaining({
          body: JSON.stringify({ permissions: ["admin.forms.publish", "workspace.support.view"] }),
          method: "PUT",
        }),
      );
    });
    expect(await screen.findByText("Изменения сохранены")).toBeInTheDocument();
  });

  it("answers queue access, searches permission catalog, and renders audit data without fake records", async () => {
    installAccessFetchMock();

    renderAccessPage();

    fireEvent.click(await screen.findByRole("button", { name: /Очереди/ }));
    expect(await screen.findByRole("heading", { name: "Очереди" })).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("Поиск очереди"), { target: { value: "helpdesk" } });
    fireEvent.click(screen.getByRole("button", { name: /Открыть очередь Helpdesk L1/ }));
    expect(screen.getByText("Кто может попасть в очередь")).toBeInTheDocument();
    expect(screen.getByText("Support L2")).toBeInTheDocument();
    expect(screen.getByText("Из API доступно только количество прямых участников, без списка логинов.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Каталог прав/ }));
    expect(await screen.findByRole("heading", { name: "Каталог прав" })).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("Поиск права или кода"), { target: { value: "forms" } });
    expect(screen.getByText("Публиковать формы")).toBeInTheDocument();
    expect(screen.queryByText("Видеть очередь тикетов")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Аудит/ }));
    expect(await screen.findByText("permissions_updated")).toBeInTheDocument();
    expect(screen.getByText("access_group 10")).toBeInTheDocument();
  });

  it("renders loading, empty and error states for the RBAC workspace", async () => {
    let resolveCatalog: (value: Response) => void = () => undefined;
    const catalogPromise = new Promise<Response>((resolve) => {
      resolveCatalog = resolve;
    });
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/web/admin/access/catalog") {
        return catalogPromise;
      }
      if (url === "/api/web/admin/access/summary") {
        return jsonResponse({
          data: { ...summaryPayload, access_groups: [], queues: [], users: [] },
          status: "success",
        });
      }
      if (url === "/api/web/admin/access/audit") {
        return jsonResponse({ data: { items: [] }, status: "success" });
      }
      return jsonResponse({ error: `Unhandled ${url}`, status: "error" }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { unmount } = renderAccessPage();
    expect(screen.getByText("Загружаем RBAC")).toBeInTheDocument();
    resolveCatalog(jsonResponse({ data: catalogPayload, status: "success" }));
    fireEvent.click(await screen.findByRole("button", { name: /Пользователи/ }));
    expect(await screen.findByText("Пользователей нет")).toBeInTheDocument();
    unmount();

    vi.unstubAllGlobals();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/web/admin/access/catalog") {
          return jsonResponse({ error: "catalog unavailable", status: "error" }, 500);
        }
        return jsonResponse({ data: summaryPayload, status: "success" });
      }),
    );

    renderAccessPage();
    expect(await screen.findByText("RBAC недоступен")).toBeInTheDocument();
    expect(screen.getByText("catalog unavailable")).toBeInTheDocument();
  });

  it("does not expose raw JSON editing in the access-control workspace", async () => {
    installAccessFetchMock();

    const { container } = renderAccessPage();

    expect(await screen.findByRole("heading", { name: "Контроль доступа" })).toBeInTheDocument();
    expect(container.querySelector("textarea")).not.toBeInTheDocument();
    expect(within(document.body).queryByText("raw JSON")).not.toBeInTheDocument();
  });
});
