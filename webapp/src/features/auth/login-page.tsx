import { startTransition, useState, type FormEvent } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";

import { WebSessionApiError } from "./api";
import { useSession } from "./session-provider";
import { resolveNextWorkspacePath } from "./workspace-access";


function resolveNextPath(nextParam: string | null, session: ReturnType<typeof useSession>["session"]) {
  return resolveNextWorkspacePath(nextParam, session) ?? "/app";
}


export function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { login, session, status } = useSession();
  const [loginValue, setLoginValue] = useState("");
  const [passwordValue, setPasswordValue] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const nextPath = resolveNextPath(searchParams.get("next"), session);

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
      startTransition(() => {
        navigate(resolveNextPath(searchParams.get("next"), nextSession), { replace: true });
      });
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

  return (
    <section className="auth-page">
      <div className="auth-card">
        <p className="app-shell__eyebrow">pc_client</p>
        <h1>Вход в рабочие места</h1>
        <p className="auth-card__description">
          Новый интерфейс `/app/*` использует серверную cookie-сессию. Войдите под своей ролью,
          чтобы открыть поддержку или администрирование без токена в `localStorage`.
        </p>
        <form className="auth-form" onSubmit={handleSubmit}>
          <label className="auth-field">
            <span>Логин</span>
            <input
              autoComplete="username"
              name="login"
              onChange={(event) => setLoginValue(event.target.value)}
              type="text"
              value={loginValue}
            />
          </label>
          <label className="auth-field">
            <span>Пароль</span>
            <input
              autoComplete="current-password"
              name="password"
              onChange={(event) => setPasswordValue(event.target.value)}
              type="password"
              value={passwordValue}
            />
          </label>
          {errorMessage ? (
            <p aria-live="polite" className="auth-form__error">
              {errorMessage}
            </p>
          ) : null}
          <button className="auth-form__submit" disabled={isSubmitting} type="submit">
            {isSubmitting ? "Входим..." : "Войти"}
          </button>
        </form>
      </div>
    </section>
  );
}
