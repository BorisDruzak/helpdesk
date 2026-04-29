import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AdminAccessPage } from "./access-page";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

function renderAccessPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <AdminAccessPage />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("AdminAccessPage", () => {
  it("renders RBAC catalog, users, queues and effective access without JSON editing", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url === "/api/web/admin/access/catalog") {
        return jsonResponse({
          status: "success",
          data: {
            version: "rbac-test",
            roles: [
              {
                code: "admin",
                label: "Администратор",
                permissions: ["workspace.admin.view", "workspace.support.view", "admin.access.view"],
              },
              {
                code: "support",
                label: "Поддержка",
                permissions: ["workspace.support.view", "ticket.queue.view", "ticket.status.change"],
              },
            ],
            groups: [
              {
                code: "workspaces",
                label: "Рабочие области",
                permissions: [
                  {
                    code: "workspace.admin.view",
                    label: "Видеть admin workspace",
                    description: "Доступ к административной рабочей области.",
                    risk: "normal",
                  },
                  {
                    code: "workspace.support.view",
                    label: "Видеть support workspace",
                    description: "Доступ к операторской рабочей области.",
                    risk: "normal",
                  },
                ],
              },
              {
                code: "tickets",
                label: "Тикеты",
                permissions: [
                  {
                    code: "ticket.status.change",
                    label: "Менять статус тикета",
                    description: "Разрешённые FSM-переходы.",
                    risk: "normal",
                  },
                ],
              },
            ],
          },
        });
      }

      if (url === "/api/web/admin/access/summary") {
        return jsonResponse({
          status: "success",
          data: {
            version: "rbac-test",
            users: [
              {
                user_login: "admin1",
                actor_role: "admin",
                role_label: "Администратор",
                is_active: true,
                groups: [],
                queue_count: 0,
              },
              {
                user_login: "support1",
                actor_role: "support",
                role_label: "Поддержка",
                is_active: true,
                groups: [],
                queue_count: 2,
              },
            ],
            queues: [
              {
                queue_id: 1,
                queue_code: "helpdesk",
                queue_name: "Helpdesk L1",
                is_active: true,
                members_count: 2,
              },
            ],
            access_groups: [],
            notes: ["Access groups are planned as the next RBAC slice."],
          },
        });
      }

      if (url === "/api/web/admin/access/effective?actor_id=admin1&actor_role=admin") {
        return jsonResponse({
          status: "success",
          data: {
            actor_id: "admin1",
            actor_role: "admin",
            role_label: "Администратор",
            permissions: ["workspace.admin.view", "workspace.support.view", "admin.access.view"],
            workspaces: ["admin", "support"],
            groups: [],
            queues: [],
            sources: {
              role: "admin",
              groups: [],
              queues: [],
            },
          },
        });
      }

      if (url === "/api/web/admin/access/effective?actor_id=support1&actor_role=support") {
        return jsonResponse({
          status: "success",
          data: {
            actor_id: "support1",
            actor_role: "support",
            role_label: "Поддержка",
            permissions: ["workspace.support.view", "ticket.queue.view", "ticket.status.change"],
            workspaces: ["support"],
            groups: [],
            queues: [
              {
                queue_id: 1,
                queue_code: "helpdesk",
                queue_name: "Helpdesk L1",
                role_in_queue: "primary",
              },
            ],
            sources: {
              role: "support",
              groups: [],
              queues: ["helpdesk"],
            },
          },
        });
      }

      return jsonResponse({ status: "error", error: `Unhandled ${url}` }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { container } = renderAccessPage();

    expect(await screen.findByRole("heading", { name: "Access Control" })).toBeInTheDocument();
    expect(await screen.findByText("rbac-test")).toBeInTheDocument();
    expect(await screen.findByText("Администратор")).toBeInTheDocument();
    expect(await screen.findByText("Поддержка")).toBeInTheDocument();
    expect(await screen.findByText("Helpdesk L1")).toBeInTheDocument();
    expect(await screen.findByText("Менять статус тикета")).toBeInTheDocument();
    expect((await screen.findAllByText("admin.access.view")).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: /support1/ }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/admin/access/effective?actor_id=support1&actor_role=support",
        expect.objectContaining({ credentials: "same-origin" }),
      );
    });

    expect((await screen.findAllByText("workspace.support.view")).length).toBeGreaterThan(0);
    expect(await screen.findByText("primary")).toBeInTheDocument();
    expect(container.querySelector("textarea")).not.toBeInTheDocument();
  });

  it("creates access groups and saves grants through controlled inputs", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);

      if (url === "/api/web/admin/access/catalog") {
        return jsonResponse({
          status: "success",
          data: {
            version: "rbac-test",
            roles: [],
            groups: [
              {
                code: "automation",
                label: "Автоматизация",
                permissions: [
                  {
                    code: "admin.forms.publish",
                    label: "Публиковать формы",
                    description: "Сохранение каталога форм.",
                    risk: "high",
                  },
                ],
              },
            ],
          },
        });
      }

      if (url === "/api/web/admin/access/summary") {
        return jsonResponse({
          status: "success",
          data: {
            version: "rbac-test",
            users: [
              {
                user_login: "support1",
                actor_role: "support",
                role_label: "Поддержка",
                is_active: true,
                groups: [],
                queue_count: 0,
              },
            ],
            queues: [
              {
                queue_id: 7,
                queue_code: "helpdesk",
                queue_name: "Helpdesk L1",
                is_active: true,
                members_count: 1,
              },
            ],
            access_groups: [],
            notes: [],
          },
        });
      }

      if (url === "/api/web/admin/access/effective?actor_id=support1&actor_role=support") {
        return jsonResponse({
          status: "success",
          data: {
            actor_id: "support1",
            actor_role: "support",
            role_label: "Поддержка",
            permissions: ["workspace.support.view"],
            workspaces: ["support"],
            groups: [],
            queues: [],
            sources: { role: "support", groups: [], queues: [] },
          },
        });
      }

      if (url === "/api/web/admin/access/groups" && init?.method === "POST") {
        return jsonResponse({
          status: "success",
          data: {
            group_id: 10,
            code: "support_l2",
            name: "Support L2",
            description: "Second line",
            is_active: true,
            permissions: [],
            members: [],
            queue_grants: [],
          },
        });
      }

      if (url === "/api/web/admin/access/groups/10/permissions" && init?.method === "PUT") {
        return jsonResponse({
          status: "success",
          data: {
            group_id: 10,
            code: "support_l2",
            name: "Support L2",
            description: "Second line",
            is_active: true,
            permissions: ["admin.forms.publish"],
            members: [],
            queue_grants: [],
          },
        });
      }

      if (url === "/api/web/admin/access/groups/10/members" && init?.method === "PUT") {
        return jsonResponse({
          status: "success",
          data: {
            group_id: 10,
            code: "support_l2",
            name: "Support L2",
            description: "Second line",
            is_active: true,
            permissions: ["admin.forms.publish"],
            members: ["support1"],
            queue_grants: [],
          },
        });
      }

      if (url === "/api/web/admin/access/groups/10/queues" && init?.method === "PUT") {
        return jsonResponse({
          status: "success",
          data: {
            group_id: 10,
            code: "support_l2",
            name: "Support L2",
            description: "Second line",
            is_active: true,
            permissions: ["admin.forms.publish"],
            members: ["support1"],
            queue_grants: [
              {
                queue_id: 7,
                queue_code: "helpdesk",
                queue_name: "Helpdesk L1",
                role_in_queue: "lead",
              },
            ],
          },
        });
      }

      return jsonResponse({ status: "error", error: `Unhandled ${url}` }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { container } = renderAccessPage();

    expect(await screen.findByRole("heading", { name: "Access Control" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Код группы"), { target: { value: "support_l2" } });
    fireEvent.change(screen.getByLabelText("Название группы"), { target: { value: "Support L2" } });
    fireEvent.change(screen.getByLabelText("Описание группы"), { target: { value: "Second line" } });
    fireEvent.click(screen.getByRole("button", { name: "Создать группу" }));

    expect((await screen.findAllByText("support_l2")).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByLabelText(/Публиковать формы/));
    fireEvent.click(screen.getByLabelText(/support1/));
    fireEvent.click(screen.getAllByLabelText(/Helpdesk L1/)[0]);
    fireEvent.change(screen.getByLabelText(/Роль в очереди Helpdesk L1/), { target: { value: "lead" } });

    fireEvent.click(screen.getByRole("button", { name: "Сохранить permissions" }));
    fireEvent.click(screen.getByRole("button", { name: "Сохранить участников" }));
    fireEvent.click(screen.getByRole("button", { name: "Сохранить очереди" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/admin/access/groups/10/permissions",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({ permissions: ["admin.forms.publish"] }),
        }),
      );
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/admin/access/groups/10/members",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({ actor_ids: ["support1"] }),
        }),
      );
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/admin/access/groups/10/queues",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({ queues: [{ queue_id: 7, role_in_queue: "lead" }] }),
        }),
      );
    });

    expect(container.querySelector("textarea")).not.toBeInTheDocument();
  });
});
