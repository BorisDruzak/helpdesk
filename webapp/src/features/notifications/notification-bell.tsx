import { Bell } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { notificationRequest } from "./api";
import { checkBrowserNotifications } from "./browser-push";
import { NotificationMenu } from "./notification-menu";

export function NotificationBell({ userLogin, requester }: { userLogin: string; requester: boolean }) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ left: 16, top: 80 });
  const client = useQueryClient();
  const count = useQuery({ queryKey: ["shell-notifications-unread", userLogin], retry: false, refetchInterval: 15_000,
    queryFn: async () => (await notificationRequest<{ unread_count: number }>("/unread_count")).unread_count });

  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    const check = () => { void checkBrowserNotifications().catch(() => {}); };
    const message = (event: MessageEvent) => {
      if (event.data?.type !== "helpdesk-notifications-updated") return;
      void client.invalidateQueries({ queryKey: ["shell-notifications-unread", userLogin] });
      void client.invalidateQueries({ queryKey: ["bell-notifications", userLogin] });
    };
    check();
    const timer = window.setInterval(check, 15_000);
    navigator.serviceWorker.addEventListener("message", message);
    return () => { window.clearInterval(timer); navigator.serviceWorker.removeEventListener("message", message); };
  }, [client, userLogin]);

  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node) && !menu.current?.contains(event.target as Node)) setOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") { setOpen(false); root.current?.querySelector("button")?.focus(); } };
    document.addEventListener("pointerdown", outside); document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", escape); };
  }, [open]);

  useLayoutEffect(() => {
    if (!open) return;
    const place = () => {
      const anchor = root.current?.getBoundingClientRect();
      if (!anchor) return;
      const width = Math.min(380, window.innerWidth - 32);
      setPosition({ left: Math.max(16, Math.min(anchor.right - width, window.innerWidth - width - 16)), top: anchor.bottom + 8 });
    };
    place();
    window.addEventListener("resize", place); window.addEventListener("scroll", place, true);
    return () => { window.removeEventListener("resize", place); window.removeEventListener("scroll", place, true); };
  }, [open]);

  const unread = count.data ?? 0;
  return <div className="relative" ref={root}>
    <button aria-label="Уведомления" aria-expanded={open} aria-haspopup="dialog" className={requester ? "relative flex h-9 w-9 items-center justify-center rounded-full hover:bg-brand-50" : "relative flex h-11 w-11 items-center justify-center rounded-full border border-border bg-white text-slate-500 hover:text-brand-700"} onClick={() => setOpen(value => !value)} title={count.isError ? "Не удалось обновить уведомления" : "Уведомления"} type="button">
      <Bell aria-hidden="true" className="h-4 w-4" />
      {unread > 0 ? <span className="absolute -right-1 -top-1 min-w-5 rounded-full bg-brand-700 px-1.5 py-0.5 text-[10px] font-bold leading-none text-white"><span aria-hidden="true">{unread > 99 ? "99+" : unread}</span><span className="sr-only">Новых событий: {unread}</span></span> : null}
      {count.isError ? <span className="sr-only">Не удалось обновить уведомления</span> : null}
    </button>
    {open ? createPortal(<div ref={menu} style={{ position: "fixed", left: position.left, top: position.top, zIndex: 60 }}><NotificationMenu key={userLogin} onClose={() => setOpen(false)} requester={requester} userLogin={userLogin} /></div>, document.body) : null}
  </div>;
}
