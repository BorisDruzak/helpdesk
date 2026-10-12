import { useEffect, useRef, useState } from "react";
import { Button } from "../../components/ui/button";
import { fetchScenarioVersions, rollbackScenarioDraft, type ScenarioDetail } from "./scenario-api";

export function ScenarioVersionHistory({ id, revision, disabled, onAccept }: {
  id: string; revision: number; disabled: boolean; onAccept: (value: ScenarioDetail) => void;
}) {
  const [versions, setVersions] = useState<Awaited<ReturnType<typeof fetchScenarioVersions>> | null>(null);
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const sequence = useRef(0);
  useEffect(() => {
    sequence.current++; setVersions(null); setSelected(""); setError(""); setBusy(false);
    return () => { sequence.current++; };
  }, [id, revision, disabled]);
  async function load() {
    const current = ++sequence.current;
    setBusy(true); setError(""); setMessage("");
    try { const value = await fetchScenarioVersions(id); if (current === sequence.current) setVersions(value); }
    catch { if (current === sequence.current) setError("История не загружена. Повторите загрузку."); }
    finally { if (current === sequence.current) setBusy(false); }
  }
  async function restore() {
    if (!selected || busy || disabled || !versions?.some(item => item.id === selected)) return;
    const current = ++sequence.current;
    setBusy(true); setError("");
    try {
      const value = await rollbackScenarioDraft(id, revision, selected);
      if (current !== sequence.current) return;
      setSelected(""); setVersions(null);
      setMessage("Версия скопирована в черновик. Перед публикацией проверьте её заново.");
      onAccept(value);
    } catch { if (current === sequence.current) setError("Черновик не восстановлен. Загрузите актуальный сценарий и повторите."); }
    finally { if (current === sequence.current) setBusy(false); }
  }
  return <section className="grid gap-3 border-t pt-4" aria-label="История опубликованных версий" aria-busy={busy}>
    <Button variant="ghost" disabled={busy} onClick={() => void load()}>История версий</Button>
    {versions && (versions.length ? <>
      <p>Выбранная версия заменит сохранённый черновик. Действующая публикация изменится только после новой проверки и подтверждения.</p>
      <label>Версия для черновика<select className="block w-full rounded border p-2" value={selected} disabled={disabled || busy} onChange={event => setSelected(event.target.value)}>
        <option value="">Выберите версию</option>
        {versions.map(item => <option key={item.id} value={item.id}>Версия {item.version} — {item.state === "published" ? "опубликована" : item.state === "retired" ? "ранее опубликована" : "отозвана"}</option>)}
      </select></label>
      <Button disabled={disabled || busy || !selected} onClick={() => void restore()}>Вернуть выбранную версию в черновик</Button>
    </> : <p>Опубликованных версий пока нет.</p>)}
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
  </section>;
}
