import { useEffect, useRef, useState } from "react";
import { RequestFormFieldControl, type DynamicFormValues } from "./dynamic-form";
import { ScenarioFields, type ScenarioProjectedField } from "./scenario-fields";
import { Button } from "./ui/form-controls";

type Step = {
  id: string;
  revision: number;
  state: string;
  linked_ticket_id?: string | null;
  entry_point_key?: string | null;
  version_id?: string;
  back_targets: { id: string; title: string }[];
  block: {
    id: string; kind: string; title: string;
    fields?: (ScenarioProjectedField & { value?: DynamicFormValues[string]; allow_unknown?: boolean })[];
    layout?: "single" | "group" | "section";
    has_dynamic_fields?: boolean;
    content?: { body: string; format: string };
    acknowledgment_required?: boolean;
    can_request_ticket?: boolean;
    message?: string;
    answers?: { key: string; label: string; type: string; value: unknown; display_value: string }[];
  };
};

type TicketPreview = { ok: boolean; expected_first_response?: string; expected_resolution?: string; approval?: { text: string }; blockers: string[]; warnings: string[] };

class SessionError extends Error {
  constructor(public code: string, public fields: Record<string, string> = {}) { super(code); }
}

const base = "/api/web/requester/request-scenarios/sessions";
async function request<T = Step>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST", credentials: "same-origin", cache: "no-store", signal,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok || result.status !== "success") throw new SessionError(result.error_code || "SESSION_OPERATION_FAILED", result.errors);
  return result.data;
}

export function ScenarioSession({ offering, owner = "", deviceId, entryPointKey }: { offering: string; owner?: string; deviceId?: string; entryPointKey?: string }) {
  const [step, setStep] = useState<Step | null>(null);
  const [values, setValues] = useState<DynamicFormValues>({});
  const [error, setError] = useState<SessionError | null>(null);
  const [busy, setBusy] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [reload, setReload] = useState(0);
  const [ticketPreview, setTicketPreview] = useState<TicketPreview | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const requestSequence = useRef(0);
  const lifecycle = useRef(0);
  const commandControllers = useRef(new Set<AbortController>());
  const storageKey = owner ? `pc_client.scenario.session:${owner}:${offering}${entryPointKey ? `:entry:${encodeURIComponent(entryPointKey)}` : ""}` : null;

  function remember(data: Step) {
    if (storageKey) {
      try { sessionStorage.setItem(storageKey, data.id); } catch { /* Server start can still resume. */ }
    }
  }
  function accept(data: Step) {
    setStep(data);
    setValues(Object.fromEntries((data.block.fields || []).map(field => [field.key, field.value])));
    setAcknowledged(false);
    setTicketPreview(null);
    setError(null);
    remember(data);
  }

  useEffect(() => {
    lifecycle.current++;
    const controller = new AbortController();
    setStep(null); setError(null); setBusy(true); setTicketPreview(null);
    let saved: string | null = null;
    try { saved = storageKey ? sessionStorage.getItem(storageKey) : null; } catch { /* Optional opaque ID. */ }
    const path = saved ? `${base}/${encodeURIComponent(saved)}` : base;
    request(path, saved ? undefined : { offering_full_code: offering, ...(entryPointKey ? { entry_point_key: entryPointKey } : {}) }, controller.signal)
      .then(data => { if (!controller.signal.aborted) accept(data); })
      .catch(cause => { if (!controller.signal.aborted) setError(cause); })
      .finally(() => { if (!controller.signal.aborted) setBusy(false); });
    return () => {
      lifecycle.current++; controller.abort(); requestSequence.current++;
      for (const pending of commandControllers.current) pending.abort();
      commandControllers.current.clear();
    };
  }, [offering, storageKey, reload, deviceId, entryPointKey]); // Context changes invalidate pending commands and previews.

  useEffect(() => { heading.current?.focus(); }, [step?.block.id]);

  async function command(kind: string, body: unknown) {
    if (!step || busy) return;
    const generation = lifecycle.current;
    const controller = new AbortController();
    commandControllers.current.add(controller);
    const current = () => generation === lifecycle.current && !controller.signal.aborted;
    requestSequence.current++; setBusy(true); setError(null);
    try {
      if (kind === "ticket-preview") {
        const data = await request<TicketPreview>(`${base}/${step.id}/${kind}`, { ...(body as object), ...deviceContext }, controller.signal);
        if (current()) setTicketPreview(data);
        return;
      }
      if (kind === "answer" && step.block.has_dynamic_fields) {
        const projected = await request(`${base}/${step.id}/step-preview`, body, controller.signal);
        if (!current()) return;
        setStep(current => current ? { ...current, block: projected.block } : current);
      }
      const data = await request(`${base}/${step.id}/${kind}`, kind === "submit" ? { ...(body as object), ...deviceContext } : body, controller.signal);
      if (current()) accept(data);
    }
    catch (cause) { if (current()) setError(cause as SessionError); }
    finally { commandControllers.current.delete(controller); if (current()) setBusy(false); }
  }

  async function preview() {
    if (!step?.block.has_dynamic_fields || busy) return;
    const sequence = ++requestSequence.current;
    try {
      const data = await request(`${base}/${step.id}/step-preview`, {
        expected_block_id: step.block.id, revision: step.revision, answers: values,
      });
      if (sequence === requestSequence.current) {
        setStep(current => current ? { ...current, block: data.block } : current);
        setValues(current => Object.fromEntries((data.block.fields || []).map(field => [field.key, current[field.key]])));
        setError(null);
      }
    } catch (cause) { if (sequence === requestSequence.current) setError(cause as SessionError); }
  }

  const answer = (result?: string) => command(step?.block.kind === "form_page" ? "answer" : "advance", {
    expected_block_id: step?.block.id, revision: step?.revision,
    ...(step?.block.kind === "form_page" ? { answers: values } : {}),
    ...(result ? { current_result: result } : {}),
  });
  const expired = ["SESSION_EXPIRED", "SESSION_REVOKED", "SESSION_NOT_FOUND"].includes(error?.code || "");
  const deviceContext = deviceId === undefined ? {} : deviceId ? { device_id: deviceId } : { device_scope: "none" };

  return <section className="grid gap-4 rounded-panel border border-slate-200 bg-white p-5" aria-busy={busy}>
    {error ? <div role="alert" className="text-sm text-rose-700">
      {error.code === "REVISION_CONFLICT" ? "Сценарий изменился в другом окне. Загрузите сохранённый шаг." : expired ? "Срок действия сценария завершён или доступ отозван." : "Не удалось выполнить действие. Проверьте ответы и повторите."}
      <Button type="button" variant="outline" onClick={() => {
        if (expired && storageKey) { try { sessionStorage.removeItem(storageKey); } catch { /* Optional storage. */ } }
        setReload(value => value + 1);
      }}>{expired ? "Начать заново" : "Загрузить сохранённый шаг"}</Button>
    </div> : null}
    {!step && busy ? <p>Загружаем сценарий...</p> : null}
    {step ? <>
      <h2 ref={heading} tabIndex={-1} className="text-xl font-semibold text-slate-950">{step.block.title}</h2>
      <fieldset disabled={busy} className="grid min-w-0 gap-4" onBlur={() => void preview()}>
        <ScenarioFields fields={step.block.fields || []} layout={step.block.layout} renderField={field => <>
          <RequestFormFieldControl field={field} value={values[field.key]} error={error?.fields[field.key]} onChange={value => {
            requestSequence.current++; setValues(current => ({ ...current, [field.key]: value })); setError(null);
          }} />
          {field.allow_unknown ? <label className="mt-2 flex gap-2 text-sm"><input type="checkbox" checked={values[field.key] === null} onChange={event => {
            const value = event.currentTarget.checked ? null : undefined;
            requestSequence.current++; setError(null);
            setValues(current => ({ ...current, [field.key]: value }));
          }} />Не знаю</label> : null}
        </>} />
        {step.block.content ? <p className="whitespace-pre-wrap break-words">{step.block.content.body}</p> : null}
        {step.block.kind === "instruction" ? <label className="flex gap-2"><input type="checkbox" checked={acknowledged} onChange={event => setAcknowledged(event.target.checked)} />Инструкция выполнена</label> : null}
        {step.block.kind === "instruction" && step.block.can_request_ticket ? <Button type="button" variant="outline" onClick={() => void answer("request_ticket")}>Нужна помощь поддержки</Button> : null}
        {step.block.answers ? <dl className="grid gap-3">{step.block.answers.map(item => <div key={item.key}><dt className="font-medium">{item.label}</dt><dd className="break-words text-sm">{item.display_value}</dd></div>)}</dl> : null}
        {step.block.message ? <p>{step.block.message}</p> : null}
      </fieldset>
      <fieldset disabled={busy} className="sticky bottom-0 z-10 grid min-w-0 gap-3 border-t border-slate-200 bg-white py-3" aria-label="Действия шага">
        {step.block.kind === "resolution_check" ? <div className="flex flex-wrap gap-2">{[["yes", "Да, решено"], ["no", "Нет, нужна помощь"], ["unknown", "Не знаю"]].map(([value, label]) => <Button key={value} type="button" onClick={() => void answer(value)}>{label}</Button>)}</div> : null}
        {["form_page", "instruction", "review"].includes(step.block.kind) ? <Button type="button" disabled={step.block.acknowledgment_required && !acknowledged} onClick={() => void answer(step.block.kind === "instruction" && acknowledged ? "acknowledged" : undefined)}>Продолжить</Button> : null}
        {step.block.kind === "finish" ? <Button type="button" onClick={() => void command("finish", { revision: step.revision })}>Завершить</Button> : null}
        {step.state === "ticket_created" && step.linked_ticket_id ? <div className="grid gap-2"><p>Обращение создано.</p><a className="font-medium text-brand-700 underline" href={`/app/requester/tickets/${encodeURIComponent(step.linked_ticket_id)}`}>Открыть обращение</a></div> : step.block.kind === "submit_ticket" ? <div className="grid gap-3">
          {ticketPreview ? <>
            {ticketPreview.expected_first_response ? <p>Первый ответ: {ticketPreview.expected_first_response}</p> : null}
            {ticketPreview.expected_resolution ? <p>{ticketPreview.expected_resolution}</p> : null}
            {ticketPreview.approval ? <p>{ticketPreview.approval.text}</p> : null}
            {ticketPreview.warnings.map((text, index) => <p key={`warning-${index}`}>{text}</p>)}
            {ticketPreview.blockers.map((text, index) => <p role="alert" key={`blocker-${index}`}>{text}</p>)}
            {ticketPreview.ok && !ticketPreview.blockers.length ? <Button type="button" onClick={() => void command("submit", { revision: step.revision, confirm: true })}>Создать обращение</Button> : null}
          </> : null}
          <Button type="button" variant={ticketPreview ? "outline" : undefined} onClick={() => void command("ticket-preview", { revision: step.revision })}>Проверить обработку</Button>
        </div> : null}
        {step.back_targets.length ? <div className="flex flex-wrap gap-2">{step.back_targets.map(target => <Button key={target.id} type="button" variant="outline" onClick={() => void command("back", { revision: step.revision, target_block_id: target.id })}>Вернуться: {target.title}</Button>)}</div> : null}
      </fieldset>
    </> : null}
  </section>;
}
