import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SupportTicketDetailPayload } from "./api";
import { SupportWorkspace } from "./support-workspace";

const ticketRealtimeListeners = new Map<string, Set<(message: { ticketId: string }) => void>>();

const realtimeClientMock = {
  subscribeTicket: vi.fn((ticketId: string, listener: (message: { ticketId: string }) => void) => {
    const listeners = ticketRealtimeListeners.get(ticketId) ?? new Set<(message: { ticketId: string }) => void>();
    listeners.add(listener);
    ticketRealtimeListeners.set(ticketId, listeners);
    return () => {
      listeners.delete(listener);
      if (listeners.size === 0) {
        ticketRealtimeListeners.delete(ticketId);
      }
    };
  }),
  subscribeDevice: vi.fn(() => () => {}),
  dispose: vi.fn(),
};

vi.mock("../../shared/realtime/client", () => ({
  getSharedWebRealtimeClient: () => realtimeClientMock,
}));


function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json"
    }
  });
}


afterEach(() => {
  ticketRealtimeListeners.clear();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});


function emitTicketRealtime(ticketId: string) {
  const listeners = ticketRealtimeListeners.get(ticketId);
  if (!listeners) {
    return;
  }
  for (const listener of listeners) {
    listener({
      ticketId,
    });
  }
}


function renderSupportWorkspace() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false
      }
    }
  });

  render(
    <QueryClientProvider client={queryClient}>
      <SupportWorkspace />
    </QueryClientProvider>
  );
}


describe("SupportWorkspace", () => {
  it("не пересоздаёт realtime-подписки на всю очередь при refetch с теми же тикетами", async () => {
    let queueRevision = 0;
    let detailRevision = 0;

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);

        if (url === "/api/web/support/bootstrap") {
          return jsonResponse({
            status: "success",
            data: {
              workspace: "support",
              features: ["queue_overview", "ticket_workspace", "observer_trace", "tool_actions"],
              observer: {
                ticket_summary_endpoint: "/api/tickets/{ticket_id}/observer",
                drawer_tab: "trace",
              },
            },
          });
        }

        if (url.startsWith("/api/web/support/queue")) {
          queueRevision += 1;
          const tickets =
            queueRevision === 1
              ? [
                  {
                    ticket_id: "ticket-1",
                    ticket_code: "T-100001",
                    title: "Первый тикет",
                    status: "new",
                    status_label: "Новая",
                    queue_code: "servicedesk_l1",
                    assignee_id: null,
                    requester_display_name: "Алексей",
                    device_id: "device-1",
                    updated_at: "2026-04-20T08:10:00+05:00",
                    created_at: "2026-04-20T07:55:00+05:00",
                    requires_operator_action: true,
                    unread_user_messages: 1,
                  },
                  {
                    ticket_id: "ticket-2",
                    ticket_code: "T-100002",
                    title: "Второй тикет",
                    status: "new",
                    status_label: "Новая",
                    queue_code: "servicedesk_l1",
                    assignee_id: "support-2",
                    requester_display_name: "Марина",
                    device_id: "device-2",
                    updated_at: "2026-04-20T08:09:00+05:00",
                    created_at: "2026-04-20T07:40:00+05:00",
                    requires_operator_action: true,
                    unread_user_messages: 1,
                  },
                ]
              : [
                  {
                    ticket_id: "ticket-2",
                    ticket_code: "T-100002",
                    title: "Второй тикет",
                    status: "new",
                    status_label: "Новая",
                    queue_code: "servicedesk_l1",
                    assignee_id: "support-2",
                    requester_display_name: "Марина",
                    device_id: "device-2",
                    updated_at: "2026-04-20T08:11:00+05:00",
                    created_at: "2026-04-20T07:40:00+05:00",
                    requires_operator_action: true,
                    unread_user_messages: 2,
                  },
                  {
                    ticket_id: "ticket-1",
                    ticket_code: "T-100001",
                    title: "Первый тикет",
                    status: "new",
                    status_label: "Новая",
                    queue_code: "servicedesk_l1",
                    assignee_id: null,
                    requester_display_name: "Алексей",
                    device_id: "device-1",
                    updated_at: "2026-04-20T08:12:00+05:00",
                    created_at: "2026-04-20T07:55:00+05:00",
                    requires_operator_action: true,
                    unread_user_messages: 2,
                  },
                ];

          return jsonResponse({
            status: "success",
            data: {
              scope: "all",
              query: "",
              status_filter: "all",
              summary: {
                visible_count: 2,
                selected_ticket_id: "ticket-1",
              },
              filters: {
                scope_options: [
                  { value: "all", label: "Все доступные" },
                  { value: "mine", label: "Только мои" },
                ],
                status_options: [{ value: "all", label: "Все статусы" }],
              },
              tickets,
            },
          });
        }

        if (url === "/api/web/support/tickets/ticket-1") {
          detailRevision += 1;
          return jsonResponse({
            status: "success",
            data: {
              ticket: {
                ticket_id: "ticket-1",
                ticket_code: "T-100001",
                title: "Первый тикет",
                description: "Проверяем стабильность подписок.",
                status: "new",
                status_label: "Новая",
                requester_display_name: "Алексей",
                device_id: "device-1",
                queue: {
                  id: 11,
                  code: "servicedesk_l1",
                  name: "ServiceDesk L1",
                },
                assignee_id: null,
                updated_at: "2026-04-20T08:10:00+05:00",
                created_at: "2026-04-20T07:55:00+05:00",
                queue_members: [],
              },
              observer: {
                ticket_summary_endpoint: "/api/tickets/ticket-1/observer",
                summary: {
                  ticket_id: "ticket-1",
                  root_trace_id: "trace-support-root",
                  trace_count: 1,
                  active_trace_count: 1,
                  error_trace_count: 0,
                  signature_count: 0,
                  latest_trace_at: "2026-04-20T08:09:00+05:00",
                },
              },
              timeline: [
                {
                  message_id: `msg-${detailRevision}`,
                  event_id: detailRevision,
                  event_type: "chat_message",
                  from_role: "support",
                  sender_display_name: "Оператор",
                  text:
                    detailRevision === 1
                      ? "Первое сообщение в ленте."
                      : "После refetch лента обновилась без лишних подписок.",
                  ts: "2026-04-20T08:11:00+05:00",
                  visibility: "public",
                  direction: "from_support",
                  attachments: [],
                  reply_to: null,
                },
              ],
              snapshot: {
                last_event_id: detailRevision,
                notification_unread: 0,
                presence: {
                  requester_online: true,
                  support_online: true,
                  agent_online: true,
                },
                device: {
                  device_id: "device-1",
                  hostname: "WS-01",
                  os: "Windows 11",
                  agent_version: "2.4.0",
                  last_seen_at: "2026-04-20T08:10:00+05:00",
                  online: true,
                },
                latest_operations: [],
              },
              actions: {
                status_options: [],
                can_send_internal_note: true,
              },
            },
          });
        }

        if (url === "/api/web/support/tickets/ticket-1/tools") {
          return jsonResponse({
            status: "success",
            data: {
              ticket_id: "ticket-1",
              device_id: "device-1",
              tools: [],
            },
          });
        }

        return jsonResponse({ status: "error", error: `Unhandled URL: ${url}` }, 404);
      })
    );

    renderSupportWorkspace();

    expect(await screen.findByText("Первое сообщение в ленте.")).toBeInTheDocument();
    const initialSubscribeCalls = realtimeClientMock.subscribeTicket.mock.calls.length;

    emitTicketRealtime("ticket-1");

    await waitFor(() => {
      expect(screen.getByText("После refetch лента обновилась без лишних подписок.")).toBeInTheDocument();
    });

    expect(realtimeClientMock.subscribeTicket.mock.calls.length).toBe(initialSubscribeCalls);
  });

  it("refetches queue and ticket detail when realtime bridge reports a ticket event", async () => {
    let detailRevision = 0;

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);

        if (url === "/api/web/support/bootstrap") {
          return jsonResponse({
            status: "success",
            data: {
              workspace: "support",
              features: ["queue_overview", "ticket_workspace", "observer_trace", "tool_actions"],
              observer: {
                ticket_summary_endpoint: "/api/tickets/{ticket_id}/observer",
                drawer_tab: "trace",
              },
            },
          });
        }

        if (url.startsWith("/api/web/support/queue")) {
          return jsonResponse({
            status: "success",
            data: {
              scope: "all",
              query: "",
              status_filter: "all",
              summary: {
                visible_count: 1,
                selected_ticket_id: "ticket-1",
              },
              filters: {
                scope_options: [
                  { value: "all", label: "Все доступные" },
                  { value: "mine", label: "Только мои" },
                ],
                status_options: [{ value: "all", label: "Все статусы" }],
              },
              tickets: [
                {
                  ticket_id: "ticket-1",
                  ticket_code: "T-100001",
                  title: "Сбой синхронизации",
                  status: "new",
                  status_label: "Новая",
                  queue_code: "servicedesk_l1",
                  assignee_id: null,
                  requester_display_name: "Алексей",
                  device_id: "device-1",
                  updated_at: "2026-04-20T08:10:00+05:00",
                  created_at: "2026-04-20T07:55:00+05:00",
                  requires_operator_action: true,
                  unread_user_messages: 1,
                },
              ],
            },
          });
        }

        if (url === "/api/web/support/tickets/ticket-1") {
          detailRevision += 1;
          return jsonResponse({
            status: "success",
            data: {
              ticket: {
                ticket_id: "ticket-1",
                ticket_code: "T-100001",
                title: "Сбой синхронизации",
                description: "Нужно переподключить агента и проверить канал.",
                status: "new",
                status_label: "Новая",
                requester_display_name: "Алексей",
                device_id: "device-1",
                queue: {
                  id: 11,
                  code: "servicedesk_l1",
                  name: "ServiceDesk L1",
                },
                assignee_id: null,
                updated_at: "2026-04-20T08:10:00+05:00",
                created_at: "2026-04-20T07:55:00+05:00",
                queue_members: [],
              },
              observer: {
                ticket_summary_endpoint: "/api/tickets/ticket-1/observer",
                summary: {
                  ticket_id: "ticket-1",
                  root_trace_id: "trace-support-root",
                  trace_count: 3,
                  active_trace_count: 1,
                  error_trace_count: 1,
                  signature_count: 1,
                  latest_trace_at: "2026-04-20T08:09:00+05:00",
                },
              },
              timeline: [
                {
                  message_id: `msg-${detailRevision}`,
                  event_id: detailRevision,
                  event_type: "chat_message",
                  from_role: "support",
                  sender_display_name: "Оператор",
                  text:
                    detailRevision === 1
                      ? "Первичный ответ в ленте."
                      : "В ленту пришло новое сообщение по realtime.",
                  ts: "2026-04-20T08:11:00+05:00",
                  visibility: "public",
                  direction: "from_support",
                  attachments: [],
                  reply_to: null,
                },
              ],
              snapshot: {
                last_event_id: detailRevision,
                notification_unread: 0,
                presence: {
                  requester_online: true,
                  support_online: true,
                  agent_online: true,
                },
                device: {
                  device_id: "device-1",
                  hostname: "WS-01",
                  os: "Windows 11",
                  agent_version: "2.4.0",
                  last_seen_at: "2026-04-20T08:10:00+05:00",
                  online: true,
                },
                latest_operations: [],
              },
              actions: {
                status_options: [],
                can_send_internal_note: true,
              },
            },
          });
        }

        if (url === "/api/web/support/tickets/ticket-1/tools") {
          return jsonResponse({
            status: "success",
            data: {
              ticket_id: "ticket-1",
              device_id: "device-1",
              tools: [],
            },
          });
        }

        return jsonResponse({ status: "error", error: `Unhandled URL: ${url}` }, 404);
      })
    );

    renderSupportWorkspace();

    expect(await screen.findByText("Первичный ответ в ленте.")).toBeInTheDocument();

    emitTicketRealtime("ticket-1");

    await waitFor(() => {
      expect(screen.getByText("В ленту пришло новое сообщение по realtime.")).toBeInTheDocument();
    });
  });

  it("renders queue data and lets the operator switch selected ticket", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);

        if (url === "/api/web/support/bootstrap") {
          return jsonResponse({
            status: "success",
            data: {
              workspace: "support",
              features: [
                "queue_overview",
                "ticket_workspace",
                "observer_trace",
                "tool_actions"
              ],
              observer: {
                ticket_summary_endpoint: "/api/tickets/{ticket_id}/observer",
                drawer_tab: "trace"
              }
            }
          });
        }

        if (url.startsWith("/api/web/support/queue")) {
          return jsonResponse({
            status: "success",
            data: {
              scope: "all",
              query: "",
              status_filter: "all",
              summary: {
                visible_count: 2,
                selected_ticket_id: "ticket-1"
              },
              filters: {
                scope_options: [
                  { value: "all", label: "Все доступные" },
                  { value: "mine", label: "Только мои" }
                ],
                status_options: [
                  { value: "all", label: "Все статусы" },
                  { value: "new", label: "Новые" }
                ]
              },
              tickets: [
                {
                  ticket_id: "ticket-1",
                  ticket_code: "T-100001",
                  title: "Сбой синхронизации",
                  status: "new",
                  status_label: "Новая",
                  queue_code: "servicedesk_l1",
                  assignee_id: null,
                  requester_display_name: "Алексей",
                  device_id: "device-1",
                  updated_at: "2026-04-20T08:10:00+05:00",
                  created_at: "2026-04-20T07:55:00+05:00",
                  requires_operator_action: true,
                  unread_user_messages: 2
                },
                {
                  ticket_id: "ticket-2",
                  ticket_code: "T-100002",
                  title: "Принтер не отвечает",
                  status: "new",
                  status_label: "Новая",
                  queue_code: "office",
                  assignee_id: "support-2",
                  requester_display_name: "Марина",
                  device_id: "device-2",
                  updated_at: "2026-04-20T08:05:00+05:00",
                  created_at: "2026-04-20T07:40:00+05:00",
                  requires_operator_action: true,
                  unread_user_messages: 1
                }
              ]
            }
          });
        }

        if (url === "/api/web/support/tickets/ticket-1") {
          return jsonResponse({
            status: "success",
            data: {
              ticket: {
                ticket_id: "ticket-1",
                ticket_code: "T-100001",
                title: "Сбой синхронизации",
                description: "Нужно переподключить агент и проверить канал.",
                status: "new",
                status_label: "Новая",
                requester_display_name: "Алексей",
                device_id: "device-1",
                queue: {
                  id: 11,
                  code: "servicedesk_l1",
                  name: "ServiceDesk L1"
                },
                assignee_id: null,
                updated_at: "2026-04-20T08:10:00+05:00",
                created_at: "2026-04-20T07:55:00+05:00",
                queue_members: [
                  { actor_id: "support-1", role_in_queue: null }
                ]
              },
              observer: {
                ticket_summary_endpoint: "/api/tickets/ticket-1/observer",
                summary: {
                  ticket_id: "ticket-1",
                  trace_count: 3,
                  active_trace_count: 1,
                  error_trace_count: 1,
                  signature_count: 1,
                  latest_trace_at: "2026-04-20T08:09:00+05:00"
                }
              }
            }
          });
        }

        if (url === "/api/web/support/tickets/ticket-2") {
          return jsonResponse({
            status: "success",
            data: {
              ticket: {
                ticket_id: "ticket-2",
                ticket_code: "T-100002",
                title: "Принтер не отвечает",
                description: "Заявка уже назначена и ждёт удалённой диагностики.",
                status: "new",
                status_label: "Новая",
                requester_display_name: "Марина",
                device_id: "device-2",
                queue: {
                  id: 15,
                  code: "office",
                  name: "Офис"
                },
                assignee_id: "support-2",
                updated_at: "2026-04-20T08:05:00+05:00",
                created_at: "2026-04-20T07:40:00+05:00",
                queue_members: [
                  { actor_id: "support-2", role_in_queue: "owner" }
                ]
              },
              observer: {
                ticket_summary_endpoint: "/api/tickets/ticket-2/observer",
                summary: {
                  ticket_id: "ticket-2",
                  trace_count: 1,
                  active_trace_count: 0,
                  error_trace_count: 0,
                  signature_count: 0,
                  latest_trace_at: null
                }
              }
            }
          });
        }

        return jsonResponse({ status: "error", error: `Unhandled URL: ${url}` }, 404);
      })
    );

    renderSupportWorkspace();

    expect(await screen.findByRole("heading", { name: "Рабочее место поддержки" })).toBeInTheDocument();
    expect(await screen.findByText("Сбой синхронизации")).toBeInTheDocument();
    expect(await screen.findByText("Нужно переподключить агент и проверить канал.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /T-100002/i }));

    await waitFor(() => {
      expect(screen.getByText("Заявка уже назначена и ждёт удалённой диагностики.")).toBeInTheDocument();
    });
    expect(screen.getByText("/api/tickets/ticket-2/observer")).toBeInTheDocument();
  });

  it("renders the message timeline and lets the operator send a reply and change status", async () => {
    let currentDetail: SupportTicketDetailPayload = {
      ticket: {
        ticket_id: "ticket-1",
        ticket_code: "T-100001",
        title: "Сбой синхронизации",
        description: "Нужно переподключить агент и проверить канал.",
        status: "new",
        status_label: "Новая",
        requester_display_name: "Алексей",
        device_id: "device-1",
        queue: {
          id: 11,
          code: "servicedesk_l1",
          name: "ServiceDesk L1"
        },
        assignee_id: null,
        updated_at: "2026-04-20T08:10:00+05:00",
        created_at: "2026-04-20T07:55:00+05:00",
        queue_members: [
          { actor_id: "support-1", role_in_queue: null }
        ]
      },
      observer: {
        ticket_summary_endpoint: "/api/tickets/ticket-1/observer",
        summary: {
          ticket_id: "ticket-1",
          trace_count: 3,
          active_trace_count: 1,
          error_trace_count: 1,
          signature_count: 1,
          latest_trace_at: "2026-04-20T08:09:00+05:00"
        }
      },
      timeline: [
        {
          message_id: "msg-user-1",
          event_id: 101,
          event_type: "chat_message",
          from_role: "user",
          sender_display_name: "Алексей",
          text: "Пользователь пишет, что ошибка повторяется.",
          ts: "2026-04-20T08:12:00+05:00",
          visibility: "public",
          direction: "to_agent",
          attachments: [],
          reply_to: null,
          tool_name: null,
          tool_status: null,
          result_summary: null,
          result_preview: null
        }
      ],
      snapshot: {
        last_event_id: 101,
        notification_unread: 0,
        presence: {
          requester_online: false,
          support_online: true,
          agent_online: false
        },
        device: {
          device_id: "device-1",
          hostname: "ws-01",
          os: "Windows 11",
          agent_version: "1.2.3",
          last_seen_at: "2026-04-20T08:11:00+05:00",
          online: false
        },
        latest_operations: [
          {
            operation_id: "op-1",
            kind: "run_tool",
            status: "succeeded",
            tool_name: "network.diagnostics",
            command_name: null,
            queued_at: "2026-04-20T08:00:00+05:00",
            finished_at: "2026-04-20T08:01:00+05:00",
            result_summary: "Проверка завершена",
            error_message: null
          }
        ]
      },
      actions: {
        status_options: [
          { value: "in_progress", label: "Взять в работу" },
          { value: "waiting_on_user", label: "Ждём пользователя" },
          { value: "resolved", label: "Решено" }
        ],
        can_send_internal_note: true
      }
    };

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";

      if (url === "/api/web/support/bootstrap") {
        return jsonResponse({
          status: "success",
          data: {
            workspace: "support",
            features: [
              "queue_overview",
              "ticket_workspace",
              "observer_trace",
              "tool_actions"
            ],
            observer: {
              ticket_summary_endpoint: "/api/tickets/{ticket_id}/observer",
              drawer_tab: "trace"
            }
          }
        });
      }

      if (url.startsWith("/api/web/support/queue")) {
        return jsonResponse({
          status: "success",
          data: {
            scope: "all",
            query: "",
            status_filter: "all",
            summary: {
              visible_count: 1,
              selected_ticket_id: "ticket-1"
            },
            filters: {
              scope_options: [
                { value: "all", label: "Все доступные" },
                { value: "mine", label: "Только мои" }
              ],
              status_options: [
                { value: "all", label: "Все статусы" },
                { value: "new", label: "Новые" },
                { value: "in_progress", label: "В работе" }
              ]
            },
            tickets: [
              {
                ticket_id: "ticket-1",
                ticket_code: "T-100001",
                title: "Сбой синхронизации",
                status: currentDetail.ticket.status,
                status_label: currentDetail.ticket.status_label,
                queue_code: "servicedesk_l1",
                assignee_id: null,
                requester_display_name: "Алексей",
                device_id: "device-1",
                updated_at: "2026-04-20T08:10:00+05:00",
                created_at: "2026-04-20T07:55:00+05:00",
                requires_operator_action: true,
                unread_user_messages: 2
              }
            ]
          }
        });
      }

      if (url === "/api/web/support/tickets/ticket-1" && method === "GET") {
        return jsonResponse({
          status: "success",
          data: currentDetail
        });
      }

      if (url === "/api/web/support/tickets/ticket-1/messages" && method === "POST") {
        currentDetail = {
          ...currentDetail,
          timeline: [
            {
              message_id: "msg-support-2",
              event_id: 102,
              event_type: "chat_message",
              from_role: "support",
              sender_display_name: "Оператор",
              text: "Начал диагностику и проверку канала.",
              ts: "2026-04-20T08:13:00+05:00",
              visibility: "public",
              direction: "to_agent",
              attachments: [],
              reply_to: null,
              tool_name: null,
              tool_status: null,
              result_summary: null,
              result_preview: null
            },
            ...currentDetail.timeline
          ]
        };
        return jsonResponse({
          status: "success",
          data: {
            ticket_id: "ticket-1",
            message: currentDetail.timeline[0]
          }
        });
      }

      if (url === "/api/web/support/tickets/ticket-1/status" && method === "POST") {
        currentDetail = {
          ...currentDetail,
          ticket: {
            ...currentDetail.ticket,
            status: "in_progress",
            status_label: "В работе"
          }
        };
        return jsonResponse({
          status: "success",
          data: {
            ticket_id: "ticket-1",
            status: "in_progress",
            status_label: "В работе"
          }
        });
      }

      return jsonResponse({ status: "error", error: `Unhandled URL: ${url}` }, 404);
    });

    vi.stubGlobal("fetch", fetchMock);

    renderSupportWorkspace();

    expect(await screen.findByText("Пользователь пишет, что ошибка повторяется.")).toBeInTheDocument();
    expect(screen.getByText("network.diagnostics")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Взять в работу" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Ответ оператору"), {
      target: { value: "Начал диагностику и проверку канала." }
    });
    fireEvent.click(screen.getByRole("button", { name: "Отправить ответ" }));

    await waitFor(() => {
      expect(screen.getByText("Начал диагностику и проверку канала.")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Взять в работу" }));

    await waitFor(() => {
      expect(screen.getAllByText("В работе").length).toBeGreaterThan(0);
    });
  });

  it("renders typed queue/detail data and observer capability map", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);

        if (url === "/api/web/support/bootstrap") {
          return jsonResponse({
            status: "success",
            data: {
              workspace: "support",
              features: [
                "queue_overview",
                "ticket_workspace",
                "observer_trace",
                "tool_actions"
              ],
              observer: {
                ticket_summary_endpoint: "/api/tickets/{ticket_id}/observer",
                drawer_tab: "trace"
              }
            }
          });
        }

        if (url.startsWith("/api/web/support/queue")) {
          return jsonResponse({
            status: "success",
            data: {
              scope: "all",
              query: "",
              status_filter: "all",
              summary: {
                visible_count: 1,
                selected_ticket_id: "ticket-1"
              },
              filters: {
                scope_options: [
                  { value: "all", label: "Все доступные" },
                  { value: "mine", label: "Только мои" }
                ],
                status_options: [
                  { value: "all", label: "Все статусы" },
                  { value: "new", label: "Новые" }
                ]
              },
              tickets: [
                {
                  ticket_id: "ticket-1",
                  ticket_code: "T-100001",
                  title: "Сбой синхронизации",
                  status: "new",
                  status_label: "Новая",
                  queue_code: "servicedesk_l1",
                  assignee_id: null,
                  requester_display_name: "Алексей",
                  device_id: "device-1",
                  updated_at: "2026-04-20T08:10:00+05:00",
                  created_at: "2026-04-20T07:55:00+05:00",
                  requires_operator_action: true,
                  unread_user_messages: 2
                }
              ]
            }
          });
        }

        if (url === "/api/web/support/tickets/ticket-1") {
          return jsonResponse({
            status: "success",
            data: {
              ticket: {
                ticket_id: "ticket-1",
                ticket_code: "T-100001",
                title: "Сбой синхронизации",
                description: "Нужно переподключить агент и проверить канал.",
                status: "new",
                status_label: "Новая",
                requester_display_name: "Алексей",
                device_id: "device-1",
                queue: {
                  id: 11,
                  code: "servicedesk_l1",
                  name: "ServiceDesk L1"
                },
                assignee_id: null,
                updated_at: "2026-04-20T08:10:00+05:00",
                created_at: "2026-04-20T07:55:00+05:00",
                queue_members: []
              },
              observer: {
                ticket_summary_endpoint: "/api/tickets/ticket-1/observer",
                summary: {
                  ticket_id: "ticket-1",
                  trace_count: 3,
                  active_trace_count: 1,
                  error_trace_count: 1,
                  signature_count: 1,
                  latest_trace_at: "2026-04-20T08:09:00+05:00"
                }
              }
            }
          });
        }

        return jsonResponse({ status: "error", error: `Unhandled URL: ${url}` }, 404);
      })
    );

    renderSupportWorkspace();

    expect(await screen.findByRole("heading", { name: "Рабочее место поддержки" })).toBeInTheDocument();
    expect(await screen.findByText("Сбой синхронизации")).toBeInTheDocument();
    expect(await screen.findByText("Нужно переподключить агент и проверить канал.")).toBeInTheDocument();
    expect(screen.getByText("/api/tickets/ticket-1/observer")).toBeInTheDocument();
    expect(screen.getAllByText("trace").length).toBeGreaterThanOrEqual(1);
  });

  it("renders the tool panel in Russian and lets the operator launch a typed tool", async () => {
    let postedBody: Record<string, unknown> | null = null;
    let currentDetail: SupportTicketDetailPayload = {
      ticket: {
        ticket_id: "ticket-1",
        ticket_code: "T-100001",
        title: "Сбой синхронизации",
        description: "Нужно переподключить агент и проверить канал.",
        status: "in_progress",
        status_label: "В работе",
        requester_display_name: "Алексей",
        device_id: "device-1",
        queue: {
          id: 11,
          code: "servicedesk_l1",
          name: "ServiceDesk L1"
        },
        assignee_id: "support-1",
        updated_at: "2026-04-20T08:10:00+05:00",
        created_at: "2026-04-20T07:55:00+05:00",
        queue_members: []
      },
      observer: {
        ticket_summary_endpoint: "/api/tickets/ticket-1/observer",
        summary: {
          ticket_id: "ticket-1",
          root_trace_id: "trace-root-1",
          trace_count: 3,
          active_trace_count: 1,
          error_trace_count: 1,
          signature_count: 1,
          latest_trace_at: "2026-04-20T08:09:00+05:00"
        }
      },
      timeline: [
        {
          message_id: "msg-user-1",
          event_id: 101,
          event_type: "chat_message",
          from_role: "user",
          sender_display_name: "Алексей",
          text: "Пользователь пишет, что ошибка повторяется.",
          ts: "2026-04-20T08:12:00+05:00",
          visibility: "public",
          direction: "to_agent",
          attachments: [],
          reply_to: null,
          tool_name: null,
          tool_status: null,
          result_summary: null,
          result_preview: null
        }
      ],
      snapshot: {
        last_event_id: 101,
        notification_unread: 0,
        presence: {
          requester_online: false,
          support_online: true,
          agent_online: false
        },
        device: {
          device_id: "device-1",
          hostname: "ws-01",
          os: "Windows 11",
          agent_version: "1.2.3",
          last_seen_at: "2026-04-20T08:11:00+05:00",
          online: false
        },
        latest_operations: []
      },
      actions: {
        status_options: [],
        can_send_internal_note: true
      }
    };

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/web/support/bootstrap") {
          return jsonResponse({
            status: "success",
            data: {
              workspace: "support",
              features: [
                "queue_overview",
                "ticket_workspace",
                "observer_trace",
                "tool_actions"
              ],
              observer: {
                ticket_summary_endpoint: "/api/tickets/{ticket_id}/observer",
                drawer_tab: "trace"
              }
            }
          });
        }

        if (url.startsWith("/api/web/support/queue")) {
          return jsonResponse({
            status: "success",
            data: {
              scope: "all",
              query: "",
              status_filter: "all",
              summary: {
                visible_count: 1,
                selected_ticket_id: "ticket-1"
              },
              filters: {
                scope_options: [
                  { value: "all", label: "Все доступные" },
                  { value: "mine", label: "Только мои" }
                ],
                status_options: [
                  { value: "all", label: "Все статусы" },
                  { value: "in_progress", label: "В работе" }
                ]
              },
              tickets: [
                {
                  ticket_id: "ticket-1",
                  ticket_code: "T-100001",
                  title: "Сбой синхронизации",
                  status: "in_progress",
                  status_label: "В работе",
                  queue_code: "servicedesk_l1",
                  assignee_id: "support-1",
                  requester_display_name: "Алексей",
                  device_id: "device-1",
                  updated_at: "2026-04-20T08:10:00+05:00",
                  created_at: "2026-04-20T07:55:00+05:00",
                  requires_operator_action: true,
                  unread_user_messages: 2
                }
              ]
            }
          });
        }

        if (url === "/api/web/support/tickets/ticket-1" && method === "GET") {
          return jsonResponse({
            status: "success",
            data: currentDetail
          });
        }

        if (url === "/api/web/support/tickets/ticket-1/tools" && method === "GET") {
          return jsonResponse({
            status: "success",
            data: {
              ticket_id: "ticket-1",
              device_id: "device-1",
              tools: [
                {
                  tool_name: "network.diagnostics",
                  module_name: "network",
                  description: "Быстрая диагностика сетевого контура",
                  risk_level: "safe_read",
                  requires_consent: false,
                  install_required: false,
                  source: "device",
                  params_schema: [
                    {
                      name: "target",
                      label: "Хост",
                      description: "Что проверить",
                      type: "string",
                      required: true,
                      default: null
                    }
                  ],
                  presets: []
                }
              ]
            }
          });
        }

        if (url === "/api/web/support/tickets/ticket-1/tools/run" && method === "POST") {
          postedBody = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
          currentDetail = {
            ...currentDetail,
            timeline: [
              {
                message_id: null,
                event_id: 102,
                event_type: "tool_call_started",
                from_role: "system",
                sender_display_name: "Система",
                text: "Запуск инструмента: network.diagnostics",
                ts: "2026-04-20T08:13:00+05:00",
                visibility: "system",
                direction: "system",
                attachments: [],
                reply_to: null,
                tool_name: "network.diagnostics",
                tool_status: "accepted",
                result_summary: null,
                result_preview: null
              },
              ...currentDetail.timeline
            ],
            snapshot: {
              ...currentDetail.snapshot,
              latest_operations: [
                {
                  operation_id: "op-tool-run-1",
                  kind: "tool_call",
                  status: "accepted",
                  tool_name: "network.diagnostics",
                  command_name: null,
                  queued_at: "2026-04-20T08:13:00+05:00",
                  finished_at: null,
                  result_summary: "Инструмент поставлен в очередь",
                  error_message: null
                }
              ]
            }
          };
          return jsonResponse(
            {
              status: "success",
              data: {
                ticket_id: "ticket-1",
                device_id: "device-1",
                tool_name: "network.diagnostics",
                dispatch_status: "accepted",
                operation_id: "op-tool-run-1",
                poll_url: "/api/operations/op-tool-run-1",
                trace_id: "trace-tool-run-1",
                message: "Инструмент поставлен в очередь выполнения"
              }
            },
            202
          );
        }

        return jsonResponse({ status: "error", error: `Unhandled URL: ${url}` }, 404);
      })
    );

    renderSupportWorkspace();

    expect(await screen.findByText("trace-root-1")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Инструменты и запуск" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /network\.diagnostics/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /network\.diagnostics/i }));
    fireEvent.change(screen.getByLabelText("Хост"), {
      target: { value: "srv-gateway" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Запустить инструмент" }));

    await waitFor(() => {
      expect(postedBody).toEqual({
        tool_name: "network.diagnostics",
        preset_id: null,
        params: {
          target: "srv-gateway"
        }
      });
    });

    expect(await screen.findByText("Операция op-tool-run-1 поставлена в очередь выполнения.")).toBeInTheDocument();
    expect(await screen.findByText("Запуск инструмента: network.diagnostics")).toBeInTheDocument();
  });

  it("shows a retry state when bootstrap loading fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(
          {
            status: "error",
            error: "Boundary недоступен",
            error_code: "BOOTSTRAP_UNAVAILABLE"
          },
          503
        )
      )
    );

    renderSupportWorkspace();

    expect(await screen.findByRole("heading", { name: "Не удалось открыть поддержку" })).toBeInTheDocument();
    expect(screen.getByText("Boundary недоступен")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Повторить загрузку" })).toBeInTheDocument();
  });

  it("shows an empty detail prompt instead of endless loading when queue is empty", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);

        if (url === "/api/web/support/bootstrap") {
          return jsonResponse({
            status: "success",
            data: {
              workspace: "support",
              features: [
                "queue_overview",
                "ticket_workspace",
                "observer_trace",
                "tool_actions"
              ],
              observer: {
                ticket_summary_endpoint: "/api/tickets/{ticket_id}/observer",
                drawer_tab: "trace"
              }
            }
          });
        }

        if (url.startsWith("/api/web/support/queue")) {
          return jsonResponse({
            status: "success",
            data: {
              scope: "all",
              query: "",
              status_filter: "all",
              summary: {
                visible_count: 0,
                selected_ticket_id: null
              },
              filters: {
                scope_options: [
                  { value: "all", label: "Все доступные" },
                  { value: "mine", label: "Только мои" }
                ],
                status_options: [
                  { value: "all", label: "Все статусы" }
                ]
              },
              tickets: []
            }
          });
        }

        return jsonResponse({ status: "error", error: `Unhandled URL: ${url}` }, 404);
      })
    );

    renderSupportWorkspace();

    expect(await screen.findByText("По текущим фильтрам тикеты не найдены.")).toBeInTheDocument();
    expect(screen.getByText("Выберите тикет в очереди, чтобы открыть карточку.")).toBeInTheDocument();
  });
});
