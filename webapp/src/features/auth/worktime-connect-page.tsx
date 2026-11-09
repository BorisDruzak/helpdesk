import { useEffect } from "react";
import { Link,Navigate,useLocation } from "react-router-dom";
import { useSession } from "./session-provider";
import { openWorktimeAuthorization,worktimeAuthorizePath } from "./worktime-navigation";

export function WorktimeConnectPage(){
  const {session,status}=useSession();
  const location=useLocation();
  const target=worktimeAuthorizePath(location.search,session?.worktime_portal_url);
  const ready=status==='authenticated' && session?.worktime_handoff_enabled && target;
  useEffect(()=>{if(ready)openWorktimeAuthorization(ready);},[ready]);
  if(status==='loading')return <main className="p-6" role="status">Проверяем вход…</main>;
  if(status==='anonymous')return <Navigate replace to={'/app/login?'+new URLSearchParams({next:location.pathname+location.search}).toString()}/>;
  if(!ready)return <main className="mx-auto max-w-xl space-y-4 p-6"><h1 className="text-2xl font-semibold">Рабочее время</h1><p role="alert">Не удалось продолжить переход. Откройте «Рабочее время» из вашего кабинета ещё раз.</p><Link to="/app/requester">Вернуться в кабинет</Link></main>;
  return <main className="mx-auto max-w-xl space-y-4 p-6"><h1 className="text-2xl font-semibold">Рабочее время</h1><p role="status">Открываем ваш кабинет без повторного ввода пароля…</p><a className="font-semibold text-brand-700" href={ready}>Продолжить в WorkTime</a></main>;
}
