export type BellNotification = {
  id: number; ticket_id: string; event_type: string; title: string; body: string;
  url: string; is_read: boolean; created_at: string | null;
};

export async function notificationRequest<T>(path: string, body?: object, timeoutMs = 10_000): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`/api/web/notifications${path}`, {
      credentials: "same-origin", cache: "no-store", signal: controller.signal,
      ...(body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {}),
    });
    if (!response.ok) throw new Error("Не удалось выполнить действие с уведомлениями.");
    const payload = await response.json();
    if (payload.status !== "ok") throw new Error("Не удалось выполнить действие с уведомлениями.");
    return payload as T;
  } finally { window.clearTimeout(timeout); }
}

export async function fetchBellNotifications(): Promise<BellNotification[]> {
  const result = await notificationRequest<{ notifications: BellNotification[] }>("?limit=30");
  return Array.isArray(result.notifications) ? result.notifications : [];
}

export function safeNotificationUrl(value: string): string | null {
  return /^\/app\/(?:requester\/)?tickets\/[a-zA-Z0-9-]+$/.test(value) ? value : null;
}
