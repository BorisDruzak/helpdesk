import { LockKeyhole, ShieldCheck, Ticket } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";

import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { requestPasswordReset, WebSessionApiError } from "./api";
import { useSession } from "./session-provider";
import { resolveNextWorkspacePath } from "./workspace-access";
import { useSessionCapabilities } from "./use-session-capabilities";
import { safeWorktimeContinuation } from "./worktime-navigation";

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

function ssoErrorMessage(code: string | null) {
  switch (code) {
    case "identity_unlinked":
      return "Доменная учётная запись пока не связана с профилем Helpdesk. Обратитесь к администратору для проверки связи с вашим существующим профилем.";
    case "identity_unavailable":
      return "Вход с этой доменной учётной записью недоступен. Обратитесь к администратору.";
    case "oidc_unavailable":
      return "Сервис доменного входа временно недоступен. Повторите попытку позже или войдите по логину и паролю.";
    case "rate_limited":
      return "Слишком много попыток доменного входа. Подождите минуту и повторите попытку.";
    case "oidc_disabled":
      return "Доменный вход сейчас недоступен. Используйте логин и пароль.";
    case "oidc_authentication_failed":
      return "Не удалось завершить доменный вход. Повторите попытку или войдите по логину и паролю.";
    default:
      return null;
  }
}

export function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { login, session, status } = useSession();
  const capabilities = useSessionCapabilities();
  const registrationEnabled = capabilities?.self_registration_enabled ?? null;
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
  const ssoError = ssoErrorMessage(searchParams.get("sso_error"));

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
        <div className="hidden flex-col justify-between bg-brand-700 px-6 py-8 text-white md:px-8 md:py-10 lg:flex">
          <div>
            <div className="flex h-14 w-14 items-center justify-center rounded-3xl bg-white text-lg font-black tracking-[0.2em] text-brand-700 shadow-soft">
              PC
            </div>
            <p className="mt-8 text-[11px] font-semibold uppercase tracking-[0.28em] text-brand-100/70">
              Служба поддержки
            </p>
            <h1 className="mt-3 font-display text-3xl font-semibold leading-tight md:text-4xl">
              Поддержка сотрудников
            </h1>
            <p className="mt-4 max-w-md text-sm leading-7 text-brand-50/80">
              Создавайте обращения, следите за ответами и находите помощь в своём рабочем кабинете.
            </p>
          </div>

          <div className="space-y-4">
            {[
              {
                icon: Ticket,
                title: "Помощь и обращения",
                description: "Ваши обращения, переписка и ответы специалистов."
              },
              {
                icon: ShieldCheck,
                title: "Рабочие сервисы",
                description: "Устройства, профиль и доступные вам инструменты."
              },
              {
                icon: LockKeyhole,
                title: "Безопасный доступ",
                description: "Вход с учётной записью вашей организации."
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
                Войдите, чтобы обратиться в поддержку или продолжить работу.
              </p>
            </div>

            {ssoError ? <p role="alert" className="rounded-[1rem] bg-rose-50 px-4 py-3 text-sm leading-6 text-rose-700">{ssoError}</p> : null}

            {capabilities?.sso_enabled ? <div className="space-y-3">
              <a className="flex min-h-12 items-center justify-center rounded-pill bg-brand-700 px-5 py-3 text-center text-sm font-semibold text-white hover:bg-brand-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-700" href={'/api/web/session/oidc/login'+(safeWorktimeContinuation(searchParams.get('next')) ? '?'+new URLSearchParams({next:searchParams.get('next')!}).toString() : '')}>
                Войти через AD
              </a>
              <p className="text-center text-sm text-slate-600">Используйте свою доменную учётную запись.</p>
              <p className="text-center text-sm text-slate-500">Или используйте существующий логин и пароль</p>
            </div> : null}

            <form className="space-y-5" onSubmit={handleSubmit}>
              {registrationComplete ? (
                <p aria-live="polite" className="rounded-[1rem] bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                  Аккаунт создан. Войдите, чтобы продолжить настройку доступа.
                </p>
              ) : null}

              <label className="block space-y-2">
                <span className="block text-sm font-medium text-slate-800">Логин</span>
                <Input
                  className="w-full"
                  autoComplete="username"
                  name="login"
                  onChange={(event) => setLoginValue(event.target.value)}
                  value={loginValue}
                />
              </label>

              <label className="block space-y-2">
                <span className="block text-sm font-medium text-slate-800">Пароль</span>
                <Input
                  className="w-full"
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
              {registrationEnabled === true ? <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3">
                <span>Еще нет аккаунта?</span>
                <Link className="font-semibold text-brand-700 hover:text-brand-900" to={registerPath(searchParams.get("next"))}>
                  Создать аккаунт
                </Link>
              </div> : <p role="status" className="border-t border-border pt-3">{registrationEnabled === null
                ? "Проверяем доступность регистрации…"
                : "Самостоятельная регистрация недоступна. Обратитесь к администратору."}</p>}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
