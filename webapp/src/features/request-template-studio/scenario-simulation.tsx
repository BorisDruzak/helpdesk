import { useEffect, useRef, useState } from "react";
import { Button } from "../../components/ui/button";
import { type DynamicFormValues } from "../requester/dynamic-form";
import { simulateScenario, ScenarioApiError, type ScenarioSimulation } from "./scenario-api";
import { scenarioIssueDestination, type ScenarioIssueDestination } from "./scenario-issue-navigation";
import type { ScenarioAnswerRequest, ScenarioDraftDefinition } from "./scenario-contract";
import { diagnosticFailureLabels, type DiagnosticFailureStatus } from "./scenario-diagnostics";
import { ScenarioProcessingResult } from "./scenario-processing-result";
import { ScenarioStepContent } from "../requester/scenario-step-content";
import { ScenarioSimulationComparison, ScenarioSimulationTrace } from "./scenario-simulation-trace";
import { scenarioIssueText, type ScenarioApiIssue } from "./scenario-issues";

export function ScenarioSimulationPanel({ id, revision, dirty, disabled, definition, onIssue, onState }: { id: string; revision: number; dirty: boolean; disabled: boolean; definition?: ScenarioDraftDefinition; onIssue?: (target: ScenarioIssueDestination) => void; onState?: (current: string, path: string[]) => void }) {
  const [entryPointKey, setEntryPointKey] = useState("");
  const [result, setResult] = useState<ScenarioSimulation | null>(null);
  const [comparison, setComparison] = useState<ScenarioSimulation | null>(null);
  const [steps, setSteps] = useState<ScenarioAnswerRequest[]>([]);
  const [values, setValues] = useState<DynamicFormValues>({});
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [issues, setIssues] = useState<ScenarioApiIssue[]>([]);
  const [diagnosticOutcomes, setDiagnosticOutcomes] = useState<Record<string, DiagnosticFailureStatus>>({});
  const diagnostics = (definition?.blocks || []).filter(item => item.kind === "diagnostic");
  const sequence = useRef(0);
  const previewTimer = useRef<number | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const block = result?.current_step;
  useEffect(() => {
    sequence.current++; setResult(null); setSteps([]); setValues({}); setError(""); setIssues([]); setBusy(false); setDiagnosticOutcomes({});
    return () => { sequence.current++; if (previewTimer.current !== null) window.clearTimeout(previewTimer.current); };
  }, [id, revision, dirty, disabled, entryPointKey]);
  useEffect(() => { heading.current?.focus(); }, [block?.id]);
  useEffect(() => { setComparison(null); }, [id, revision, dirty]);
  async function run(next: ScenarioAnswerRequest[], preview?: ScenarioAnswerRequest) {
    if (dirty || disabled) return;
    if (previewTimer.current !== null) window.clearTimeout(previewTimer.current);
    previewTimer.current = null;
    const current = ++sequence.current;
    setBusy(true); setError(""); setIssues([]);
    try {
      const outcomes = Object.fromEntries(diagnostics.map(item => [item.id, diagnosticOutcomes[item.id] || "unavailable"]));
      const response = await simulateScenario(id, revision, next, preview, outcomes, entryPointKey);
      if (current !== sequence.current) return;
      setResult(response);
      onState?.(response.state.current_block_id, response.state.history ?? []);
      if (!preview) { setSteps(next); setAcknowledged(false); setValues(Object.fromEntries((response.current_step?.fields || []).map(field => [field.key, field.value])) as DynamicFormValues); }
      else setValues(previous => {
        const nextValues = Object.fromEntries((response.current_step?.fields || []).map(field => [field.key, previous[field.key]]));
        return Object.keys(previous).length === Object.keys(nextValues).length && Object.keys(nextValues).every(key => Object.is(previous[key], nextValues[key])) ? previous : nextValues;
      });
    } catch (failure) { if (current === sequence.current) {
      setIssues(failure instanceof ScenarioApiError ? failure.issues : []);
      setError(failure instanceof ScenarioApiError && failure.errorCode === "SCENARIO_INVALID" ? "Сценарий пока не готов к проверке. Исправьте указанные шаги и сохраните черновик." : failure instanceof ScenarioApiError && failure.errorCode === "REVISION_CONFLICT" ? "Сохранённая версия изменилась. Загрузите текущую версию сценария и повторите проверку." : "Проверьте ответы и сохранённый сценарий, затем повторите проверку.");
    } }
    finally { if (current === sequence.current) setBusy(false); }
  }
  function answer(currentResult?: ScenarioAnswerRequest["current_result"], actionKey?: string) {
    if (!block || !result) return;
    const answers = Object.fromEntries(Object.entries(values).filter(([, value]) => value !== undefined)) as ScenarioAnswerRequest["answers"];
    void run([...steps, { expected_block_id: block.id, revision: result.state.revision,
      ...(block.kind === "form_page" ? { answers } : {}), ...(currentResult ? { current_result: currentResult } : {}), ...(actionKey ? { action_key: actionKey } : {}) }]);
  }
  function preview(previewValues = values) {
    if (!block?.has_dynamic_fields || !result || busy) return;
    const answers = Object.fromEntries(Object.entries(previewValues).filter(([, value]) => value !== undefined)) as ScenarioAnswerRequest["answers"];
    void run(steps, { expected_block_id: block.id, revision: result.state.revision, answers });
  }
  return <div className="min-w-0 space-y-4" aria-busy={busy}>
    <h2 className="text-lg font-semibold">Проверка пользовательского сценария</h2>
    <p>Ответы и переходы проверяет сервер. Обращение, согласование и операции устройства не создаются.</p>
    <label className="block">Точка входа для проверки<select className="field-base block w-full" value={entryPointKey} disabled={busy} onChange={event => setEntryPointKey(event.target.value)}><option value="">Совместимый вход карты</option>{definition?.entry_points?.map(entry => <option key={entry.key} value={entry.key}>{entry.title}</option>)}</select></label>
    <details><summary>Сообщённые и проверенные сведения</summary><p>Сообщённый симптом: {definition?.entry_points?.find(entry => entry.key === entryPointKey)?.reported_symptom || "не задан"}</p><p>Ответы сотрудника: {Object.entries(result?.state.answers ?? {}).map(([key, value]) => `${definition?.blocks?.flatMap(block => block.kind === "form_page" ? block.fields : []).find(field => field.key === key)?.label ?? "Ответ"}: ${String(value ?? "Не знаю")}`).join("; ") || "пока нет"}</p><p>Проверенные факты диагностики: пока нет. Реальная диагностика недоступна.</p></details>
    {!!diagnostics.length && <fieldset className="grid gap-3 rounded border p-3" disabled={dirty || disabled || busy}>
      <legend>Исходы диагностики только для симуляции</legend>
      {diagnostics.map(item => <label key={item.id}>Исход симуляции: {item.title}<select className="block w-full rounded border p-2" value={diagnosticOutcomes[item.id] || "unavailable"} onChange={event => {
        sequence.current++; setResult(null); setSteps([]); setValues({}); setDiagnosticOutcomes(previous => ({ ...previous, [item.id]: event.target.value as DiagnosticFailureStatus }));
      }}>{Object.entries(diagnosticFailureLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>)}
    </fieldset>}
    <Button className="max-w-full whitespace-normal" disabled={dirty || disabled || busy} onClick={() => void run([])}>Начать проверку</Button>
    {result?.processing && <Button className="h-auto min-h-11 w-full min-w-0 whitespace-normal py-2" variant="outline" disabled={dirty || disabled || busy} onClick={() => { setComparison(structuredClone(result)); void run([]); }}>Сохранить результат и сравнить другой набор ответов</Button>}
    {comparison && result?.processing && <><ScenarioSimulationComparison first={comparison} second={result} definition={definition} /><Button variant="ghost" onClick={() => setComparison(null)}>Убрать сравнение</Button></>}
    {dirty && <p>Сначала сохраните изменения.</p>}{error && <p role="alert">{error}</p>}
    {result?.simulation_scope?.limited_scope && <p role="status" className="rounded border border-amber-300 p-3">Проверяется только допустимая часть выбранного входа. В черновике есть ошибки; публикация всей карты заблокирована. Исключённые шаги: {result.simulation_scope.excluded_block_ids.map(id => definition?.blocks?.find(block => block.id === id)?.title ?? "Шаг").join(", ")}.</p>}
    {issues.map((issue, index) => {
      const target = definition ? scenarioIssueDestination(issue, definition) : null;
      return <div key={index} className="rounded border border-amber-300 p-3"><p>{scenarioIssueText(issue, definition)}</p>{target && onIssue && <Button variant="outline" onClick={() => onIssue(target)}>Исправить шаг</Button>}</div>;
    })}
    {Object.entries(result?.state.results || {}).filter(([, value]) => value !== null && typeof value === "object" && "simulated" in value && value.simulated === true && "operation_created" in value && value.operation_created === false).map(([key, value]) => {
      const status = (value as { status?: string }).status;
      const label = status && Object.hasOwn(diagnosticFailureLabels, status) ? diagnosticFailureLabels[status as DiagnosticFailureStatus] : "Недоступно";
      return <div className="rounded border p-3" key={key} role="status"><p>Симуляция — реальная операция не выполнялась.</p><p>{diagnostics.find(item => item.id === key)?.title || "Проверка"}: {label}</p></div>;
    })}
    {block && <fieldset className="min-w-0 space-y-4" disabled={dirty || disabled || busy} onBlur={event => {
      // Heading/button focus also bubbles here; preview only edited controls.
      // Actions send these answers themselves; preview must not swallow their click.
      const next = event.relatedTarget;
      if (next instanceof Element && next.closest("button") && event.currentTarget.contains(next)) return;
      if (event.target.matches("input, textarea, select")) preview();
    }}>
      <h3 tabIndex={-1} ref={heading} className="font-semibold">{block.title}</h3>
      <ScenarioStepContent block={block} values={values} acknowledged={acknowledged} onAcknowledged={setAcknowledged} onValue={(key, value) => {
        sequence.current++;
        const next = { ...values, [key]: value };
        setValues(next); setError("");
        if (previewTimer.current !== null) window.clearTimeout(previewTimer.current);
        if (block.has_dynamic_fields) previewTimer.current = window.setTimeout(() => { previewTimer.current = null; preview(next); }, 300);
      }} onRequestTicket={() => answer("request_ticket")} />
      {block.actions !== undefined && <div className="flex flex-wrap gap-2">{block.actions.map(action => <Button key={action.key} disabled={block.acknowledgment_required && !acknowledged} onClick={() => answer(block.kind === "instruction" ? "acknowledged" : undefined, action.key)}>{action.label}</Button>)}{!block.actions.length && <p role="status">Заполните вопросы, чтобы увидеть доступные действия.</p>}</div>}
      {block.actions === undefined && block.kind === "resolution_check" ? <div className="flex flex-wrap gap-2">{(["yes", "no", "unknown"] as const).map(value => <Button key={value} onClick={() => answer(value)}>{value === "yes" ? "Да, решено" : value === "no" ? "Нет, нужна помощь" : "Не знаю"}</Button>)}</div> : null}
      {block.actions === undefined && ["form_page", "instruction", "review"].includes(block.kind) && <Button disabled={block.acknowledgment_required && !acknowledged} onClick={() => answer(block.kind === "instruction" && acknowledged ? "acknowledged" : undefined)}>Продолжить проверку</Button>}
      {block.kind === "finish" && <p role="status">{block.message || "Решено без обращения"}</p>}
      {result?.processing && <ScenarioProcessingResult result={result} definition={definition} />}
      {result?.map_processing && !result.processing && <ScenarioSimulationTrace result={result} definition={definition} />}
      {result?.processing_error && <div role="alert" className="space-y-2 rounded border border-amber-300 p-3"><p>Маршрут дошёл до создания обращения, но действующий шаблон или политики обработки требуют дополнительных данных. Проверьте обязательные вопросы типа обращения и настройки обработки.</p>{onIssue&&<Button variant="outline" onClick={()=>onIssue({step:1,label:block.title,blockId:block.id})}>Настроить данные обращения</Button>}</div>}
      {!!Object.keys(result?.state.results || {}).length && <p>Результаты инструкций и проверок сохранены только в этой симуляции.</p>}
      {!!steps.length && <Button variant="outline" onClick={() => void run(steps.slice(0, -1))}>Назад в проверке</Button>}
    </fieldset>}
  </div>;
}
