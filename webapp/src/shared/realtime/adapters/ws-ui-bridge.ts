export type RealtimeScope = "ticket" | "device" | "chat";

export type RealtimeChannelContract = {
  channel: string;
  scope: RealtimeScope;
  subscribe_message_type: string;
  unsubscribe_message_type: string;
  supports_catchup: boolean;
  supports_live_only: boolean;
};

export type RealtimeBootstrapPayload = {
  transport: "ws_ui_bridge";
  auth_mode: "session_cookie";
  hello_message_type: "ui_hello";
  socket_url: string;
  ping_interval_ms: number;
  channels: RealtimeChannelContract[];
};

type SuccessResponse<T> = {
  status: "success";
  data: T;
};

type ErrorResponse = {
  status: "error";
  error?: string;
  error_code?: string;
};

export class WebRealtimeBootstrapError extends Error {
  status: number;
  errorCode?: string;

  constructor(message: string, status: number, errorCode?: string) {
    super(message);
    this.name = "WebRealtimeBootstrapError";
    this.status = status;
    this.errorCode = errorCode;
  }
}

export type LocationLike = {
  protocol: string;
  host: string;
};

export type WebSocketMessageListener = (event: { data: string }) => void;
export type WebSocketVoidListener = () => void;

export interface WebSocketLike {
  readyState: number;
  send(data: string): void;
  close(code?: number, reason?: string): void;
  addEventListener(type: "open", listener: WebSocketVoidListener): void;
  addEventListener(type: "close", listener: WebSocketVoidListener): void;
  addEventListener(type: "error", listener: WebSocketVoidListener): void;
  addEventListener(type: "message", listener: WebSocketMessageListener): void;
  removeEventListener(type: "open", listener: WebSocketVoidListener): void;
  removeEventListener(type: "close", listener: WebSocketVoidListener): void;
  removeEventListener(type: "error", listener: WebSocketVoidListener): void;
  removeEventListener(type: "message", listener: WebSocketMessageListener): void;
}

export type WebSocketFactory = (url: string) => WebSocketLike;

async function readJson<T>(response: Response): Promise<T | null> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return null;
  }

  return (await response.json()) as T;
}

export function buildRealtimeSocketUrl(socketUrl: string, locationObj: LocationLike): string {
  if (/^wss?:\/\//.test(socketUrl)) {
    return socketUrl;
  }

  const protocol = locationObj.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${locationObj.host}${socketUrl}`;
}

export async function fetchWsUiBridgeBootstrap(
  fetchImpl: typeof fetch = fetch
): Promise<RealtimeBootstrapPayload> {
  const response = await fetchImpl("/api/web/realtime/bootstrap", {
    credentials: "same-origin",
  });
  const payload = await readJson<SuccessResponse<RealtimeBootstrapPayload> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new WebRealtimeBootstrapError(
      errorPayload?.error ?? "Не удалось загрузить realtime-мост для нового webapp.",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export function createBrowserWebSocketFactory(): WebSocketFactory | null {
  if (typeof WebSocket === "undefined") {
    return null;
  }

  return (url: string) => new WebSocket(url);
}
