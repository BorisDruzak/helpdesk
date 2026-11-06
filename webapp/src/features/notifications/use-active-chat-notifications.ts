import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { notificationRequest } from "./api";

// A URL alone does not mean the conversation loaded or is actually being read.
export function visibleChatTicket(): string | null {
  if (document.visibilityState !== "visible" || !document.hasFocus() || document.querySelector('dialog[open], [aria-modal="true"][role="dialog"], [aria-modal="true"][role="alertdialog"]')) return null;
  return document.querySelector<HTMLElement>("[data-helpdesk-active-chat]")?.dataset.helpdeskActiveChat ?? null;
}

export function useActiveChatNotifications(userLogin: string) {
  const { pathname } = useLocation();
  const client = useQueryClient();
  useEffect(() => {
    let alive = true, busy = false;
    const refresh = () => {
      void client.invalidateQueries({ queryKey: ["bell-notifications", userLogin] });
      void client.invalidateQueries({ queryKey: ["shell-notifications-unread", userLogin] });
    };
    const read = async () => {
      const ticket = visibleChatTicket();
      if (!ticket || busy) return;
      busy = true;
      try {
        const result = await notificationRequest<{ updated: number }>("/read_ticket", { ticket_id: ticket, expected_actor_id: userLogin });
        if (alive && result.updated > 0) {
          refresh();
          const registration = await navigator.serviceWorker?.getRegistration("/");
          (await registration?.getNotifications())?.filter(item => item.data?.actor_id === userLogin && item.data?.url?.endsWith(`/tickets/${ticket}`)).forEach(item => item.close());
        }
      } catch { /* Keep unread state and retry on focus/poll; never fake a read. */ }
      finally { busy = false; }
    };
    const probe = (event: MessageEvent) => {
      if (event.data?.type !== "helpdesk-is-chat-visible") return;
      event.ports[0]?.postMessage({ active: event.data.actor_id === userLogin && visibleChatTicket() === event.data.ticket_id });
      event.ports[0]?.close();
    };
    const update = () => { void read(); };
    update();
    const timer = window.setInterval(update, 5000);
    window.addEventListener("focus", update); document.addEventListener("visibilitychange", update);
    navigator.serviceWorker?.addEventListener("message", probe);
    return () => {
      alive = false; window.clearInterval(timer);
      window.removeEventListener("focus", update); document.removeEventListener("visibilitychange", update);
      navigator.serviceWorker?.removeEventListener("message", probe);
    };
  }, [client, pathname, userLogin]);
}
