import { waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createWebRealtimeClient, resetSharedWebRealtimeClientForTests } from "./client";


class FakeWebSocket {
  static instances: FakeWebSocket[] = [];

  readyState = 1;
  sent: string[] = [];
  closed = false;

  private readonly listeners = {
    open: new Set<() => void>(),
    close: new Set<() => void>(),
    error: new Set<() => void>(),
    message: new Set<(event: { data: string }) => void>(),
  };

  constructor(readonly url: string) {
    FakeWebSocket.instances.push(this);
  }

  addEventListener(type: "open" | "close" | "error", listener: () => void): void;
  addEventListener(type: "message", listener: (event: { data: string }) => void): void;
  addEventListener(
    type: "open" | "close" | "error" | "message",
    listener: (() => void) | ((event: { data: string }) => void)
  ) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (this.listeners[type] as Set<any>).add(listener);
  }

  removeEventListener(type: "open" | "close" | "error", listener: () => void): void;
  removeEventListener(type: "message", listener: (event: { data: string }) => void): void;
  removeEventListener(
    type: "open" | "close" | "error" | "message",
    listener: (() => void) | ((event: { data: string }) => void)
  ) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (this.listeners[type] as Set<any>).delete(listener);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.closed = true;
  }

  emitOpen() {
    for (const listener of this.listeners.open) {
      listener();
    }
  }

  emitMessage(payload: unknown) {
    const data = typeof payload === "string" ? payload : JSON.stringify(payload);
    for (const listener of this.listeners.message) {
      listener({ data });
    }
  }
}


afterEach(() => {
  resetSharedWebRealtimeClientForTests();
  FakeWebSocket.instances = [];
  vi.restoreAllMocks();
});


describe("createWebRealtimeClient", () => {
  it("loads bridge bootstrap, authenticates via ui_hello and routes ticket/device messages", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          status: "success",
          data: {
            transport: "ws_ui_bridge",
            auth_mode: "session_cookie",
            hello_message_type: "ui_hello",
            socket_url: "/ws_ui",
            ping_interval_ms: 20000,
            channels: [
              {
                channel: "support.queue",
                scope: "ticket",
                subscribe_message_type: "subscribe_ticket",
                unsubscribe_message_type: "unsubscribe_ticket",
                supports_catchup: true,
                supports_live_only: true,
              },
              {
                channel: "admin.devices",
                scope: "device",
                subscribe_message_type: "subscribe_device",
                unsubscribe_message_type: "unsubscribe_device",
                supports_catchup: true,
                supports_live_only: true,
              },
            ],
          },
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        }
      )
    );

    const ticketListener = vi.fn();
    const deviceListener = vi.fn();
    const client = createWebRealtimeClient({
      fetchImpl: fetchMock as typeof fetch,
      webSocketFactory: (url) => new FakeWebSocket(url),
      locationOverride: {
        protocol: "http:",
        host: "127.0.0.1:8666",
      },
    });

    const unsubscribeTicket = client.subscribeTicket("ticket-1", ticketListener);
    const unsubscribeDevice = client.subscribeDevice("device-1", deviceListener);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/web/realtime/bootstrap", {
        credentials: "same-origin",
      });
      expect(FakeWebSocket.instances).toHaveLength(1);
    });
    expect(FakeWebSocket.instances[0]?.url).toBe("ws://127.0.0.1:8666/ws_ui");

    const socket = FakeWebSocket.instances[0]!;
    socket.emitOpen();
    expect(socket.sent).toContain(JSON.stringify({ type: "ui_hello" }));

    socket.emitMessage({
      type: "ui_hello_ack",
      connection_id: "conn-1",
      role: "support",
    });
    expect(socket.sent).toContain(
      JSON.stringify({
        type: "subscribe_ticket",
        ticket_id: "ticket-1",
        since_event_id: 0,
        skip_catchup: true,
      })
    );
    expect(socket.sent).toContain(
      JSON.stringify({
        type: "subscribe_device",
        device_id: "device-1",
        since_event_id: 0,
        skip_catchup: true,
      })
    );

    socket.emitMessage({
      type: "subscribe_ack",
      ticket_id: "ticket-1",
      since_event_id: 0,
    });
    socket.emitMessage({
      type: "subscribe_ack",
      device_id: "device-1",
      since_event_id: 0,
    });

    socket.emitMessage({
      type: "ticket_event_committed",
      ticket_id: "ticket-1",
      event_id: 15,
      event_type: "chat_message",
      payload: {
        text: "Проверка realtime",
      },
    });
    socket.emitMessage({
      type: "operation_updated",
      operation_id: "op-1",
      ticket_id: "ticket-1",
      device_id: "device-1",
      status: "queued",
      updated_at: "2026-04-21T10:00:00+05:00",
    });
    socket.emitMessage({
      type: "device_event_committed",
      device_id: "device-1",
      event_id: 21,
      event_type: "agent_status_changed",
      payload: {
        online: true,
      },
    });

    expect(ticketListener).toHaveBeenNthCalledWith(1, {
      kind: "ticket_event",
      ticketId: "ticket-1",
      eventId: 15,
      eventType: "chat_message",
      payload: {
        text: "Проверка realtime",
      },
    });
    expect(ticketListener).toHaveBeenNthCalledWith(2, {
      kind: "operation_updated",
      ticketId: "ticket-1",
      operationId: "op-1",
      deviceId: "device-1",
      status: "queued",
      updatedAt: "2026-04-21T10:00:00+05:00",
    });
    expect(deviceListener).toHaveBeenNthCalledWith(1, {
      kind: "operation_updated",
      deviceId: "device-1",
      operationId: "op-1",
      ticketId: "ticket-1",
      status: "queued",
      updatedAt: "2026-04-21T10:00:00+05:00",
    });
    expect(deviceListener).toHaveBeenNthCalledWith(2, {
      kind: "device_event",
      deviceId: "device-1",
      eventId: 21,
      eventType: "agent_status_changed",
      payload: {
        online: true,
      },
    });

    unsubscribeTicket();
    unsubscribeDevice();

    expect(socket.sent).toContain(
      JSON.stringify({
        type: "unsubscribe_ticket",
        ticket_id: "ticket-1",
      })
    );
    expect(socket.sent).toContain(
      JSON.stringify({
        type: "unsubscribe_device",
        device_id: "device-1",
      })
    );
    expect(socket.closed).toBe(true);

    client.dispose();
  });

  it("retries ui_hello when the browser websocket is still connecting during open callback", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          status: "success",
          data: {
            transport: "ws_ui_bridge",
            auth_mode: "session_cookie",
            hello_message_type: "ui_hello",
            socket_url: "/ws_ui",
            ping_interval_ms: 20000,
            channels: [],
          },
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        }
      )
    );

    const client = createWebRealtimeClient({
      fetchImpl: fetchMock as typeof fetch,
      webSocketFactory: (url) => new FakeWebSocket(url),
      locationOverride: {
        protocol: "http:",
        host: "127.0.0.1:8666",
      },
    });

    client.subscribeTicket("ticket-1", vi.fn());

    await waitFor(() => {
      expect(FakeWebSocket.instances).toHaveLength(1);
    });

    vi.useFakeTimers();
    try {
      const socket = FakeWebSocket.instances[0]!;
      socket.readyState = 0;
      socket.emitOpen();
      expect(socket.sent).toEqual([]);

      socket.readyState = 1;
      await vi.advanceTimersByTimeAsync(60);

      expect(socket.sent).toContain(JSON.stringify({ type: "ui_hello" }));
      client.dispose();
    } finally {
      vi.useRealTimers();
    }
  });
});
