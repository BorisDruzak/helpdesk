// Short-lived memory only. Reload intentionally returns to manual entry.
let pending: { code: string; expiresAt: number } | null = null;

export function normalizeDeviceCode(value: string): string {
  const normalized = value.trim().replace(/^([0-9]{3})-([0-9]{3})$/, "$1$2");
  return /^[0-9]{6}$/.test(normalized) ? normalized : "";
}

export function clearPendingDeviceCode() { pending = null; }

export function rememberPendingDeviceCode(value: string) {
  const code = normalizeDeviceCode(value);
  pending = code ? { code, expiresAt: Date.now() + 600_000 } : null;
}

export function pendingDeviceCode(): string {
  if (pending && pending.expiresAt > Date.now()) return pending.code;
  pending = null;
  return "";
}

export function captureDeviceLinkFragment() {
  if (window.location.pathname !== "/app/requester/devices/link" || !window.location.hash) return;
  const fragment = new URLSearchParams(window.location.hash.slice(1));
  if (!fragment.has("code")) return;
  rememberPendingDeviceCode(fragment.get("code") ?? "");
  window.history.replaceState(window.history.state, "", `${window.location.pathname}${window.location.search}`);
}
