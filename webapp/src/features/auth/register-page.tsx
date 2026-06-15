import { KeyRound, LinkIcon, ShieldCheck, UserPlus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";

import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { registerWebSessionAccount, WebSessionApiError } from "./api";
import { useSession } from "./session-provider";
import { resolveNextWorkspacePath } from "./workspace-access";

function initialDeviceCode(searchParams: URLSearchParams) {
  return searchParams.get("device_link_code") ?? searchParams.get("pairing_code") ?? "";
}

export function RegisterPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { session, status } = useSession();
  const [loginValue, setLoginValue] = useState("");
  const [passwordValue, setPasswordValue] = useState("");
  const [passwordRepeatValue, setPasswordRepeatValue] = useState("");
  const [deviceLinkCode, setDeviceLinkCode] = useState(() => initialDeviceCode(searchParams));
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const authenticatedNextPath = resolveNextWorkspacePath(searchParams.get("next"), session) ?? "/app";

  if (status === "authenticated") {
    return <Navigate replace to={authenticatedNextPath} />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage(null);

    const login = loginValue.trim();
    if (!login) {
      setErrorMessage("Введите логин.");
      return;
    }
    if (!passwordValue) {
      setErrorMessage("Введите пароль.");
      return;
    }
    if (passwordValue !== passwordRepeatValue) {
      setErrorMessage("Пароли не совпадают.");
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await registerWebSessionAccount({
        login,
        password: passwordValue,
        passwordRepeat: passwordRepeatValue,
        deviceLinkCode
      });

      navigate(result.next_path || "/app/login?registered=1", { replace: true });
    } catch (error) {
      if (error instanceof WebSessionApiError) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage("Не удалось создать аккаунт. Повторите попытку.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="min-h-screen bg-app px-4 py-6 md:px-6 md:py-8">
      <div className="mx-auto grid min-h-[calc(100vh-3rem)] max-w-7xl overflow-hidden rounded-[2rem] border border-border bg-white shadow-soft lg:grid-cols-[minmax(340px,0.9fr)_minmax(0,1fr)]">
        <div className="flex flex-col justify-between bg-slate-950 px-6 py-8 text-white md:px-8 md:py-10">
          <div>
            <div className="flex h-14 w-14 items-center justify-center rounded-3xl bg-white text-lg font-black tracking-[0.2em] text-slate-950 shadow-soft">
              PC
            </div>
            <p className="mt-8 text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-300">
              Web-first доступ
            </p>
            <h1 className="mt-3 font-display text-3xl font-semibold leading-tight md:text-4xl">
              Новый аккаунт заявителя
            </h1>
            <p className="mt-4 max-w-md text-sm leading-7 text-slate-300">
              Создайте учетную запись для браузерного кабинета. Данные сотрудника и устройство подключаются отдельными шагами после входа.
            </p>
          </div>

          <div className="space-y-4">
            {[
              {
                icon: UserPlus,
                title: "Только аккаунт",
                description: "На этом шаге нужны логин и пароль без служебных атрибутов."
              },
              {
                icon: LinkIcon,
                title: "Код устройства опционален",
                description: "Код проверяется сейчас, но активная привязка оформляется позже."
              },
              {
                icon: ShieldCheck,
                title: "Проверка администратором",
                description: "Доступ к устройствам и рабочим данным остается под контролем политики."
              }
            ].map((item) => {
              const Icon = item.icon;

              return (
                <div key={item.title} className="rounded-[1.4rem] border border-white/10 bg-white/8 px-4 py-4">
                  <div className="flex items-start gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white/10">
                      <Icon className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="font-semibold">{item.title}</p>
                      <p className="mt-1 text-sm leading-6 text-slate-300">{item.description}</p>
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
                Регистрация
              </p>
              <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-slate-950">
                Создать аккаунт
              </h2>
              <p className="mt-3 text-sm leading-7 text-slate-500">
                После создания войдите с новым логином и продолжите настройку доступа.
              </p>
            </div>

            <form className="space-y-5" onSubmit={handleSubmit}>
              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-800">Логин</span>
                <Input
                  autoComplete="username"
                  className="mt-2 block w-full"
                  name="login"
                  onChange={(event) => setLoginValue(event.target.value)}
                  value={loginValue}
                />
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-800">Пароль</span>
                <Input
                  autoComplete="new-password"
                  className="mt-2 block w-full"
                  name="password"
                  onChange={(event) => setPasswordValue(event.target.value)}
                  type="password"
                  value={passwordValue}
                />
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-800">Повторите пароль</span>
                <Input
                  autoComplete="new-password"
                  className="mt-2 block w-full"
                  name="password_repeat"
                  onChange={(event) => setPasswordRepeatValue(event.target.value)}
                  type="password"
                  value={passwordRepeatValue}
                />
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-800">Код привязки устройства</span>
                <Input
                  autoComplete="off"
                  className="mt-2 block w-full"
                  name="device_link_code"
                  onChange={(event) => setDeviceLinkCode(event.target.value)}
                  placeholder="Необязательно"
                  value={deviceLinkCode}
                />
              </label>

              {errorMessage ? (
                <p aria-live="polite" className="rounded-[1rem] bg-rose-50 px-4 py-3 text-sm text-rose-700">
                  {errorMessage}
                </p>
              ) : null}

              <Button
                className="w-full"
                disabled={isSubmitting}
                leadingIcon={<KeyRound className="h-4 w-4" />}
                size="lg"
                type="submit"
              >
                {isSubmitting ? "Создаем..." : "Создать аккаунт"}
              </Button>
            </form>

            <div className="flex items-center justify-between gap-3 rounded-[1.2rem] bg-surface-subtle px-4 py-4 text-sm text-slate-500">
              <span>Уже есть аккаунт?</span>
              <Link className="font-semibold text-brand-700 hover:text-brand-900" to="/app/login">
                Войти
              </Link>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
