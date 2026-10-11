import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "../../components/ui/button";
import { RequestStudioApiError } from "./api";
import { previewScenarioPublication, publishScenario, type ScenarioPublicationPreview } from "./scenario-api";

function humanValue(value: unknown): string {
  if (value === null || value === undefined) return "Не задано";
  if (typeof value === "boolean") return value ? "Да" : "Нет";
  if (Array.isArray(value)) return value.map(item => {
    if (item && typeof item === "object" && "title" in item) return String(item.title);
    return humanValue(item);
  }).join(", ");
  if (typeof value === "object") return Object.entries(value).map(([key, item]) => `${key}: ${humanValue(item)}`).join("; ");
  return String(value);
}
const labels: Record<string, string> = { title: "Название", description: "Описание", blocks: "Шаги и вопросы", entry_block_id: "Первый шаг", category_id: "Категория", process_binding: "Обработка обращения", service_code: "Раздел", offering_full_code: "Услуга", scenario_key: "Сценарий", schema_version: "Формат" };

export function ScenarioPublication({ id, revision, dirty, disabled }: { id: string; revision: number; dirty: boolean; disabled: boolean }) {
  const cache = useQueryClient();
  const [preview, setPreview] = useState<ScenarioPublicationPreview | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const sequence = useRef(0);
  useEffect(() => {
    sequence.current++;
    setPreview(null); setConfirmed(false); setError(""); setMessage(""); setBusy(false);
    return () => { sequence.current++; };
  }, [id, revision, dirty, disabled]);
  async function prepare() {
    const current = ++sequence.current;
    setBusy(true); setError(""); setPreview(null); setConfirmed(false); setMessage("");
    try { const value = await previewScenarioPublication(id, revision); if (current === sequence.current) setPreview(value); }
    catch { if (current === sequence.current) setError("Не удалось проверить публикацию. Повторите проверку."); }
    finally { if (current === sequence.current) setBusy(false); }
  }
  async function publish() {
    if (!preview?.confirmation_token || !confirmed || dirty || disabled || busy) return;
    const current = ++sequence.current;
    setBusy(true); setError("");
    try {
      const result = await publishScenario(id, revision, preview.confirmation_token);
      if (current !== sequence.current) return;
      setPreview(null); setConfirmed(false); setMessage(`Опубликована версия ${result.version.version}.`);
      await cache.invalidateQueries({ queryKey: ["scenario-catalog"] });
      await cache.invalidateQueries({ queryKey: ["scenario-detail", id] });
    } catch (cause) {
      if (current !== sequence.current) return;
      setPreview(null); setConfirmed(false);
      setError(cause instanceof RequestStudioApiError && cause.status === 409
        ? "Черновик, обработка или срок подтверждения изменились. Подготовьте публикацию заново."
        : "Сценарий не опубликован. Подготовьте публикацию заново.");
    } finally { if (current === sequence.current) setBusy(false); }
  }
  return <div className="min-w-0 space-y-4" aria-busy={busy}>
    <h2 className="text-lg font-semibold">Готовность к публикации</h2>
    <p>Проверка охватывает ветви и действующую обработку. Перед публикацией проверьте изменения.</p>
    <Button disabled={dirty || disabled || busy} onClick={() => void prepare()}>Подготовить публикацию</Button>
    {dirty && <p>Сначала сохраните изменения.</p>}
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    {preview && <>
      <p>Policy Health: {preview.health.health_status}. Готовность: {preview.readiness.can_publish ? "проверена" : "есть препятствия"}.</p>
      <p>Проверено исходов: {preview.readiness.variants_checked}.</p>
      {preview.readiness.issues.map((issue, index) => <p role="alert" key={`${issue.code}-${index}`}>{issue.message}</p>)}
      <h3 className="font-semibold">Изменения относительно опубликованной версии</h3>
      {preview.diff.length ? <dl className="min-w-0 space-y-3">{preview.diff.map(change => <div key={change.path} className="min-w-0 break-words rounded border p-3">
        <dt className="font-medium">{labels[change.path] || change.path}</dt><dd className="grid gap-1"><span>{humanValue(change.before)}</span><span>{humanValue(change.after)}</span></dd>
      </div>)}</dl> : <p>Содержимое сценария не изменилось. Будет создана новая версия с проверенной обработкой.</p>}
      {preview.readiness.can_publish && preview.confirmation_token && <div className="grid gap-3">
        <label className="flex items-start gap-2"><input type="checkbox" checked={confirmed} disabled={busy || dirty || disabled} onChange={event => setConfirmed(event.target.checked)} />Изменения проверены, подтверждаю публикацию</label>
        <Button disabled={!confirmed || busy || dirty || disabled} onClick={() => void publish()}>Опубликовать сценарий</Button>
      </div>}
    </>}
  </div>;
}
