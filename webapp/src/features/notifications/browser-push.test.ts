import { afterEach, expect, it, vi } from "vitest";
import { disableBrowserPush, enableBrowserPush } from "./browser-push";

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

function browser() {
  const subscription = { endpoint: "https://fcm.googleapis.com/fcm/send/synthetic", options: {}, unsubscribe: vi.fn(async () => true) };
  const notification = { close: vi.fn() };
  const registration = {
    pushManager: { getSubscription: vi.fn(async () => null as typeof subscription | null), subscribe: vi.fn(async () => subscription) },
    active: { scriptURL: "https://helpdesk.test/helpdesk-notifications-sw.js", postMessage: vi.fn((_: unknown, ports?: { postMessage: (value: object) => void }[]) => ports?.[0].postMessage({ stopped: true })) },
    getNotifications: vi.fn(async () => [notification]),
  };
  const serviceWorker = { register: vi.fn(async () => registration), ready: Promise.resolve(registration), getRegistration: vi.fn(async () => registration) };
  const permission = vi.fn(async () => "granted");
  vi.stubGlobal("isSecureContext", true);
  vi.stubGlobal("Notification", { requestPermission: permission });
  vi.stubGlobal("PushManager", function () {});
  vi.stubGlobal("navigator", { serviceWorker });
  vi.stubGlobal("MessageChannel", class {
    port1 = { onmessage: null as (() => void) | null, close() {} };
    port2 = { postMessage: () => this.port1.onmessage?.() };
  });
  const fetch = vi.fn(async (_url: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify({ status: "ok" }), { headers: { "Content-Type": "application/json" } }));
  vi.stubGlobal("fetch", fetch);
  return { subscription, registration, serviceWorker, permission, notification, fetch };
}

it("asks permission only on explicit opt-in and registers the notification-only worker", async () => {
  const fixture = browser();
  expect(fixture.permission).not.toHaveBeenCalled();
  await enableBrowserPush("BA");
  expect(fixture.permission).toHaveBeenCalledOnce();
  expect(fixture.serviceWorker.register).toHaveBeenCalledWith("/helpdesk-notifications-sw.js", { scope: "/", updateViaCache: "none" });
  expect(fixture.fetch).toHaveBeenCalledWith("/api/web/notifications/push/subscribe", expect.objectContaining({ method: "POST" }));
});

it("denied permission cannot register or subscribe", async () => {
  const fixture = browser(); fixture.permission.mockResolvedValue("denied");
  await expect(enableBrowserPush("BA")).rejects.toThrow("не разрешён");
  expect(fixture.serviceWorker.register).not.toHaveBeenCalled();
  expect(fixture.fetch).not.toHaveBeenCalled();
});

it("failed server opt-in rolls back a newly created browser subscription", async () => {
  const fixture = browser(); fixture.fetch.mockResolvedValue(new Response("{}", { status: 503 }));
  await expect(enableBrowserPush("BA")).rejects.toThrow();
  expect(fixture.subscription.unsubscribe).toHaveBeenCalledOnce();
});

it("logout drains the worker, revokes the browser and closes notifications even if the server fails", async () => {
  const fixture = browser();
  fixture.registration.pushManager.getSubscription.mockResolvedValue(fixture.subscription);
  fixture.fetch.mockResolvedValue(new Response("{}", { status: 503 }));
  await expect(disableBrowserPush()).rejects.toThrow();
  expect(fixture.registration.active.postMessage).toHaveBeenCalledWith({ type: "helpdesk-notifications-suspend" }, expect.any(Array));
  expect(fixture.subscription.unsubscribe).toHaveBeenCalledOnce();
  expect(fixture.notification.close).toHaveBeenCalledOnce();
});

it("a stalled server cannot indefinitely block browser cleanup on logout", async () => {
  vi.useFakeTimers();
  const fixture = browser();
  fixture.registration.pushManager.getSubscription.mockResolvedValue(fixture.subscription);
  fixture.fetch.mockImplementation(async (_url, init) => new Promise<Response>((_resolve, reject) => {
    init!.signal!.addEventListener("abort", () => reject(new Error("aborted")));
  }));
  const outcome = disableBrowserPush().catch(error => error);
  await vi.advanceTimersByTimeAsync(3001);
  expect(await outcome).toBeInstanceOf(Error);
  expect(fixture.subscription.unsubscribe).toHaveBeenCalledOnce();
  expect(fixture.notification.close).toHaveBeenCalledOnce();
});
