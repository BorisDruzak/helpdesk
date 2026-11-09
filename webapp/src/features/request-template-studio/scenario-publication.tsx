import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "../../components/ui/button";
import { RequestStudioApiError } from "./api";
import { previewScenarioPublication, publishScenario, type ScenarioPublicationPreview } from "./scenario-api";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { ScenarioPublicationSummary } from "./scenario-publication-summary";
import type { ScenarioIssueDestination } from "./scenario-issue-navigation";
import { ScenarioPublicationChecks } from "./scenario-publication-checks";
import { ScenarioPublicationOutcomes } from "./scenario-publication-outcomes";
import { ScenarioPublicationDiff } from "./scenario-publication-diff";
import "./scenario-publication.css";

type Props = { id: string; revision: number; dirty: boolean; disabled: boolean; definition?: ScenarioDraftDefinition; offeringTitle?: string;
  onIssue?: (destination: ScenarioIssueDestination) => void; onBack?: () => void; catalogVisibility?: ReactNode; offeringVisibility?: string };
function validExpiry(preview: ScenarioPublicationPreview) { return !!preview.expires_at && new Date(preview.expires_at).getTime() > Date.now(); }
export function ScenarioPublication({ id, revision, dirty, disabled, definition, offeringTitle, onIssue, onBack, catalogVisibility, offeringVisibility }: Props) {
  const cache = useQueryClient();
  const [preview, setPreview] = useState<ScenarioPublicationPreview | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [published, setPublished] = useState<ScenarioDraftDefinition | null>(null);
  const sequence = useRef(0);
  const inFlight = useRef(false);
  useEffect(() => {
    sequence.current++;
    inFlight.current = false;
    setPreview(null); setConfirmed(false); setError(""); setMessage(""); setPublished(null); setBusy(false);
    return () => { sequence.current++; };
  }, [id, revision, dirty, disabled, offeringVisibility]);
  useEffect(() => {
    if (!preview?.confirmation_token || !preview.expires_at) return;
    const remaining = new Date(preview.expires_at).getTime() - Date.now();
    // Confirmation tokens are short lived; bound the timer to the DOM maximum.
    const timeout = setTimeout(() => {
      if (new Date(preview.expires_at!).getTime() > Date.now()) return;
      setPreview(null); setConfirmed(false); setError("Срок подтверждения истёк. Подготовьте публикацию заново.");
    }, Math.max(0, Math.min(remaining, 2147483647)));
    return () => clearTimeout(timeout);
  }, [preview]);
  async function prepare() {
    if (dirty || disabled || inFlight.current) return;
    const current = ++sequence.current;
    inFlight.current = true;
    setBusy(true); setError(""); setPreview(null); setConfirmed(false); setMessage(""); setPublished(null);
    try {
      const value = await previewScenarioPublication(id, revision);
      if (current !== sequence.current) return;
      if (value.revision !== revision) { setError("Сохранённая версия изменилась. Подготовьте публикацию заново."); return; }
      if (value.confirmation_token && !validExpiry(value)) { setError("Срок подтверждения истёк. Подготовьте публикацию заново."); return; }
      setPreview(value);
    } catch { if (current === sequence.current) setError("Не удалось проверить публикацию. Повторите проверку."); }
    finally { if (current === sequence.current) { inFlight.current = false; setBusy(false); } }
  }
  async function publish() {
    if (!preview?.readiness.can_publish || !preview.confirmation_token || !confirmed || dirty || disabled || busy || inFlight.current || preview.revision !== revision) return;
    if (!validExpiry(preview)) { setPreview(null); setConfirmed(false); setError("Срок подтверждения истёк. Подготовьте публикацию заново."); return; }
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
        ? "Черновик, обработка или срок подтверждения изменились. Подготовьте публикацию заново."
        : "Сценарий не опубликован. Подготовьте публикацию заново.");
    } finally { if (current === sequence.current) { inFlight.current = false; setBusy(false); } }
  }
  return <section className="scenario-publication" aria-label="Публикация сценария" aria-busy={busy}>
    <header className="scenario-publication-header"><div><h1>Публикация сценария</h1><p>{offeringTitle || definition?.title || "Проверка сохранённого сценария"} · ревизия {revision}</p></div><div className="scenario-publication-header-actions">
      {onBack && <Button variant="outline" disabled={busy} onClick={onBack}>Вернуться к карте</Button>}
      <Button disabled={dirty || disabled || busy} onClick={() => void prepare()}>{busy ? "Проверка…" : "Подготовить публикацию"}</Button>
    </div></header>
    <p className="text-slate-600">Проверьте замечания, исходы и изменения, затем подтвердите публикацию сохранённой версии.</p>
    {dirty && <p role="status">Сначала сохраните изменения.</p>}
    {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4">{error}</p>}{message && <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">{message}</p>}
    {catalogVisibility && <div className="scenario-publication-section">{catalogVisibility}</div>}
    {published && <a className="inline-block text-brand-700 underline" target="_blank" rel="noopener noreferrer" href={`/app/requester/new?${new URLSearchParams({ offering: published.offering_full_code })}`}>Открыть сценарий сотрудника</a>}
    {!preview && !published && <section className="scenario-publication-section" aria-label="Готовность к проверке"><h2>Готовность к публикации</h2><p>{busy ? "Сервер проверяет допустимые ветви, очереди и действующие правила обработки." : "Нажмите «Подготовить публикацию», чтобы проверить все допустимые исходы на сервере."}</p><p className="text-sm text-slate-500">Проверка не создаёт обращения и не публикует черновик.</p></section>}
    {preview && <>
      <ScenarioPublicationChecks preview={preview} definition={definition} onIssue={onIssue} />
      <ScenarioPublicationOutcomes outcomes={preview.outcomes} definition={definition} onIssue={onIssue} />
      <ScenarioPublicationDiff diff={preview.diff} definition={definition} />
    </>}
    {(published || definition) && <div className="scenario-publication-section">{published ? <ScenarioPublicationSummary definition={published} offeringTitle={offeringTitle} /> : <details><summary className="cursor-pointer font-medium">Что увидит сотрудник</summary><div className="mt-3"><ScenarioPublicationSummary definition={definition!} offeringTitle={offeringTitle} /></div></details>}</div>}
    {preview?.readiness.can_publish && preview.confirmation_token && <div className="scenario-publication-confirmation">
      <label><input type="checkbox" checked={confirmed} disabled={busy || dirty || disabled} onChange={event => setConfirmed(event.target.checked)} />Изменения проверены, подтверждаю публикацию</label>
      <Button disabled={!confirmed || busy || dirty || disabled} onClick={() => void publish()}>Опубликовать сценарий</Button>
    </div>}
  </section>;
}
