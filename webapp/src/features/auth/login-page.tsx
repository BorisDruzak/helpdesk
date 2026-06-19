import { LockKeyhole, ShieldCheck, Ticket } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";

import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { requestPasswordReset, WebSessionApiError } from "./api";
import { useSession } from "./session-provider";
import { resolveNextWorkspacePath } from "./workspace-access";

function resolveNextPath(nextParam: string | null, session: ReturnType<typeof useSession>["session"]) {
  return resolveNextWorkspacePath(nextParam, session) ?? "/app";
}

function isSafeAppNextPath(value: string | null) {
  return Boolean(value && (value === "/app" || value.startsWith("/app/")) && !value.startsWith("//"));
}

function registerPath(nextParam: string | null) {
  if (!isSafeAppNextPath(nextParam)) {
    return "/app/register";
  }
  const params = new URLSearchParams({ next: nextParam as string });
  return `/app/register?${params.toString()}`;
}

export function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { login, session, status } = useSession();
  const [loginValue, setLoginValue] = useState("");
  const [passwordValue, setPasswordValue] = useState("");
  const [passwordResetLogin, setPasswordResetLogin] = useState("");
  const [showPasswordReset, setShowPasswordReset] = useState(searchParams.get("forgot_password") === "1");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [passwordResetMessage, setPasswordResetMessage] = useState<string | null>(null);
  const [passwordResetError, setPasswordResetError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isPasswordResetSubmitting, setIsPasswordResetSubmitting] = useState(false);

  const nextPath = resolveNextPath(searchParams.get("next"), session);
  const registrationComplete = searchParams.get("registered") === "1";

  if (status === "authenticated") {
    return <Navigate replace to={nextPath} />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage(null);
    setIsSubmitting(true);

    try {
      const nextSession = await login({
        login: loginValue,
        password: passwordValue
      });

      navigate(resolveNextPath(searchParams.get("next"), nextSession), { replace: true });
    } catch (error) {
      if (error instanceof WebSessionApiError) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage("Не удалось выполнить вход. Повторите попытку.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handlePasswordResetSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPasswordResetMessage(null);
    setPasswordResetError(null);
    const login = passwordResetLogin.trim();
    if (!login) {
      setPasswordResetError("Введите логин для восстановления.");
      return;
    }
    setIsPasswordResetSubmitting(true);
    try {
      await requestPasswordReset(login);
      setPasswordResetMessage("Заявка отправлена администратору.");
    } catch (error) {
      setPasswordResetError(error instanceof Error ? error.message : "Не удалось отправить заявку.");
    } finally {
      setIsPasswordResetSubmitting(false);
    }
  }

  return (
    <section className="min-h-screen bg-app px-4 py-6 md:px-6 md:py-8">
      <div className="mx-auto grid min-h-[calc(100vh-3rem)] max-w-7xl overflow-hidden rounded-[2rem] border border-border bg-white shadow-soft lg:grid-cols-[minmax(340px,0.9fr)_minmax(0,1fr)]">
        <div className="flex flex-col justify-between bg-brand-700 px-6 py-8 text-white md:px-8 md:py-10">
          <div>
            <div className="flex h-14 w-14 items-center justify-center rounded-3xl bg-white text-lg font-black tracking-[0.2em] text-brand-700 shadow-soft">
              PC
            </div>
            <p className="mt-8 text-[11px] font-semibold uppercase tracking-[0.28em] text-brand-100/70">
              Единый workspace
            </p>
            <h1 className="mt-3 font-display text-3xl font-semibold leading-tight md:text-4xl">
              Вход в рабочие места
            </h1>
            <p className="mt-4 max-w-md text-sm leading-7 text-brand-50/80">
              Новый SaaS-shell объединяет поддержку и администрирование в одном продукте. Сессия открывается через серверный cookie-boundary и новые маршруты `/app/*`.
            </p>
          </div>

          <div className="space-y-4">
            {[
              {
                icon: Ticket,
                title: "Support workspace",
                description: "Список тикетов, карточка и быстрые проверки сроков ответа."
              },
              {
                icon: ShieldCheck,
                title: "Admin workspace",
                description: "Инвентарь, observer, модули и forms builder."
              },
              {
                icon: LockKeyhole,
                title: "Безопасный доступ",
                description: "Одна cookie-сессия без ручного переключения legacy shell."
              }
            ].map((item) => {
              const Icon = item.icon;

              return (
                <div key={item.title} className="rounded-[1.4rem] border border-white/10 bg-white/10 px-4 py-4">
                  <div className="flex items-start gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white/12">
                      <Icon className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="font-semibold">{item.title}</p>
                      <p className="mt-1 text-sm leading-6 text-brand-50/75">{item.description}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="flex items-center justify-center px-6 py-8 md:px-10">
          <div className="w-full max-w-md space-y-8">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-brand-700">
                Авторизация
              </p>
              <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-slate-950">
                Добро пожаловать
              </h2>
              <p className="mt-3 text-sm leading-7 text-slate-500">
                Используйте служебный логин, чтобы открыть нужную рабочую зону.
              </p>
            </div>

            <form className="space-y-5" onSubmit={handleSubmit}>
              {registrationComplete ? (
                <p aria-live="polite" className="rounded-[1rem] bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                  Аккаунт создан. Войдите, чтобы продолжить настройку доступа.
                </p>
              ) : null}

              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-800">Логин</span>
                <Input
                  autoComplete="username"
                  name="login"
                  onChange={(event) => setLoginValue(event.target.value)}
                  value={loginValue}
                />
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-800">Пароль</span>
                <Input
                  autoComplete="current-password"
                  name="password"
                  onChange={(event) => setPasswordValue(event.target.value)}
                  type="password"
                  value={passwordValue}
                />
              </label>

              {errorMessage ? (
                <p aria-live="polite" className="rounded-[1rem] bg-rose-50 px-4 py-3 text-sm text-rose-700">
                  {errorMessage}
                </p>
              ) : null}

              <Button className="w-full" disabled={isSubmitting} size="lg" type="submit">
                {isSubmitting ? "Входим..." : "Войти"}
              </Button>
            </form>

            <div className="space-y-3 rounded-[1.2rem] bg-surface-subtle px-4 py-4 text-sm text-slate-500">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <span>Не получается войти?</span>
                <button
                  className="font-semibold text-brand-700 hover:text-brand-900"
                  onClick={() => setShowPasswordReset((current) => !current)}
                  type="button"
                >
                  Забыли пароль?
                </button>
              </div>
              {showPasswordReset ? (
                <form className="space-y-3" onSubmit={handlePasswordResetSubmit}>
                  <label className="block space-y-2">
                    <span className="text-sm font-medium text-slate-800">Логин для восстановления</span>
                    <Input
                      autoComplete="username"
                      name="password_reset_login"
                      onChange={(event) => setPasswordResetLogin(event.target.value)}
                      value={passwordResetLogin}
                    />
                  </label>
                  {passwordResetError ? (
                    <p aria-live="polite" className="rounded-[1rem] bg-rose-50 px-4 py-3 text-sm text-rose-700">
                      {passwordResetError}
                    </p>
                  ) : null}
                  {passwordResetMessage ? (
                    <p aria-live="polite" className="rounded-[1rem] bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                      {passwordResetMessage}
                    </p>
                  ) : null}
                  <Button disabled={isPasswordResetSubmitting} size="sm" type="submit" variant="outline">
                    {isPasswordResetSubmitting ? "Отправляем..." : "Отправить заявку"}
                  </Button>
                </form>
              ) : null}
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3">
                <span>Еще нет аккаунта?</span>
                <Link className="font-semibold text-brand-700 hover:text-brand-900" to={registerPath(searchParams.get("next"))}>
                  Создать аккаунт
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
