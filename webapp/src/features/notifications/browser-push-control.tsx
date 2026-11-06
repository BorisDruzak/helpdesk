import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { notificationRequest } from "./api";
import { disableBrowserPush, enableBrowserPush, existingPushRegistration, supportsBrowserPush } from "./browser-push";

export function BrowserPushControl({ userLogin, onEnabled }: { userLogin: string; onEnabled?: () => void }) {
  const supported = supportsBrowserPush();
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const config = useQuery({ queryKey: ["browser-push-config", userLogin], enabled: supported, retry: false,
    queryFn: () => notificationRequest<{ enabled: boolean; public_key: string | null }>("/push/config") });

  useEffect(() => {
    let ignore = false;
    void (async () => {
      const registration = await existingPushRegistration();
      const subscription = await registration?.pushManager.getSubscription();
      if (!subscription) return;
      const status = await notificationRequest<{ subscribed: boolean }>("/push/status", { endpoint: subscription.endpoint });
      if (!ignore) setEnabled(status.subscribed);
    })().catch(() => { if (!ignore) setError("Не удалось проверить подключение браузера."); });
    return () => { ignore = true; };
  }, [userLogin]);

  async function toggle() {
    setBusy(true); setError("");
    try {
      if (enabled) await disableBrowserPush();
      else if (config.data?.public_key) await enableBrowserPush(config.data.public_key);
      setEnabled(!enabled);
      if (!enabled) onEnabled?.();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Не удалось подключить уведомления."); }
    finally { setBusy(false); }
  }

  return <div className="border-t border-border px-4 py-3 text-xs text-slate-600">
    {!supported ? <p>Браузерные уведомления требуют HTTPS и поддержки Web Push.</p> : <>
      {config.isPending ? <p>Проверяем браузерные уведомления…</p> : null}
      {config.isError ? <p role="status">Не удалось проверить настройки уведомлений.</p> : null}
      {config.data && !config.data.enabled ? <p>Браузерные уведомления ещё не настроены на сервере.</p> : null}
      {config.data?.enabled ? <><button className="font-semibold text-brand-700 underline disabled:opacity-50" disabled={busy} onClick={() => void toggle()} type="button">{busy ? "Подождите…" : enabled ? "Отключить уведомления в этом браузере" : "Включить уведомления в браузере"}</button><p className="mt-1">О новых сообщениях и смене статуса, даже при закрытой вкладке.</p></> : null}
      {error ? <p className="mt-2 text-rose-700" role="alert">{error}</p> : null}
    </>}
  </div>;
}
