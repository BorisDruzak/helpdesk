import { useEffect, useRef, useState } from "react";
import { Button } from "../../components/ui/button";
import { RequestFormFieldControl, type DynamicFormValues } from "../requester/dynamic-form";
import { simulateScenario, type ScenarioSimulation } from "./scenario-api";
import type { ScenarioAnswerRequest } from "./scenario-contract";

export function ScenarioSimulationPanel({ id, revision, dirty, disabled }: { id: string; revision: number; dirty: boolean; disabled: boolean }) {
  const [result, setResult] = useState<ScenarioSimulation | null>(null);
  const [steps, setSteps] = useState<ScenarioAnswerRequest[]>([]);
  const [values, setValues] = useState<DynamicFormValues>({});
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const sequence = useRef(0);
  const heading = useRef<HTMLHeadingElement>(null);
  const block = result?.current_step;
  useEffect(() => {
    sequence.current++; setResult(null); setSteps([]); setValues({}); setError(""); setBusy(false);
    return () => { sequence.current++; };
  }, [id, revision, dirty, disabled]);
  useEffect(() => { heading.current?.focus(); }, [block?.id]);
  async function run(next: ScenarioAnswerRequest[], preview?: ScenarioAnswerRequest) {
    if (dirty || disabled) return;
    const current = ++sequence.current;
    setBusy(true); setError("");
    try {
      const response = await simulateScenario(id, revision, next, preview);
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
    <Button disabled={dirty || disabled || busy} onClick={() => void run([])}>Начать проверку</Button>
    {dirty && <p>Сначала сохраните изменения.</p>}{error && <p role="alert">{error}</p>}
    {block && <fieldset className="min-w-0 space-y-4" disabled={dirty || disabled || busy} onBlur={preview}>
      <h3 tabIndex={-1} ref={heading} className="font-semibold">{block.title}</h3>
      {(block.fields || []).map(field => <RequestFormFieldControl key={field.key} field={field} value={values[field.key]} onChange={value => {
        sequence.current++; setValues(previous => ({ ...previous, [field.key]: value })); setError("");
      }} />)}
      {block.content && <p className="whitespace-pre-wrap">{block.content.body}</p>}
      {block.kind === "instruction" && <label className="flex gap-2"><input type="checkbox" checked={acknowledged} onChange={event => setAcknowledged(event.target.checked)} />Инструкция выполнена</label>}
      {block.answers && <dl className="space-y-2">{block.answers.map(item => <div key={item.key}><dt className="font-medium">{item.label}</dt><dd>{item.display_value}</dd></div>)}</dl>}
      {block.kind === "resolution_check" ? <div className="flex flex-wrap gap-2">{(["yes", "no", "unknown"] as const).map(value => <Button key={value} onClick={() => answer(value)}>{value === "yes" ? "Да, решено" : value === "no" ? "Нет, нужна помощь" : "Не знаю"}</Button>)}</div> : null}
      {["form_page", "instruction", "review"].includes(block.kind) && <Button disabled={block.acknowledgment_required && !acknowledged} onClick={() => answer(block.kind === "instruction" && acknowledged ? "acknowledged" : undefined)}>Продолжить проверку</Button>}
      {block.kind === "finish" && <p role="status">{block.message || "Решено без обращения"}</p>}
      {result?.processing && <div role="status" className="space-y-2 rounded border p-3">
        <p>Результат серверной проверки обработки</p><p>Приоритет: {result.processing.priority.priority_class}</p>
        <p>Очередь: {result.processing.routing.queue_code || result.processing.routing.queue_id || "Не определена"}</p>
        <p>Срок выполнения: {result.processing.sla.resolution_min ? `${result.processing.sla.resolution_min} мин.` : "Не определён"}</p>
        <p>{result.processing.approval.required ? "Потребуется согласование" : "Согласование не требуется"}</p>
      </div>}
      {!!Object.keys(result?.state.results || {}).length && <p>Результаты инструкций и проверок сохранены только в этой симуляции.</p>}
      {!!steps.length && <Button variant="outline" onClick={() => void run(steps.slice(0, -1))}>Назад в проверке</Button>}
    </fieldset>}
  </div>;
}
