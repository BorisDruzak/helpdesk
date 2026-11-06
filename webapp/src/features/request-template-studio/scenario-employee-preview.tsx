import { useEffect, useRef, useState } from "react";
import { Button } from "../requester/ui/form-controls";
import { ScenarioStepContent } from "../requester/scenario-step-content";
import type { DynamicFormValues } from "../requester/dynamic-form";
import { ScenarioApiError, simulateScenario, type ScenarioDetail, type ScenarioSimulation } from "./scenario-api";
import type { ScenarioAnswerRequest, ScenarioDraftDefinition } from "./scenario-contract";
import { isPolicyAttachment } from "./scenario-policy-attachments-model";
import { ScenarioProcessingResult } from "./scenario-processing-result";
import { scenarioIssueText } from "./scenario-issues";

type Props = {
  definition: ScenarioDraftDefinition;
  detail?: ScenarioDetail | null;
  ensureSaved?: () => Promise<ScenarioDetail>;
  onState?: (result: ScenarioSimulation) => void;
};

/** Employee controls backed by the authenticated, side-effect-free draft runner. */
export function ScenarioEmployeePreview({ definition, detail, ensureSaved, onState }: Props) {
  const [entry, setEntry] = useState("");
  const [result, setResult] = useState<ScenarioSimulation | null>(null);
  const [steps, setSteps] = useState<ScenarioAnswerRequest[]>([]);
  const [values, setValues] = useState<DynamicFormValues>({});
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [retry, setRetry] = useState(0);
  const heading = useRef<HTMLHeadingElement>(null);
  const sequence = useRef(0), timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const prepared = useRef<ScenarioDetail | null>(null);
  const callbacks = useRef({ ensureSaved, detail, onState }); callbacks.current = { ensureSaved, detail, onState };
  const definitionKey = JSON.stringify(definition);
  const flow = definition.blocks?.filter(block => !isPolicyAttachment(block)) ?? [];
  const hasEntry = flow.some(block => block.id === definition.entry_block_id);
  const block = result?.current_step;
  const stoppedAutomatic = !!result?.preview_stop && !!block && ["decision", "diagnostic", "sla"].includes(block.kind);
  useEffect(() => { heading.current?.focus(); }, [block?.id]);
  function cancelTimer() { if (timer.current !== null) clearTimeout(timer.current); timer.current = null; }
  function failed(failure: unknown) {
    const api = failure instanceof ScenarioApiError ? failure : null;
    setErrors(Object.fromEntries(Object.entries(api?.errors ?? {}).map(([key, value]) => [key, value === "Field is required" ? "Ответьте на вопрос." : "Проверьте значение ответа."])));
    setError(api?.errorCode === "INVALID_ANSWERS" ? "Проверьте ответы на вопросы."
      : api?.errorCode === "REVISION_CONFLICT" ? "Черновик изменился. Закройте просмотр и откройте его снова."
      : api?.issues.length ? api.issues.map(issue => scenarioIssueText(issue, definition)).join("\n")
      : "Не удалось подготовить просмотр. Проверьте сохранение черновика и повторите попытку.");
  }
  async function run(next: ScenarioAnswerRequest[], preview?: ScenarioAnswerRequest, restored?: DynamicFormValues) {
    cancelTimer();
    const active = prepared.current;
    if (!active) return;
    const current = ++sequence.current;
    setBusy(true); setError(""); setErrors({});
    try {
      const response = await simulateScenario(active.scenario.id, active.draft.revision, next, preview, undefined, entry, true);
      if (current !== sequence.current) return;
      setResult(response); callbacks.current.onState?.(response);
      if (!preview) {
        setSteps(next); setAcknowledged(false);
        setValues(Object.fromEntries((response.current_step?.fields ?? []).map(field => [field.key,
          restored && Object.hasOwn(restored, field.key) ? restored[field.key] : field.value])) as DynamicFormValues);
      } else setValues(previous => Object.fromEntries((response.current_step?.fields ?? []).map(field => [field.key,
        Object.hasOwn(previous, field.key) ? previous[field.key] : field.value])) as DynamicFormValues);
    } catch (failure) { if (current === sequence.current) failed(failure); }
    finally { if (current === sequence.current) setBusy(false); }
  }
  useEffect(() => {
    cancelTimer(); const current = ++sequence.current;
    prepared.current = null; setResult(null); setSteps([]); setValues({}); setAcknowledged(false); setError(""); setErrors({});
    if (!flow.length || !hasEntry) { setBusy(false); return; }
    setBusy(true);
    void (async () => {
      try {
        const active = callbacks.current.ensureSaved ? await callbacks.current.ensureSaved() : callbacks.current.detail;
        if (current !== sequence.current) return;
        if (!active || active.scenario.archived) throw new Error("Draft is unavailable");
        prepared.current = active;
        await run([]);
      } catch (failure) { if (current === sequence.current) { failed(failure); setBusy(false); } }
    })();
    return () => { sequence.current++; cancelTimer(); };
  }, [definitionKey, entry, detail?.scenario.id, detail?.draft.revision, retry]);
  function answer(currentResult?: ScenarioAnswerRequest["current_result"], actionKey?: string) {
    if (!block || !result || busy) return;
    const answers = Object.fromEntries(Object.entries(values).filter(([, value]) => value !== undefined)) as ScenarioAnswerRequest["answers"];
    void run([...steps, { expected_block_id: block.id, revision: result.state.revision,
      ...(block.kind === "form_page" ? { answers } : {}), ...(currentResult ? { current_result: currentResult } : {}), ...(actionKey ? { action_key: actionKey } : {}) }]);
  }
  function valueChanged(key: string, value: DynamicFormValues[string]) {
    const next = { ...values, [key]: value }; setValues(next); setErrors(previous => { const copy = { ...previous }; delete copy[key]; return copy; }); setError("");
    cancelTimer();
    if (block?.has_dynamic_fields && result) timer.current = setTimeout(() => {
      timer.current = null;
      const answers = Object.fromEntries(Object.entries(next).filter(([, item]) => item !== undefined)) as ScenarioAnswerRequest["answers"];
      void run(steps, { expected_block_id: block.id, revision: result.state.revision, answers });
    }, 300);
  }
  if (!flow.length) return <p role="status">Добавьте первый блок на карту, чтобы пройти сценарий.</p>;
  if (!hasEntry) return <p role="status">Соедините «Начало» с первым блоком сценария.</p>;
  return <section className="grid min-w-0 gap-4 rounded-panel border border-slate-200 bg-white p-5" aria-label="Блок глазами сотрудника" aria-busy={busy}>
    {(definition.entry_points?.filter(item => item.enabled !== false).length ?? 0) > 0 && <label>Пункт каталога<select className="field-base block w-full" value={entry} disabled={busy} onChange={event => setEntry(event.target.value)}><option value="">Основной вход</option>{definition.entry_points?.filter(item => item.enabled !== false).map(item => <option key={item.key} value={item.key}>{item.title}</option>)}</select></label>}
    {busy && !block && <p role="status">Подготавливаем черновик и открываем первый шаг…</p>}
    {error && <div className="grid gap-2"><p role="alert" className="whitespace-pre-line text-rose-700">{error}</p>{!block && <Button disabled={busy} variant="outline" onClick={()=>setRetry(value=>value+1)}>Повторить просмотр</Button>}</div>}
    {block && <fieldset disabled={busy} className="grid min-w-0 gap-4">
      <h2 ref={heading} tabIndex={-1} className="text-xl font-semibold text-slate-950">{stoppedAutomatic ? "Продолжение маршрута не настроено" : block.title}</h2>
      {!stoppedAutomatic && <ScenarioStepContent block={block} values={values} errors={errors} acknowledged={acknowledged} onAcknowledged={setAcknowledged} onValue={valueChanged} onRequestTicket={() => answer("request_ticket")} />}
      {result?.preview_stop ? <p role="status" className="rounded border border-amber-300 p-3">Следующий шаг ещё не настроен. Вернитесь к карте и соедините этот блок с продолжением.</p> : <>
        {block.actions !== undefined && <div className="flex flex-wrap gap-3">{block.actions.map(action => <Button key={action.key} disabled={!!block.acknowledgment_required && !acknowledged} onClick={() => answer(block.kind === "instruction" ? "acknowledged" : undefined, action.key)}>{action.label}</Button>)}{!block.actions.length && <p role="status">Заполните вопросы, чтобы увидеть доступные действия.</p>}</div>}
        {block.actions === undefined && block.kind === "resolution_check" && <div className="flex flex-wrap gap-3">{(["yes", "no", "unknown"] as const).map(value => <Button key={value} onClick={() => answer(value)}>{value === "yes" ? "Да, решено" : value === "no" ? "Нет, нужна помощь" : "Не знаю"}</Button>)}</div>}
        {block.actions === undefined && ["form_page", "instruction", "review"].includes(block.kind) && <Button disabled={!!block.acknowledgment_required && !acknowledged} onClick={() => answer(block.kind === "instruction" && acknowledged ? "acknowledged" : undefined)}>Продолжить</Button>}
      </>}
      {result?.processing && <ScenarioProcessingResult result={result} definition={definition} />}
      {result?.processing_error && <p role="status" className="rounded border border-amber-300 p-3">{result.processing_error.code === "AUTHOR_PREVIEW_INCOMPLETE" ? "Путь дошёл до завершения. Для расчёта SLA и маршрута завершите настройки обработки и остальных переходов карты." : "Путь дошёл до завершения, но шаблону обращения или политикам обработки нужны дополнительные данные. Проверьте вопросы и настройки обработки."}</p>}
      {block.kind === "finish" && <p role="status">Проверка завершена без создания обращения.</p>}
      {!!steps.length && <Button variant="outline" onClick={() => void run(steps.slice(0, -1), undefined, result?.state.answers as DynamicFormValues)}>Назад</Button>}
    </fieldset>}
  </section>;
}
