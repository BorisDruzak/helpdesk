import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "../../components/ui/button";
import { RequestStudioApiError } from "./api";
import { previewScenarioPublication, publishScenario, type ScenarioPublicationPreview } from "./scenario-api";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { ScenarioPublicationSummary } from "./scenario-publication-summary";
import { scenarioIssueDestination, type ScenarioIssueDestination } from "./scenario-issue-navigation";

function changeLabel(path: string, definition?: ScenarioDraftDefinition): string {
  const parts = path.split(".");
  if (parts[0] === "blocks") {
    if (parts[1] === "order") return "Порядок шагов";
    const block = definition?.blocks?.find(item => item.id === parts[1]);
    const field = block?.kind === "form_page" ? block.fields.find(item => item.key === parts[3]) : undefined;
    return field ? `Вопрос «${field.label}»` : block ? `Шаг «${block.title}»` : "Состав шагов и вопросов";
  }
  if (parts[0] === "entry_points") {
    const entry = definition?.entry_points?.find(item => item.key === parts[1]);
    return entry ? `Пункт каталога «${entry.title}»` : "Состав пунктов каталога";
  }
  return ({ editor_layout: "Расположение блоков", process_binding: "Правила обработки", category_id: "Категория услуги",
    service_code: "Раздел каталога", entry_block_id: "Вход в маршрут", publish_offering: "Публикация услуги", offering: "Доступность услуги" } as Record<string, string>)[parts[0]] ?? "Настройки услуги";
}

export function ScenarioPublication({ id, revision, dirty, disabled, definition, offeringTitle, onIssue }: { id: string; revision: number; dirty: boolean; disabled: boolean; definition?: ScenarioDraftDefinition; offeringTitle?: string; onIssue?: (destination: ScenarioIssueDestination) => void }) {
  const cache = useQueryClient();
  const [preview, setPreview] = useState<ScenarioPublicationPreview | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [published, setPublished] = useState<ScenarioDraftDefinition | null>(null);
  const sequence = useRef(0);
  useEffect(() => {
    sequence.current++;
    setPreview(null); setConfirmed(false); setError(""); setMessage(""); setPublished(null); setBusy(false);
    return () => { sequence.current++; };
  }, [id, revision, dirty, disabled]);
  async function prepare() {
    const current = ++sequence.current;
    setBusy(true); setError(""); setPreview(null); setConfirmed(false); setMessage(""); setPublished(null);
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
      setPublished(result.version.definition ?? result.draft?.definition ?? definition ?? null);
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
    {published && <a className="inline-block text-brand-700 underline" target="_blank" rel="noopener noreferrer" href={`/app/requester/new?${new URLSearchParams({ offering: published.offering_full_code })}`}>Открыть сценарий сотрудника</a>}
    {(published || definition) && <ScenarioPublicationSummary definition={(published || definition)!} offeringTitle={offeringTitle} />}
    {preview && <>
      <p>Проверка правил обработки: {preview.health.health_status === "ok" ? "пройдена" : "есть замечания"}. Готовность: {preview.readiness.can_publish ? "проверена" : "есть препятствия"}.</p>
      <p>Проверено исходов: {preview.readiness.variants_checked}.</p>
      {preview.readiness.issues.map((issue, index) => {
        const destination = definition ? scenarioIssueDestination(issue, definition) : null;
        return <div key={`${issue.code}-${index}`} className="space-y-2"><p role="alert">{issue.message}</p>{destination && onIssue && <Button variant="outline" onClick={() => onIssue(destination)}>Исправить: {destination.label}</Button>}</div>;
      })}
      <h3 className="font-semibold">Изменения относительно опубликованной версии</h3>
      {preview.diff.length ? <div className="space-y-3">
        {preview.diff.filter(change => ["title", "description"].includes(change.path)).map(change => <div key={change.path} className="rounded border p-3"><p className="font-medium">{change.path === "title" ? "Название услуги" : "Описание"}</p><p>{String(change.before ?? "Не задано")}</p><p>{String(change.after ?? "Не задано")}</p></div>)}
        <ul className="list-disc pl-5">{[...new Set(preview.diff.filter(change => !["title", "description", "scenario_key", "offering_full_code", "schema_version", "process_binding.request_template_key"].includes(change.path)).map(change => changeLabel(change.path, definition)))].map(label => <li key={label}>{label}</li>)}</ul>
        <p className="text-sm text-slate-500">Проверьте вопросы, пункты каталога и пути на карте. Декларацию целиком можно получить через экспорт JSON / YAML.</p>
      </div> : <p>Содержимое сценария не изменилось. Будет создана новая версия с проверенной обработкой.</p>}
      {preview.readiness.can_publish && preview.confirmation_token && <div className="sticky bottom-0 z-10 grid gap-3 border-t bg-white py-3">
        <label className="flex items-start gap-2"><input type="checkbox" checked={confirmed} disabled={busy || dirty || disabled} onChange={event => setConfirmed(event.target.checked)} />Изменения проверены, подтверждаю публикацию</label>
        <Button disabled={!confirmed || busy || dirty || disabled} onClick={() => void publish()}>Опубликовать сценарий</Button>
      </div>}
    </>}
  </div>;
}
