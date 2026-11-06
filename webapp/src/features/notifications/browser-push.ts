import { notificationRequest } from "./api";

export const WORKER_URL = "/helpdesk-notifications-sw.js";

export function supportsBrowserPush(): boolean {
  return window.isSecureContext && "Notification" in window && "serviceWorker" in navigator && "PushManager" in window;
}

export async function existingPushRegistration(): Promise<ServiceWorkerRegistration | undefined> {
  if (!supportsBrowserPush()) return undefined;
  const registration = await navigator.serviceWorker.getRegistration("/");
  return registration?.active?.scriptURL.endsWith(WORKER_URL) ? registration : undefined;
}

export async function enableBrowserPush(publicKey: string): Promise<void> {
  if (!supportsBrowserPush()) throw new Error("Нужен браузер с поддержкой уведомлений и защищённое HTTPS-соединение.");
  const permission = await Notification.requestPermission();
  if (permission !== "granted") throw new Error("Показ уведомлений не разрешён. Разрешение можно изменить в настройках сайта в браузере.");
  await navigator.serviceWorker.register(WORKER_URL, { scope: "/", updateViaCache: "none" });
  const registration = await navigator.serviceWorker.ready;
  const key = Uint8Array.from(atob(publicKey.replace(/-/g, "+").replace(/_/g, "/")), c => c.charCodeAt(0));
  let subscription = await registration.pushManager.getSubscription();
  if (subscription) {
    const oldKey = subscription.options.applicationServerKey;
    if (oldKey && (new Uint8Array(oldKey).length !== key.length || new Uint8Array(oldKey).some((v, i) => v !== key[i]))) {
      await subscription.unsubscribe(); subscription = null;
    }
  }
  const created = !subscription;
  subscription ??= await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
  try {
    await notificationRequest("/push/subscribe", { endpoint: subscription.endpoint });
    registration.active?.postMessage({ type: "helpdesk-notifications-resume" });
  } catch (error) {
    if (created) await subscription.unsubscribe();
    throw error;
  }
}

export async function disableBrowserPush(): Promise<void> {
  const registration = await existingPushRegistration();
  let failure: unknown;
  if (registration?.active) {
    await new Promise<void>((resolve, reject) => {
      const channel = new MessageChannel();
      const timeout = window.setTimeout(() => { channel.port1.close(); reject(new Error("Не удалось остановить уведомления.")); }, 12_000);
      channel.port1.onmessage = () => { window.clearTimeout(timeout); channel.port1.close(); resolve(); };
      registration.active!.postMessage({ type: "helpdesk-notifications-suspend" }, [channel.port2]);
    }).catch(error => { failure = error; });
  }
  const subscription = await registration?.pushManager.getSubscription();
  if (subscription) {
    // Browser unsubscribe still runs when a server/session is unavailable.
    try { await notificationRequest("/push/unsubscribe", { endpoint: subscription.endpoint }, 3000); }
    catch (error) { failure = error; }
    finally { await subscription.unsubscribe(); }
  }
  const notifications = await registration?.getNotifications();
  notifications?.forEach(notification => notification.close());
  if (failure) throw failure;
}

export async function checkBrowserNotifications(): Promise<void> {
  const registration = await existingPushRegistration();
  if (registration && await registration.pushManager.getSubscription()) {
    registration.active?.postMessage({ type: "helpdesk-check-notifications" });
  }
}
