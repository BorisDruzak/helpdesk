import { Link, Navigate, useSearchParams } from "react-router-dom";
import { RegistrationWizard } from "./registration-wizard";
import { useSession } from "./session-provider";
import { useRegistrationPolicy } from "./use-registration-policy";
import { resolveNextWorkspacePath } from "./workspace-access";

export function RegisterPage() {
  const [params] = useSearchParams();
  const {session,status} = useSession();
  const enabled = useRegistrationPolicy();
  const switchAccount = params.get("switch_account") === "1";
  const next = params.get("next");
  const loginPath = next && (next==="/app" || next.startsWith("/app/")) ? `/app/login?next=${encodeURIComponent(next)}` : "/app/login";
  if(status === "authenticated" && !switchAccount) return <Navigate replace to={session?.actor_role==="user" ? "/app/requester" : resolveNextWorkspacePath(next,session) ?? "/app"} state={{registrationCompleted:session?.actor_role==="user"}}/>;
  return <main className="min-h-screen bg-app px-4 py-6 md:py-10">
    <section className="mx-auto max-w-xl space-y-5 rounded-3xl border border-border bg-white p-5 shadow-soft md:p-8" aria-labelledby="register-title">
      <header className="space-y-2"><p className="text-sm font-semibold text-brand-700">Helpdesk</p><h1 id="register-title" className="font-display text-2xl font-semibold">Регистрация сотрудника</h1>
        <p className="text-sm leading-6 text-slate-600">Заполните профиль и создайте пароль. После регистрации откроется ваш кабинет, где можно обратиться в поддержку.</p></header>
      {enabled === true ? <RegistrationWizard switchAccount={switchAccount}/> : <p role="status">{enabled===null ? "Проверяем доступность регистрации…" : "Самостоятельная регистрация недоступна. Обратитесь к администратору."}</p>}
      <p className="border-t pt-4 text-sm text-slate-600">Уже есть аккаунт? <Link className="font-semibold text-brand-700" to={loginPath}>Войти</Link></p>
    </section>
  </main>;
}
