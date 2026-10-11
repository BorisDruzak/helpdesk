import { useEffect, useRef, useState } from "react";
import { Button } from "../../components/ui/button";
import { RequestFormFieldControl, type DynamicFormValues } from "../requester/dynamic-form";
import { simulateScenario, type ScenarioSimulation } from "./scenario-api";
import type { ScenarioAnswerRequest, ScenarioDraftDefinition } from "./scenario-contract";
import { diagnosticFailureLabels, type DiagnosticFailureStatus } from "./scenario-diagnostics";
import { ScenarioProcessingResult } from "./scenario-processing-result";
import { ScenarioFields } from "../requester/scenario-fields";

export function ScenarioSimulationPanel({ id, revision, dirty, disabled, definition }: { id: string; revision: number; dirty: boolean; disabled: boolean; definition?: ScenarioDraftDefinition }) {
  const [result, setResult] = useState<ScenarioSimulation | null>(null);
  const [steps, setSteps] = useState<ScenarioAnswerRequest[]>([]);
  const [values, setValues] = useState<DynamicFormValues>({});
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [diagnosticOutcomes, setDiagnosticOutcomes] = useState<Record<string, DiagnosticFailureStatus>>({});
  const diagnostics = (definition?.blocks || []).filter(item => item.kind === "diagnostic");
  const sequence = useRef(0);
  const heading = useRef<HTMLHeadingElement>(null);
  const block = result?.current_step;
  useEffect(() => {
    sequence.current++; setResult(null); setSteps([]); setValues({}); setError(""); setBusy(false); setDiagnosticOutcomes({});
    return () => { sequence.current++; };
  }, [id, revision, dirty, disabled]);
  useEffect(() => { heading.current?.focus(); }, [block?.id]);
  async function run(next: ScenarioAnswerRequest[], preview?: ScenarioAnswerRequest) {
    if (dirty || disabled) return;
    const current = ++sequence.current;
    setBusy(true); setError("");
    try {
      const outcomes = Object.fromEntries(diagnostics.map(item => [item.id, diagnosticOutcomes[item.id] || "unavailable"]));
      const response = await simulateScenario(id, revision, next, preview, outcomes);
      if (current !== sequence.current) return;
      setResult(response);
      if (!preview) { setSteps(next); setAcknowledged(false); setValues(Object.fromEntries((response.current_step?.fields || []).map(field => [field.key, field.value])) as DynamicFormValues); }
      else setValues(previous => Object.fromEntries((response.current_step?.fields || []).map(field => [field.key, previous[field.key]])));
    } catch { if (current === sequence.current) setError("Проверьте ответы и сохранённый сценарий, затем повторите проверку."); }
    finally { if (current === sequence.current) setBusy(false); }
  }
  function answer(currentResult?: ScenarioAnswerRequest["current_result"]) {
    if (!block || !result) return;
    const answers = Object.fromEntries(Object.entries(values).filter(([, value]) => value !== undefined)) as ScenarioAnswerRequest["answers"];
    void run([...steps, { expected_block_id: block.id, revision: result.state.revision,
      ...(block.kind === "form_page" ? { answers } : {}), ...(currentResult ? { current_result: currentResult } : {}) }]);
  }
  function preview() {
    if (!block?.has_dynamic_fields || !result || busy) return;
    const answers = Object.fromEntries(Object.entries(values).filter(([, value]) => value !== undefined)) as ScenarioAnswerRequest["answers"];
    void run(steps, { expected_block_id: block.id, revision: result.state.revision, answers });
  }
  return <div className="min-w-0 space-y-4" aria-busy={busy}>
    <h2 className="text-lg font-semibold">Проверка пользовательского сценария</h2>
    <p>Ответы и переходы проверяет сервер. Обращение, согласование и операции устройства не создаются.</p>
    {!!diagnostics.length && <fieldset className="grid gap-3 rounded border p-3" disabled={dirty || disabled || busy}>
      <legend>Исходы диагностики только для симуляции</legend>
      {diagnostics.map(item => <label key={item.id}>Исход симуляции: {item.title}<select className="block w-full rounded border p-2" value={diagnosticOutcomes[item.id] || "unavailable"} onChange={event => {
        sequence.current++; setResult(null); setSteps([]); setValues({}); setDiagnosticOutcomes(previous => ({ ...previous, [item.id]: event.target.value as DiagnosticFailureStatus }));
      }}>{Object.entries(diagnosticFailureLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>)}
    </fieldset>}
    <Button disabled={dirty || disabled || busy} onClick={() => void run([])}>Начать проверку</Button>
    {dirty && <p>Сначала сохраните изменения.</p>}{error && <p role="alert">{error}</p>}
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
      <ScenarioFields fields={block.fields || []} layout={block.layout} renderField={field => <><RequestFormFieldControl field={field} value={values[field.key]} onChange={value => {
        sequence.current++; setValues(previous => ({ ...previous, [field.key]: value })); setError("");
      }} />{field.allow_unknown && <label className="mt-2 flex gap-2 text-sm"><input type="checkbox" checked={values[field.key] === null} onChange={event => {
        const value = event.currentTarget.checked ? null : undefined;
        sequence.current++; setError(""); setValues(previous => ({ ...previous, [field.key]: value }));
      }} />Не знаю</label>}</>} />
      {block.content && <p className="whitespace-pre-wrap">{block.content.body}</p>}
      {block.kind === "instruction" && <label className="flex gap-2"><input type="checkbox" checked={acknowledged} onChange={event => setAcknowledged(event.target.checked)} />Инструкция выполнена</label>}
      {block.kind === "instruction" && block.can_request_ticket ? <Button variant="outline" onClick={() => answer("request_ticket")}>Нужна помощь поддержки</Button> : null}
      {block.answers && <dl className="space-y-2">{block.answers.map(item => <div key={item.key}><dt className="font-medium">{item.label}</dt><dd>{item.display_value}</dd></div>)}</dl>}
      {block.kind === "resolution_check" ? <div className="flex flex-wrap gap-2">{(["yes", "no", "unknown"] as const).map(value => <Button key={value} onClick={() => answer(value)}>{value === "yes" ? "Да, решено" : value === "no" ? "Нет, нужна помощь" : "Не знаю"}</Button>)}</div> : null}
      {["form_page", "instruction", "review"].includes(block.kind) && <Button disabled={block.acknowledgment_required && !acknowledged} onClick={() => answer(block.kind === "instruction" && acknowledged ? "acknowledged" : undefined)}>Продолжить проверку</Button>}
      {block.kind === "finish" && <p role="status">{block.message || "Решено без обращения"}</p>}
      {result?.processing && <ScenarioProcessingResult result={result} definition={definition} />}
      {!!Object.keys(result?.state.results || {}).length && <p>Результаты инструкций и проверок сохранены только в этой симуляции.</p>}
      {!!steps.length && <Button variant="outline" onClick={() => void run(steps.slice(0, -1))}>Назад в проверке</Button>}
    </fieldset>}
  </div>;
}
