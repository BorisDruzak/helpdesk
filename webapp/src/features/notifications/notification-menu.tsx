import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { fetchBellNotifications, notificationRequest, safeNotificationUrl } from "./api";
import { BrowserPushControl } from "./browser-push-control";

export function NotificationMenu({ userLogin, requester, onClose }: { userLogin: string; requester: boolean; onClose: () => void }) {
  const client = useQueryClient();
  const [error, setError] = useState("");
  const list = useQuery({ queryKey: ["bell-notifications", userLogin], queryFn: fetchBellNotifications, retry: false, refetchInterval: 15_000 });
  async function markRead(id?: number) {
    try {
      await notificationRequest(id ? `/${id}/read` : "/read_all", {});
      await Promise.all([client.invalidateQueries({ queryKey: ["bell-notifications", userLogin] }), client.invalidateQueries({ queryKey: ["shell-notifications-unread"] })]);
    } catch { setError("Не удалось отметить уведомления прочитанными."); }
  }
  return <section role="dialog" aria-label="События обращений" className="w-[min(380px,calc(100vw-2rem))] overflow-hidden rounded-xl border border-border bg-white text-sm shadow-lg">
    <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3"><h2 className="font-semibold text-slate-950">Уведомления</h2><button aria-label="Закрыть уведомления" className="text-slate-600" onClick={onClose} type="button">✕</button></div>
    <div className="max-h-[min(340px,50vh)] overflow-y-auto">
      {list.isPending ? <p className="px-4 py-3" role="status">Загружаем уведомления…</p> : null}
      {list.isError ? <p className="px-4 py-3 text-rose-700" role="status">Не удалось загрузить уведомления. <button className="underline" onClick={() => void list.refetch()} type="button">Повторить</button></p> : null}
      {list.isSuccess && !list.data.length ? <p className="px-4 py-3 text-slate-600">Уведомлений пока нет</p> : null}
      {list.data?.map(item => {
        const url = safeNotificationUrl(item.url);
        return <div className={`border-b border-border/60 ${item.is_read ? "" : "bg-brand-50"}`} key={item.id}>
          {url ? <Link className="block px-4 py-3 hover:bg-brand-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-700" onClick={() => { void markRead(item.id); onClose(); }} to={url}><span className="block font-semibold">{!item.is_read ? <span aria-label="Не прочитано">● </span> : null}{item.title}</span><span className="mt-1 block text-xs text-slate-600">{item.body}</span></Link> : <p className="px-4 py-3">{item.title}</p>}
        </div>;
      })}
    </div>
    {error ? <p className="px-4 py-2 text-rose-700" role="alert">{error}</p> : null}
    <div className="flex flex-wrap justify-between gap-2 px-4 py-3"><Link className="text-brand-700 underline" onClick={onClose} to={requester ? "/app/requester/tickets" : "/app/tickets"}>{requester ? "Мои обращения" : "Все обращения"}</Link>{list.data?.some(item => !item.is_read) ? <button className="text-brand-700 underline" onClick={() => void markRead()} type="button">Прочитать все</button> : null}</div>
    <BrowserPushControl key={userLogin} userLogin={userLogin} />
  </section>;
}
