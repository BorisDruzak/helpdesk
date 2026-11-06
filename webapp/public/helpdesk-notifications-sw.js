/* Notification-only service worker. No fetch interception or application cache. */
"use strict";
const API = "/api/web/notifications/push/";
let running = Promise.resolve();
let generation = 0;
let paused = false;

function shownDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("helpdesk-notifications-v1", 1);
    request.onupgradeneeded = () => request.result.createObjectStore("shown");
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(new Error("Notification storage unavailable"));
  });
}

async function alreadyShown(key, remember = false) {
  const db = await shownDatabase();
  try {
    return await new Promise((resolve, reject) => {
      const transaction = db.transaction("shown", remember ? "readwrite" : "readonly");
      const store = transaction.objectStore("shown");
      const request = remember ? store.put(Date.now(), key) : store.get(key);
      if (remember) {
        const cursor = store.openCursor();
        cursor.onsuccess = () => {
          const item = cursor.result;
          if (!item) return;
          if (item.value < Date.now() - 7 * 86400_000) item.delete();
          item.continue();
        };
      }
      transaction.oncomplete = () => resolve(remember || Boolean(request.result));
      transaction.onerror = () => reject(new Error("Notification storage unavailable"));
      transaction.onabort = () => reject(new Error("Notification storage unavailable"));
    });
  } finally { db.close(); }
}

async function post(action, body) {
  return fetch(API + action, { method: "POST", credentials: "same-origin", cache: "no-store", signal: AbortSignal.timeout(8000), headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

async function currentActor() {
  const response = await fetch("/api/web/session/me", { credentials: "same-origin", cache: "no-store", signal: AbortSignal.timeout(8000) });
  if (!response.ok) return null;
  const payload = await response.json();
  return payload.data?.user_login ?? payload.user_login;
}

async function chatIsVisible(notification, actor) {
  const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
  const ticket = new URL(notification.url, self.location.origin).pathname.split("/").pop();
  const matches = client => client.focused && client.visibilityState === "visible" &&
    new URL(client.url).origin === self.location.origin &&
    /^\/app\/(?:requester\/)?tickets\/[^/]+\/?$/.test(new URL(client.url).pathname) &&
    new URL(client.url).pathname.replace(/\/$/, "").endsWith(`/tickets/${ticket}`);
  const candidates = windows.filter(matches);
  const replies = await Promise.all(candidates.map(client => new Promise(resolve => {
    const channel = new MessageChannel();
    const done = value => { clearTimeout(timer); channel.port1.close(); resolve(value); };
    const timer = setTimeout(() => done(false), 750);
    channel.port1.onmessage = event => done(event.data?.active === true);
    try { client.postMessage({ type: "helpdesk-is-chat-visible", ticket_id: ticket, actor_id: actor }, [channel.port2]); }
    catch { done(false); }
  })));
  // A user may have switched away while the page was answering.
  const current = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
  return candidates.some((client, index) => replies[index] && current.some(item => item.id === client.id && matches(item)));
}

async function checkNotifications() {
  const version = generation;
  if (paused) return;
  const subscription = await self.registration.pushManager.getSubscription();
  if (!subscription) return;
  const response = await post("messages", { endpoint: subscription.endpoint });
  if (response.status === 401 || response.status === 403) {
    await subscription.unsubscribe();
    return; // An expired session cannot retrieve private event data.
  }
  if (!response.ok) throw new Error("Notification retrieval unavailable");
  const payload = await response.json();
  if (payload.status !== "ok" || !Array.isArray(payload.notifications)) return;
  const acknowledged = [];
  for (const notification of payload.notifications) {
    if (!Number.isSafeInteger(notification.id) || !/^\/app\/(?:requester\/)?tickets\/[a-zA-Z0-9-]+$/.test(notification.url)) continue;
    const key = `${payload.actor_id}:${notification.id}`;
    if (!await alreadyShown(key)) {
      // Covers cookie/session changes in another tab as well as local logout.
      if (await currentActor() !== payload.actor_id || paused || version !== generation) return;
      const active = await chatIsVisible(notification, payload.actor_id);
      if (await currentActor() !== payload.actor_id || paused || version !== generation) return;
      if (active) {
        try {
          const read = await fetch(`/api/web/notifications/${notification.id}/read`, { method: "POST", credentials: "same-origin", signal: AbortSignal.timeout(8000) });
          if (read.ok && (await read.json()).updated) {
            (await self.registration.getNotifications({ tag: `helpdesk-${key}` })).forEach(item => item.close());
            await alreadyShown(key, true);
            acknowledged.push(notification.id);
            continue;
          }
        } catch { /* A failed read must fall back to an alert, not lose the event. */ }
      }
      if (await currentActor() !== payload.actor_id || paused || version !== generation) return;
      await self.registration.showNotification(notification.title, { body: notification.body, tag: `helpdesk-${key}`, renotify: false, icon: "/favicon.svg", data: { url: notification.url, actor_id: payload.actor_id, id: notification.id } });
      if (paused || version !== generation) {
        (await self.registration.getNotifications({ tag: `helpdesk-${key}` })).forEach(item => item.close());
        return;
      }
      await alreadyShown(key, true);
    }
    acknowledged.push(notification.id);
  }
  if (acknowledged.length) {
    const ack = await post("acknowledge", { endpoint: subscription.endpoint, notification_ids: acknowledged });
    if (!ack.ok) throw new Error("Notification acknowledgement unavailable");
  }
  const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
  windows.forEach(client => client.postMessage({ type: "helpdesk-notifications-updated" }));
}

function queueCheck(event) {
  running = running.catch(() => {}).then(checkNotifications);
  event.waitUntil(running);
}
self.addEventListener("install", event => event.waitUntil(self.skipWaiting()));
self.addEventListener("activate", event => event.waitUntil(self.clients.claim()));
self.addEventListener("push", queueCheck);
self.addEventListener("message", event => {
  if (event.data?.type === "helpdesk-check-notifications") queueCheck(event);
  if (event.data?.type === "helpdesk-notifications-resume") { paused = false; generation++; }
  if (event.data?.type === "helpdesk-notifications-suspend") {
    paused = true; generation++;
    event.waitUntil(running.catch(() => {}).then(async () => {
      (await self.registration.getNotifications()).forEach(item => item.close());
      event.ports[0]?.postMessage({ stopped: true });
    }));
  }
});
self.addEventListener("notificationclick", event => {
  event.notification.close();
  const data = event.notification.data;
  event.waitUntil((async () => {
    if (!data || !/^\/app\/(?:requester\/)?tickets\/[a-zA-Z0-9-]+$/.test(data.url)) return;
    // Re-check the session on click; another person may have since signed in.
    const session = await fetch("/api/web/session/me", { credentials: "same-origin", cache: "no-store" });
    if (!session.ok) { await self.clients.openWindow("/app/login"); return; }
    const payload = await session.json();
    const login = payload.data?.user_login ?? payload.user_login;
    if (login !== data.actor_id) { await self.clients.openWindow("/app"); return; }
    await fetch(`/api/web/notifications/${data.id}/read`, { method: "POST", credentials: "same-origin" });
    const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    const existing = windows.find(client => new URL(client.url).origin === self.location.origin && new URL(client.url).pathname.startsWith("/app"));
    if (existing) { await existing.navigate(data.url); await existing.focus(); }
    else await self.clients.openWindow(data.url);
  })());
});
