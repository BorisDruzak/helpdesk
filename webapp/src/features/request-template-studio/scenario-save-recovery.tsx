import { useEffect, useRef, useState } from "react";
import { fetchCurrentSession } from "../auth/api";
import { Button } from "../../components/ui/button";

/** Recheck without remounting SessionProvider: an identity change would discard the draft. */
export function ScenarioSaveRecovery({ kind, actorLogin, disabled, onRetry }: {
  kind: "session" | "origin" | "forbidden"; actorLogin?: string; disabled: boolean; onRetry: () => void;
}) {
  const [checking, setChecking] = useState(false);
  const [notice, setNotice] = useState("");
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  async function verify() {
    if (checking || disabled) return;
    setChecking(true); setNotice("");
    try {
      const session = await fetchCurrentSession();
      if (!mounted.current) return;
      if (!session) setNotice("Вход ещё не выполнен. Войдите в отдельной вкладке и повторите проверку.");
      else if (!actorLogin || session.user_login !== actorLogin) setNotice("Вход выполнен под другой учётной записью. Для сохранения этих правок войдите в исходную учётную запись администратора.");
      else if (session.actor_role !== "admin") setNotice("У текущей учётной записи нет прав администратора. Правки остаются в этой вкладке.");
      else onRetry();
    } catch { if (mounted.current) setNotice("Не удалось проверить вход. Проверьте соединение; правки остаются в этой вкладке."); }
    finally { if (mounted.current) setChecking(false); }
  }
  return <div className="space-y-2">
    {kind === "session" && <a className="inline-flex min-h-10 items-center font-semibold underline" href="/app/login?next=%2Fapp%2Fadmin%2Frequest-template-studio" target="_blank" rel="noopener noreferrer">Войти в отдельной вкладке</a>}
    <div><Button variant="outline" disabled={disabled || checking} onClick={() => void verify()}>{checking ? "Проверяем вход…" : "Проверить вход и сохранить"}</Button></div>
    {notice && <p role="status">{notice}</p>}
  </div>;
}
