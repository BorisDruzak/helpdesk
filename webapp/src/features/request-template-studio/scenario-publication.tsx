import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "../../components/ui/button";
import { RequestStudioApiError } from "./api";
import { previewScenarioPublication, publishScenario, type ScenarioPublicationPreview } from "./scenario-api";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { ScenarioPublicationSummary } from "./scenario-publication-summary";
import { scenarioIssueDestination, type ScenarioIssueDestination } from "./scenario-issue-navigation";
import { ScenarioPublicationChecks, publicationIssueGroup } from "./scenario-publication-checks";
import { ScenarioPublicationOutcomes } from "./scenario-publication-outcomes";
import { ScenarioPublicationDiff } from "./scenario-publication-diff";
import "./scenario-publication.css";

type Props = { id: string; revision: number; dirty: boolean; disabled: boolean; definition?: ScenarioDraftDefinition; offeringTitle?: string;
  onIssue?: (destination: ScenarioIssueDestination) => void; onBack?: () => void; catalogVisibility?: ReactNode; settingsPanel?: ReactNode; serviceSettingsPanel?: ReactNode; actorIdentity?: string; offeringVisibility?: string };
function validExpiry(preview: ScenarioPublicationPreview) { return !!preview.expires_at && new Date(preview.expires_at).getTime() > Date.now(); }
export function ScenarioPublication({ id, revision, dirty, disabled, definition, offeringTitle, onIssue, onBack, catalogVisibility, settingsPanel, serviceSettingsPanel, actorIdentity, offeringVisibility }: Props) {
  const cache = useQueryClient();
  const [preview, setPreview] = useState<ScenarioPublicationPreview | null>(null);
  const contextKey = JSON.stringify([id, revision, actorIdentity, offeringVisibility]);
  const [previewContext, setPreviewContext] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [published, setPublished] = useState<ScenarioDraftDefinition | null>(null);
  const [checkEpoch, setCheckEpoch] = useState(0);
  const [highlighted, setHighlighted] = useState(false);
  const steps = useRef<Array<HTMLElement | null>>([]);
  const sequence = useRef(0);
  const inFlight = useRef(false);
  useEffect(() => {
    sequence.current++;
    inFlight.current = false;
    setPreview(null); setPreviewContext(""); setConfirmed(false); setError(""); setMessage(""); setPublished(null); setBusy(false);
    setHighlighted(false);
    if (dirty || disabled) return;
    const timer = setTimeout(() => { void prepare(); }, 250);
    return () => { clearTimeout(timer); sequence.current++; };
  }, [id, revision, dirty, disabled, offeringVisibility, actorIdentity, checkEpoch]);
  useEffect(() => {
    if (busy || !preview) return;
    const expiresAt = preview.confirmation_token ? preview.expires_at : null;
    const remaining = expiresAt ? new Date(expiresAt).getTime() - Date.now() : 30_000;
    // Confirmation tokens are short lived; bound the timer to the DOM maximum.
    const timeout = setTimeout(() => {
      if (expiresAt && new Date(expiresAt).getTime() > Date.now()) return;
      setPreview(null); setConfirmed(false); setCheckEpoch(value => value + 1);
    }, Math.max(0, Math.min(remaining, 2147483647)));
    return () => clearTimeout(timeout);
  }, [preview, busy]);
  useEffect(() => {
    function refresh() {
      if (dirty || disabled || published || inFlight.current || document.visibilityState === "hidden") return;
      setCheckEpoch(value => value + 1);
    }
    window.addEventListener("focus", refresh);
    window.addEventListener("online", refresh);
    document.addEventListener("visibilitychange", refresh);
    return () => { window.removeEventListener("focus", refresh); window.removeEventListener("online", refresh); document.removeEventListener("visibilitychange", refresh); };
  }, [dirty, disabled, published]);
  async function prepare() {
    if (dirty || disabled || inFlight.current) return;
    const current = ++sequence.current;
    inFlight.current = true;
    setBusy(true); setError(""); setPreview(null); setConfirmed(false); setMessage(""); setPublished(null);
    try {
      const value = await previewScenarioPublication(id, revision);
      if (current !== sequence.current) return;
      if (value.revision !== revision) { setError("Сохранённая версия изменилась. Дождитесь повторной автоматической проверки."); return; }
      if (value.confirmation_token && !validExpiry(value)) { setError("Срок подтверждения истёк. Дождитесь повторной автоматической проверки."); return; }
      setPreviewContext(contextKey); setPreview(value);
    } catch { if (current === sequence.current) setError("Не удалось проверить публикацию. Повторите проверку."); }
    finally { if (current === sequence.current) { inFlight.current = false; setBusy(false); } }
  }
  async function publish() {
    if (previewContext !== contextKey || !preview?.readiness.can_publish || !preview.confirmation_token || !confirmed || dirty || disabled || busy || inFlight.current || preview.revision !== revision) return;
    if (!validExpiry(preview)) { setPreview(null); setConfirmed(false); setError("Срок подтверждения истёк. Дождитесь повторной автоматической проверки."); return; }
    const current = ++sequence.current;
    inFlight.current = true;
    setBusy(true); setError("");
    try {
      const result = await publishScenario(id, revision, preview.confirmation_token);
      // A write that finishes after navigation must still refresh other views.
      void cache.invalidateQueries({ queryKey: ["scenario-catalog"] });
      void cache.invalidateQueries({ queryKey: ["scenario-detail", id] });
      if (current !== sequence.current) return;
      setPreview(null); setConfirmed(false); setMessage(`Опубликована версия ${result.version.version}.`);
      setPublished(result.version.definition ?? result.draft?.definition ?? definition ?? null);
    } catch (cause) {
      if (current !== sequence.current) return;
      setPreview(null); setConfirmed(false);
      setError(cause instanceof RequestStudioApiError && cause.status === 409
        ? "Черновик, обработка или срок подтверждения изменились. Дождитесь повторной автоматической проверки."
        : "Сценарий не опубликован. Дождитесь повторной автоматической проверки.");
    } finally { if (current === sequence.current) { inFlight.current = false; setBusy(false); } }
  }
  const currentPreview = !dirty && !disabled && previewContext === contextKey && preview?.revision === revision && (!preview.confirmation_token || validExpiry(preview)) ? preview : null;
  const missingMetadata = definition ? !definition.title?.trim() ? "title" : !definition.service_code ? "service_code" : null : null;
  const titles = ["Данные услуги", "Карта сценария", "Обработка и сроки", "Проверенные исходы", "Изменения и публикация"];
  const states = titles.map((_, index) => {
    if (index === 0 && missingMetadata) return { tone: "problem", label: missingMetadata === "title" ? "Укажите название" : "Выберите раздел" };
    if (dirty) return { tone: "pending", label: "Ожидает сохранения" };
    if (disabled) return { tone: "pending", label: "Только просмотр" };
    if (error) return { tone: "pending", label: "Не проверено" };
    if (!currentPreview) return { tone: "pending", label: published ? "Опубликовано" : "Проверяем…" };
    const issues = currentPreview.readiness.issues.filter(issue => publicationIssueGroup(issue) === index);
    if (index < 3 && issues.length) return { tone: "problem", label: `Замечаний: ${issues.length}` };
    if (index === 4 && !currentPreview.readiness.can_publish) return { tone: "problem", label: "Нужно исправить пункты" };
    if (!currentPreview.readiness.variants_checked && !currentPreview.readiness.can_publish) return { tone: "pending", label: "Ожидает проверки" };
    return { tone: "ready", label: index === 4 ? "Можно подтвердить" : "Готово" };
  });
  function goToStep(index: number) { steps.current[index]?.scrollIntoView?.({ block: "start", behavior: "smooth" }); steps.current[index]?.focus({ preventScroll: true }); }
  function showProblems() { setHighlighted(true); const index = states.findIndex(state => state.tone === "problem"); goToStep(index < 0 ? 4 : index); if (missingMetadata && definition) onIssue?.(scenarioIssueDestination({code:"required",path:missingMetadata},definition)); }
  function step(index: number, children: ReactNode) {
    const state = states[index];
    return <section className="scenario-publication-step" aria-label={`${index + 1}. ${titles[index]}`} tabIndex={-1} ref={element => { steps.current[index] = element; }} data-step={index + 1} data-state={state.tone} data-highlighted={highlighted && state.tone === "problem"}>
      <header><h2>{index + 1}. {titles[index]}</h2><span className="scenario-readiness-badge" data-state={state.tone}>{state.label}</span></header>
      {currentPreview && index < 3 && <ScenarioPublicationChecks preview={currentPreview} definition={definition} onIssue={onIssue} groupIndex={index} />}
      {children}
    </section>;
  }
  return <section className="scenario-publication" aria-label="Публикация сценария" aria-busy={busy}>
    <header className="scenario-publication-header"><div><h1>Публикация услуги</h1><p>{offeringTitle || definition?.title || "Настройка услуги"} · ревизия {revision}</p></div><div className="scenario-publication-header-actions">
      {onBack && <Button variant="outline" disabled={busy} onClick={onBack}>Вернуться к карте</Button>}
      <Button disabled={disabled || busy || (!currentPreview && !missingMetadata)} onClick={showProblems}>Показать, что исправить</Button>
    </div></header>
    <p className="text-slate-600">Пройдите пункты по порядку. Изменения сохраняются автоматически, готовность проверяется после сохранения.</p>
    <ol className="scenario-publication-progress" aria-label="Порядок настройки услуги">{titles.map((title, index) => <li key={title}><button type="button" onClick={() => goToStep(index)} data-state={states[index].tone}><span>{index + 1}. {title}</span><small>{states[index].label}</small></button></li>)}</ol>
    {dirty && <p role="status">Изменения сохраняются автоматически. Проверка обновится после сохранения.</p>}
    {!dirty && !disabled && !currentPreview && !error && !published && <p role="status">Проверяем услугу: карту, доступность, обработку и сроки…</p>}
    {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4"><p>{error}</p><Button variant="outline" disabled={dirty || disabled || busy} onClick={() => void prepare()}>Повторить проверку</Button></div>}
    {message && <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">{message}</p>}
    {step(0, <>{serviceSettingsPanel ?? catalogVisibility ?? <p>Название: {offeringTitle || definition?.title || "Не указано"}</p>}</>)}
    {step(1, <><p>Формы, вопросы, переходы и завершения должны составлять полный путь сотрудника.</p>{onBack && <Button variant="outline" onClick={onBack}>Открыть карту сценария</Button>}</>)}
    {step(2, settingsPanel ?? <p>Проверяем действующие правила обработки и сроки каждого пути.</p>)}
    {step(3, <>{currentPreview ? <><p>Проверено исходов: {currentPreview.readiness.variants_checked}.</p><ScenarioPublicationOutcomes outcomes={currentPreview.outcomes} definition={definition} onIssue={onIssue} /></> : <p>Исходы появятся после автоматической проверки сохранённой услуги.</p>}
      {published ? <ScenarioPublicationSummary definition={published} offeringTitle={offeringTitle} /> : definition && <details><summary className="cursor-pointer font-medium">Что увидит сотрудник</summary><div className="mt-3"><ScenarioPublicationSummary definition={definition} offeringTitle={offeringTitle} /></div></details>}
    </>)}
    {step(4, <>{currentPreview && <ScenarioPublicationDiff diff={currentPreview.diff} definition={definition} />}
      {published && <a className="inline-block text-brand-700 underline" target="_blank" rel="noopener noreferrer" href={`/app/requester/new?${new URLSearchParams({ offering: published.offering_full_code })}`}>Открыть сценарий сотрудника</a>}
      {currentPreview?.readiness.can_publish && currentPreview.confirmation_token ? <div className="scenario-publication-confirmation">
        <label><input type="checkbox" checked={confirmed} disabled={busy} onChange={event => setConfirmed(event.target.checked)} />Изменения проверены, подтверждаю публикацию</label>
        <Button disabled={!confirmed || busy} onClick={() => void publish()}>Опубликовать сценарий</Button>
      </div> : !published && <p>Публикация станет доступна, когда обязательные пункты будут выполнены и проверка завершится.</p>}
    </>)}
  </section>;
}
