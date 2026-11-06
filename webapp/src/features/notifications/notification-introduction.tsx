import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { notificationRequest } from "./api";
import { existingPushRegistration, supportsBrowserPush } from "./browser-push";
import { BrowserPushControl } from "./browser-push-control";

const dismissedInMemory = new Set<string>();
const storageKey = (login: string) => `helpdesk-notification-intro-v1:${login}`;
function wasDismissed(login: string): boolean {
  try { return dismissedInMemory.has(login) || localStorage.getItem(storageKey(login)) === "1"; }
  catch { return dismissedInMemory.has(login); }
}

function IntroductionDialog({ userLogin, onClose }: { userLogin: string; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current!;
    dialog.showModal();
    return () => dialog.close();
  }, []);
  return createPortal(<dialog ref={ref} aria-labelledby="notification-intro-title" onCancel={event => { event.preventDefault(); onClose(); }}
    className="fixed inset-0 m-auto max-h-[calc(100dvh-2rem)] w-[min(440px,calc(100vw-2rem))] overflow-y-auto rounded-xl border border-border bg-white p-5 text-sm text-slate-700 shadow-xl backdrop:bg-slate-950/30">
    <div className="flex items-start justify-between gap-4"><h2 className="text-lg font-semibold text-slate-950" id="notification-intro-title">Не пропускайте ответы по обращениям</h2><button autoFocus aria-label="Закрыть подсказку" className="rounded px-2 py-1 text-slate-500 hover:bg-slate-100" onClick={onClose} type="button">✕</button></div>
    <p className="mt-3">Включите уведомления о новых сообщениях в чате и смене статуса обращения. Они придут в браузер, даже когда вкладка службы поддержки закрыта.</p>
    <p className="mt-2 mb-3">В колокольчике остаются непрочитанные события. В открытом активном чате уведомления не отвлекают. Разрешение браузера понадобится только после нажатия кнопки ниже.</p>
    <BrowserPushControl userLogin={userLogin} onEnabled={onClose} />
    <button className="mt-3 font-semibold text-brand-700 underline" onClick={onClose} type="button">Понятно</button>
  </dialog>, document.body);
}

export function NotificationIntroduction({ userLogin }: { userLogin: string }) {
  const [dismissed, setDismissed] = useState(() => wasDismissed(userLogin));
  const [ready, setReady] = useState(false);
  const supported = supportsBrowserPush();
  const config = useQuery({ queryKey: ["browser-push-config", userLogin], enabled: supported, retry: false,
    queryFn: () => notificationRequest<{ enabled: boolean; public_key: string | null }>("/push/config") });
  useEffect(() => {
    if (!supported || dismissed) return;
    let alive = true;
    void (async () => {
      const registration = await existingPushRegistration();
      const subscription = await registration?.pushManager.getSubscription();
      const status = subscription ? await notificationRequest<{ subscribed: boolean }>("/push/status", { endpoint: subscription.endpoint }) : null;
      if (alive) setReady(!status?.subscribed);
    })().catch(() => { if (alive) setReady(true); });
    return () => { alive = false; };
  }, [dismissed, supported, userLogin]);
  function close() {
    dismissedInMemory.add(userLogin);
    try { localStorage.setItem(storageKey(userLogin), "1"); } catch { /* Closing must work with blocked storage. */ }
    setDismissed(true);
  }
  return !dismissed && ready && config.data?.enabled ? <IntroductionDialog userLogin={userLogin} onClose={close} /> : null;
}
