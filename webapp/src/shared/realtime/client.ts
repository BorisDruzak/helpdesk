import {
  buildRealtimeSocketUrl,
  createBrowserWebSocketFactory,
  fetchWsUiBridgeBootstrap,
  type LocationLike,
  type RealtimeBootstrapPayload,
  type WebSocketFactory,
  type WebSocketLike,
} from "./adapters/ws-ui-bridge";

export type TicketRealtimeMessage =
  | {
      kind: "ticket_event";
      ticketId: string;
      eventId: number | null;
      eventType: string;
      payload: Record<string, unknown> | null;
    }
  | {
      kind: "operation_updated";
      ticketId: string;
      operationId: string;
      deviceId: string | null;
      status: string;
      updatedAt: string | null;
    };

export type DeviceRealtimeMessage =
  | {
      kind: "device_event";
      deviceId: string;
      eventId: number | null;
      eventType: string;
      payload: Record<string, unknown> | null;
    }
  | {
      kind: "operation_updated";
      deviceId: string;
      operationId: string;
      ticketId: string | null;
      status: string;
      updatedAt: string | null;
    };

type TicketListener = (message: TicketRealtimeMessage) => void;
type DeviceListener = (message: DeviceRealtimeMessage) => void;
type TimerHandle = ReturnType<typeof setTimeout> | ReturnType<typeof setInterval>;
const SOCKET_OPEN_READY_STATE = 1;

type TicketSubscriptionState = {
  listeners: Set<TicketListener>;
  active: boolean;
};

type DeviceSubscriptionState = {
  listeners: Set<DeviceListener>;
  active: boolean;
};

type CreateWebRealtimeClientOptions = {
  fetchImpl?: typeof fetch;
  webSocketFactory?: WebSocketFactory | null;
  locationOverride?: LocationLike;
  reconnectDelayMs?: number;
  pingIntervalOverrideMs?: number;
};

export interface WebRealtimeClient {
  subscribeTicket(ticketId: string, listener: TicketListener): () => void;
  subscribeDevice(deviceId: string, listener: DeviceListener): () => void;
  dispose(): void;
}

function normalizePayload(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

class WebRealtimeClientImpl implements WebRealtimeClient {
  private readonly fetchImpl: typeof fetch;
  private readonly webSocketFactory: WebSocketFactory | null;
  private readonly reconnectDelayMs: number;
  private readonly pingIntervalOverrideMs?: number;
  private readonly locationOverride?: LocationLike;

  private bootstrapPromise: Promise<RealtimeBootstrapPayload> | null = null;
  private connectPromise: Promise<void> | null = null;
  private socket: WebSocketLike | null = null;
  private bootstrap: RealtimeBootstrapPayload | null = null;
  private helloComplete = false;
  private manualClose = false;
  private pingTimer: TimerHandle | null = null;
  private reconnectTimer: TimerHandle | null = null;
  private helloRetryTimer: TimerHandle | null = null;
  private flushRetryTimer: TimerHandle | null = null;

  private readonly ticketSubscriptions = new Map<string, TicketSubscriptionState>();
  private readonly deviceSubscriptions = new Map<string, DeviceSubscriptionState>();

  private readonly handleSocketOpen = () => {
    if (!this.socket || !this.bootstrap) {
      return;
    }
    if (
      !this.sendSocketPayload(this.socket, {
        type: this.bootstrap.hello_message_type,
      })
    ) {
      this.scheduleHelloRetry();
    }
  };

  private readonly handleSocketMessage = (event: { data: string }) => {
    let payload: Record<string, unknown>;
    try {
      payload = JSON.parse(event.data) as Record<string, unknown>;
    } catch {
      return;
    }

    const messageType = typeof payload.type === "string" ? payload.type : null;
    if (!messageType) {
      return;
    }

    if (messageType === "ui_hello_ack") {
      this.helloComplete = true;
      this.startPingLoop();
      this.flushSubscriptions();
      return;
    }

    if (messageType === "subscribe_ack") {
      if (typeof payload.ticket_id === "string") {
        const subscription = this.ticketSubscriptions.get(payload.ticket_id);
        if (subscription) {
          subscription.active = true;
        }
      }
      if (typeof payload.device_id === "string") {
        const subscription = this.deviceSubscriptions.get(payload.device_id);
        if (subscription) {
          subscription.active = true;
        }
      }
      return;
    }

    if (messageType === "unsubscribe_ack") {
      if (typeof payload.ticket_id === "string") {
        const subscription = this.ticketSubscriptions.get(payload.ticket_id);
        if (subscription) {
          subscription.active = false;
        }
      }
      if (typeof payload.device_id === "string") {
        const subscription = this.deviceSubscriptions.get(payload.device_id);
        if (subscription) {
          subscription.active = false;
        }
      }
      return;
    }

    if (messageType === "ticket_event_committed" && typeof payload.ticket_id === "string") {
      this.dispatchTicketMessage(payload.ticket_id, {
        kind: "ticket_event",
        ticketId: payload.ticket_id,
        eventId: typeof payload.event_id === "number" ? payload.event_id : null,
        eventType: typeof payload.event_type === "string" ? payload.event_type : "unknown",
        payload: normalizePayload(payload.payload),
      });
      return;
    }

    if (messageType === "device_event_committed" && typeof payload.device_id === "string") {
      this.dispatchDeviceMessage(payload.device_id, {
        kind: "device_event",
        deviceId: payload.device_id,
        eventId: typeof payload.event_id === "number" ? payload.event_id : null,
        eventType: typeof payload.event_type === "string" ? payload.event_type : "unknown",
        payload: normalizePayload(payload.payload),
      });
      return;
    }

    if (messageType === "operation_updated") {
      if (typeof payload.ticket_id === "string") {
        this.dispatchTicketMessage(payload.ticket_id, {
          kind: "operation_updated",
          ticketId: payload.ticket_id,
          operationId: typeof payload.operation_id === "string" ? payload.operation_id : "unknown-operation",
          deviceId: typeof payload.device_id === "string" ? payload.device_id : null,
          status: typeof payload.status === "string" ? payload.status : "unknown",
          updatedAt: typeof payload.updated_at === "string" ? payload.updated_at : null,
        });
      }
      if (typeof payload.device_id === "string") {
        this.dispatchDeviceMessage(payload.device_id, {
          kind: "operation_updated",
          deviceId: payload.device_id,
          operationId: typeof payload.operation_id === "string" ? payload.operation_id : "unknown-operation",
          ticketId: typeof payload.ticket_id === "string" ? payload.ticket_id : null,
          status: typeof payload.status === "string" ? payload.status : "unknown",
          updatedAt: typeof payload.updated_at === "string" ? payload.updated_at : null,
        });
      }
      return;
    }

    if (messageType === "error") {
      const errorText = typeof payload.error === "string" ? payload.error : "unknown realtime error";
      console.warn("[webapp-realtime] bridge error:", errorText);
    }
  };

  private readonly handleSocketClose = () => {
    this.stopPingLoop();
    this.connectPromise = null;
    this.socket = null;
    this.helloComplete = false;
    for (const subscription of this.ticketSubscriptions.values()) {
      subscription.active = false;
    }
    for (const subscription of this.deviceSubscriptions.values()) {
      subscription.active = false;
    }

    if (this.manualClose || !this.hasSubscriptions()) {
      return;
    }

    this.scheduleReconnect();
  };

  private readonly handleSocketError = () => {
    if (!this.manualClose) {
      console.warn("[webapp-realtime] websocket bridge reported an error");
    }
  };

  constructor(options: CreateWebRealtimeClientOptions = {}) {
    this.fetchImpl = options.fetchImpl ?? fetch;
    this.webSocketFactory = options.webSocketFactory ?? createBrowserWebSocketFactory();
    this.locationOverride = options.locationOverride;
    this.reconnectDelayMs = options.reconnectDelayMs ?? 1500;
    this.pingIntervalOverrideMs = options.pingIntervalOverrideMs;
  }

  subscribeTicket(ticketId: string, listener: TicketListener): () => void {
    if (!this.webSocketFactory) {
      return () => {};
    }

    const subscription = this.ticketSubscriptions.get(ticketId) ?? {
      listeners: new Set<TicketListener>(),
      active: false,
    };
    subscription.listeners.add(listener);
    this.ticketSubscriptions.set(ticketId, subscription);
    void this.ensureConnected();

    return () => {
      const current = this.ticketSubscriptions.get(ticketId);
      if (!current) {
        return;
      }
      current.listeners.delete(listener);
      if (current.listeners.size > 0) {
        return;
      }

      if (current.active) {
        this.sendMessage({
          type: "unsubscribe_ticket",
          ticket_id: ticketId,
        });
      }
      this.ticketSubscriptions.delete(ticketId);
      this.closeIfIdle();
    };
  }

  subscribeDevice(deviceId: string, listener: DeviceListener): () => void {
    if (!this.webSocketFactory) {
      return () => {};
    }

    const subscription = this.deviceSubscriptions.get(deviceId) ?? {
      listeners: new Set<DeviceListener>(),
      active: false,
    };
    subscription.listeners.add(listener);
    this.deviceSubscriptions.set(deviceId, subscription);
    void this.ensureConnected();

    return () => {
      const current = this.deviceSubscriptions.get(deviceId);
      if (!current) {
        return;
      }
      current.listeners.delete(listener);
      if (current.listeners.size > 0) {
        return;
      }

      if (current.active) {
        this.sendMessage({
          type: "unsubscribe_device",
          device_id: deviceId,
        });
      }
      this.deviceSubscriptions.delete(deviceId);
      this.closeIfIdle();
    };
  }

  dispose() {
    this.ticketSubscriptions.clear();
    this.deviceSubscriptions.clear();
    this.closeSocket(true);
  }

  private async ensureConnected(): Promise<void> {
    if (!this.webSocketFactory) {
      return;
    }

    if (this.socket && this.helloComplete) {
      this.flushSubscriptions();
      return;
    }

    if (this.connectPromise) {
      return this.connectPromise;
    }

    this.connectPromise = this.openSocket();
    return this.connectPromise;
  }

  private async openSocket(): Promise<void> {
    this.bootstrap = await this.loadBootstrap();
    if (!this.webSocketFactory) {
      return;
    }

    const locationObj = this.locationOverride ?? {
      protocol: window.location.protocol,
      host: window.location.host,
    };
    const socketUrl = buildRealtimeSocketUrl(this.bootstrap.socket_url, locationObj);
    this.manualClose = false;
    const socket = this.webSocketFactory(socketUrl);
    this.attachSocket(socket);
    this.socket = socket;
  }

  private attachSocket(socket: WebSocketLike) {
    socket.addEventListener("open", this.handleSocketOpen);
    socket.addEventListener("message", this.handleSocketMessage);
    socket.addEventListener("close", this.handleSocketClose);
    socket.addEventListener("error", this.handleSocketError);
  }

  private detachSocket(socket: WebSocketLike) {
    socket.removeEventListener("open", this.handleSocketOpen);
    socket.removeEventListener("message", this.handleSocketMessage);
    socket.removeEventListener("close", this.handleSocketClose);
    socket.removeEventListener("error", this.handleSocketError);
  }

  private async loadBootstrap(): Promise<RealtimeBootstrapPayload> {
    if (!this.bootstrapPromise) {
      this.bootstrapPromise = fetchWsUiBridgeBootstrap(this.fetchImpl);
    }
    return this.bootstrapPromise;
  }

  private flushSubscriptions() {
    if (!this.helloComplete) {
      return;
    }

    for (const [ticketId, subscription] of this.ticketSubscriptions.entries()) {
      if (subscription.listeners.size === 0 || subscription.active) {
        continue;
      }
      if (
        !this.sendMessage({
          type: "subscribe_ticket",
          ticket_id: ticketId,
          since_event_id: 0,
          skip_catchup: true,
        })
      ) {
        this.scheduleFlushRetry();
        return;
      }
    }

    for (const [deviceId, subscription] of this.deviceSubscriptions.entries()) {
      if (subscription.listeners.size === 0 || subscription.active) {
        continue;
      }
      if (
        !this.sendMessage({
          type: "subscribe_device",
          device_id: deviceId,
          since_event_id: 0,
          skip_catchup: true,
        })
      ) {
        this.scheduleFlushRetry();
        return;
      }
    }
  }

  private sendMessage(payload: Record<string, unknown>): boolean {
    if (!this.socket || !this.helloComplete) {
      return false;
    }
    return this.sendSocketPayload(this.socket, payload);
  }

  private sendSocketPayload(socket: WebSocketLike, payload: Record<string, unknown>): boolean {
    if (socket.readyState !== SOCKET_OPEN_READY_STATE) {
      return false;
    }

    try {
      socket.send(JSON.stringify(payload));
      return true;
    } catch {
      return false;
    }
  }

  private dispatchTicketMessage(ticketId: string, message: TicketRealtimeMessage) {
    const subscription = this.ticketSubscriptions.get(ticketId);
    if (!subscription) {
      return;
    }

    for (const listener of subscription.listeners) {
      listener(message);
    }
  }

  private dispatchDeviceMessage(deviceId: string, message: DeviceRealtimeMessage) {
    const subscription = this.deviceSubscriptions.get(deviceId);
    if (!subscription) {
      return;
    }

    for (const listener of subscription.listeners) {
      listener(message);
    }
  }

  private hasSubscriptions(): boolean {
    return this.ticketSubscriptions.size > 0 || this.deviceSubscriptions.size > 0;
  }

  private startPingLoop() {
    this.stopPingLoop();
    const intervalMs = this.pingIntervalOverrideMs ?? this.bootstrap?.ping_interval_ms ?? 20_000;
    this.pingTimer = setInterval(() => {
      this.sendMessage({ type: "ping" });
    }, intervalMs);
  }

  private stopPingLoop() {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimer || !this.hasSubscriptions()) {
      return;
    }

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      void this.ensureConnected();
    }, this.reconnectDelayMs);
  }

  private scheduleHelloRetry() {
    if (this.helloRetryTimer || !this.socket || !this.bootstrap || this.helloComplete) {
      return;
    }

    this.helloRetryTimer = setTimeout(() => {
      this.helloRetryTimer = null;
      this.handleSocketOpen();
    }, 50);
  }

  private scheduleFlushRetry() {
    if (this.flushRetryTimer || !this.helloComplete) {
      return;
    }

    this.flushRetryTimer = setTimeout(() => {
      this.flushRetryTimer = null;
      this.flushSubscriptions();
    }, 50);
  }

  private closeIfIdle() {
    if (this.hasSubscriptions()) {
      return;
    }
    this.closeSocket(true);
  }

  private closeSocket(manualClose: boolean) {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.helloRetryTimer) {
      clearTimeout(this.helloRetryTimer);
      this.helloRetryTimer = null;
    }

    if (this.flushRetryTimer) {
      clearTimeout(this.flushRetryTimer);
      this.flushRetryTimer = null;
    }

    this.manualClose = manualClose;
    this.stopPingLoop();

    if (!this.socket) {
      this.connectPromise = null;
      this.helloComplete = false;
      return;
    }

    const socket = this.socket;
    this.socket = null;
    this.connectPromise = null;
    this.helloComplete = false;
    this.detachSocket(socket);
    socket.close();
  }
}

let sharedClient: WebRealtimeClient | null = null;

export function createWebRealtimeClient(options: CreateWebRealtimeClientOptions = {}): WebRealtimeClient {
  return new WebRealtimeClientImpl(options);
}

export function getSharedWebRealtimeClient(): WebRealtimeClient {
  if (!sharedClient) {
    sharedClient = createWebRealtimeClient();
  }
  return sharedClient;
}

export function resetSharedWebRealtimeClientForTests() {
  if (sharedClient) {
    sharedClient.dispose();
    sharedClient = null;
  }
}
