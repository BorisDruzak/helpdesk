import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCatalogEvent } from "./catalog-funnel";
import { type DynamicFormValues } from "./dynamic-form";
import { ScenarioStepContent, type ScenarioStepDisplay } from "./scenario-step-content";
import { Button } from "./ui/form-controls";
import type { ScenarioAttachment } from "../request-template-studio/scenario-contract";

type Step = {
  id: string;
  revision: number;
  state: string;
  linked_ticket_id?: string | null;
  entry_point_key?: string | null;
  version_id?: string;
  back_targets: { id: string; title: string }[];
  block: ScenarioStepDisplay;
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
  const recordCatalogEvent=useCatalogEvent();
  const navigate = useNavigate();
  const commandBusy = useRef(false);
  const [step, setStep] = useState<Step | null>(null);
  const [values, setValues] = useState<DynamicFormValues>({});
  const [error, setError] = useState<SessionError | null>(null);
  const [busy, setBusy] = useState(false);
  const attachmentFields = useRef(new Set<string>());
  const [attachmentsBusy, setAttachmentsBusy] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [reload, setReload] = useState(0);
  const [ticketPreview, setTicketPreview] = useState<TicketPreview | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const requestSequence = useRef(0);
  const lifecycle = useRef(0);
  const commandControllers = useRef(new Set<AbortController>());
  const previewTimer = useRef<number | null>(null);
  const previewController = useRef<AbortController | null>(null);
  const storageKey = owner ? `pc_client.scenario.session:${owner}:${offering}${entryPointKey ? `:entry:${encodeURIComponent(entryPointKey)}` : ""}` : null;
  const stepRef = useRef(step); stepRef.current = step;

  function attachmentBusy(key: string, pending: boolean) {
    if (pending) { attachmentFields.current.add(key); cancelScheduledPreview(); requestSequence.current++; }
    else attachmentFields.current.delete(key);
    setAttachmentsBusy(attachmentFields.current.size > 0);
  }
  async function attachment(key: string, signal: AbortSignal, file?: File, assetId?: string) {
    if (!step || commandBusy.current) return;
    const generation = lifecycle.current;
    const current = () => generation === lifecycle.current && !signal.aborted && stepRef.current?.id === step.id && stepRef.current?.revision === step.revision && stepRef.current?.block.id === step.block.id;
    const body = new FormData();
    if (file) { body.append("file", file); body.append("field_key", key); body.append("expected_block_id", step.block.id); body.append("revision", String(step.revision)); body.append("answers", JSON.stringify(values)); }
    const response = await fetch(`${base}/${encodeURIComponent(step.id)}/attachments${assetId ? `/${encodeURIComponent(assetId)}` : ""}`, {
      method: assetId ? "DELETE" : "POST", credentials: "same-origin", signal,
      ...(assetId ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_block_id: step.block.id, revision: step.revision }) } : { body }),
    });
    const payload = await response.json();
    if (!current()) return;
    if (!response.ok || payload.status !== "success") {
      const cause = new SessionError(payload.error_code || "ATTACHMENT_OPERATION_FAILED");
      if (["REVISION_CONFLICT", "SESSION_EXPIRED", "SESSION_REVOKED", "SESSION_NOT_FOUND"].includes(cause.code)) setError(cause);
      throw cause;
    }
    setStep(previous => previous && current() ? { ...previous, block: { ...previous.block, fields: previous.block.fields?.map(field => field.key !== key ? field : { ...field, answer_attachments: assetId ? (field.answer_attachments || []).filter(item => item.asset_id !== assetId) : [...(field.answer_attachments || []), payload.data as ScenarioAttachment] }) } } : previous);
  }

  function cancelScheduledPreview() {
    if (previewTimer.current !== null) window.clearTimeout(previewTimer.current);
    previewTimer.current = null;
    previewController.current?.abort();
    previewController.current = null;
  }

  function remember(data: Step) {
    if (storageKey) {
      try {
        const completed = (data.state === "ticket_created" && data.linked_ticket_id) || data.state === "completed_self_service";
        if (completed) {
          // Forget only an acknowledged terminal session; uncertain commands keep their resume handle.
          if (sessionStorage.getItem(storageKey) === data.id) sessionStorage.removeItem(storageKey);
        } else sessionStorage.setItem(storageKey, data.id);
      } catch { /* Server start can still resume active sessions. */ }
    }
  }
  function accept(data: Step) {
    setStep(data);
    setValues(Object.fromEntries((data.block.fields || []).map(field => [field.key, field.value])));
    setAcknowledged(false);
    setTicketPreview(null);
    setError(null);
    remember(data);
    if (data.state === "ticket_created" && data.linked_ticket_id) {
      void navigate(`/app/requester/tickets/${encodeURIComponent(data.linked_ticket_id)}`, { replace: true });
    }
  }

  useEffect(() => {
    lifecycle.current++;
    attachmentFields.current.clear(); setAttachmentsBusy(false);
    commandBusy.current = true;
    const controller = new AbortController();
    setStep(null); setError(null); setBusy(true); setTicketPreview(null);
    let saved: string | null = null;
    try { saved = storageKey ? sessionStorage.getItem(storageKey) : null; } catch { /* Optional opaque ID. */ }
    const path = saved ? `${base}/${encodeURIComponent(saved)}` : base;
    request(path, saved ? undefined : { offering_full_code: offering, ...(entryPointKey ? { entry_point_key: entryPointKey } : {}) }, controller.signal)
      .then(data => { if (!controller.signal.aborted) accept(data); })
      .catch(cause => { if (!controller.signal.aborted) setError(cause); })
      .finally(() => { if (!controller.signal.aborted) { commandBusy.current = false; setBusy(false); } });
    return () => {
      lifecycle.current++; controller.abort(); requestSequence.current++;
      cancelScheduledPreview();
      for (const pending of commandControllers.current) pending.abort();
      commandControllers.current.clear();
    };
  }, [offering, storageKey, reload, deviceId, entryPointKey]); // Context changes invalidate pending commands and previews.

  useEffect(() => { heading.current?.focus(); }, [step?.block.id]);

  async function command(kind: string, body: unknown) {
    if (!step || commandBusy.current || attachmentFields.current.size) return;
    if (kind === "submit" && (step.state !== "active" || !ticketPreview?.ok || ticketPreview.blockers.length || error)) return;
    cancelScheduledPreview();
    commandBusy.current = true;
    const generation = lifecycle.current;
    const controller = new AbortController();
    commandControllers.current.add(controller);
    const current = () => generation === lifecycle.current && !controller.signal.aborted;
    requestSequence.current++; setBusy(true); setError(null);
    if (kind === "ticket-preview") setTicketPreview(null);
    try {
      if (kind === "ticket-preview") {
        const data = await request<TicketPreview | Step>(`${base}/${step.id}/${kind}`, { ...(body as object), ...deviceContext }, controller.signal);
        if (current()) {
          // Another window may have completed this session before preview arrived.
          if ("state" in data) accept(data);
          else setTicketPreview(data);
        }
        return;
      }
      if (kind === "answer" && step.block.has_dynamic_fields) {
        const projected = await request(`${base}/${step.id}/step-preview`, body, controller.signal);
        if (!current()) return;
        setStep(current => current ? { ...current, block: projected.block } : current);
      }
      const data = await request(`${base}/${step.id}/${kind}`, kind === "submit" ? { ...(body as object), ...deviceContext } : body, controller.signal);
      if (current()) { if(kind==='submit'&&data.state==='ticket_created')recordCatalogEvent('submitted'); accept(data); }
    }
    catch (cause) { if (current()) setError(cause as SessionError); }
    finally { commandControllers.current.delete(controller); if (current()) { commandBusy.current = false; setBusy(false); } }
  }

  useEffect(() => {
    if (step?.state === "active" && step.block.kind === "submit_ticket" && !busy && !ticketPreview && !error) {
      void command("ticket-preview", { revision: step.revision });
    }
  }, [step, busy, ticketPreview, error]);

  async function preview(answers = values) {
    if (!step?.block.has_dynamic_fields || busy || commandBusy.current || attachmentFields.current.size) return;
    cancelScheduledPreview();
    const sequence = ++requestSequence.current;
    const generation = lifecycle.current;
    const controller = new AbortController();
    previewController.current = controller;
    commandControllers.current.add(controller);
    const current = () => sequence === requestSequence.current && generation === lifecycle.current && !controller.signal.aborted;
    try {
      const data = await request(`${base}/${step.id}/step-preview`, {
        expected_block_id: step.block.id, revision: step.revision, answers,
      }, controller.signal);
      if (current()) {
        setStep(current => current ? { ...current, block: data.block } : current);
        setValues(current => {
          const projected = Object.fromEntries((data.block.fields || []).map(field => [field.key, current[field.key]]));
          return Object.keys(current).length === Object.keys(projected).length && Object.keys(projected).every(key => Object.hasOwn(current, key) && Object.is(current[key], projected[key])) ? current : projected;
        });
        setError(null);
      }
    } catch (cause) { if (current()) setError(cause as SessionError); }
    finally {
      commandControllers.current.delete(controller);
      if (previewController.current === controller) previewController.current = null;
    }
  }

  // Native paste inserts its text after the clipboard event. Keep editors enabled
  // during uploads, then project any edits once the attachment batch has finished.
  useEffect(() => { if (!attachmentsBusy && attachmentFields.current.size === 0) void preview(); }, [attachmentsBusy]);

  function changeValue(key: string, value: DynamicFormValues[string]) {
    const next = { ...values, [key]: value };
    requestSequence.current++;
    cancelScheduledPreview();
    setValues(next);
    setError(null);
    if (step?.block.has_dynamic_fields && !busy && !attachmentFields.current.size) {
      const type = step.block.fields?.find(field => field.key === key)?.type;
      const delay = type && ["text", "textarea", "number"].includes(type) ? 150 : 0;
      previewTimer.current = window.setTimeout(() => { previewTimer.current = null; void preview(next); }, delay);
    }
  }

  const answer = (result?: string) => command(step?.block.kind === "form_page" ? "answer" : "advance", {
    expected_block_id: step?.block.id, revision: step?.revision,
    ...(step?.block.kind === "form_page" ? { answers: values } : {}),
    ...(result ? { current_result: result } : {}),
  });
  const expired = ["SESSION_EXPIRED", "SESSION_REVOKED", "SESSION_NOT_FOUND"].includes(error?.code || "");
  const deviceContext = deviceId === undefined ? {} : deviceId ? { device_id: deviceId } : { device_scope: "none" };

  return <section className="grid gap-4 rounded-panel border border-slate-200 bg-white p-5" aria-busy={busy || attachmentsBusy}>
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
        <ScenarioStepContent block={step.block} values={values} errors={error?.fields} acknowledged={acknowledged} onAcknowledged={setAcknowledged} onValue={changeValue} onRequestTicket={()=>void answer("request_ticket")} attachmentScope={`${offering}:${owner}:${deviceId}:${entryPointKey}:${reload}:${step.id}:${step.revision}`} attachmentsDisabled={busy || attachmentsBusy} onAttachmentBusy={attachmentBusy} onUpload={(key, file, signal) => attachment(key, signal, file)} onRemove={(key, id, signal) => attachment(key, signal, undefined, id)} />
      </fieldset>
      <fieldset disabled={busy || attachmentsBusy} className="grid min-w-0 gap-3 border-t border-slate-200 bg-white py-3" aria-label="Действия шага">
        {step.block.kind === "resolution_check" ? <div className="flex flex-wrap gap-2">{[["yes", "Да, решено"], ["no", "Нет, нужна помощь"], ["unknown", "Не знаю"]].map(([value, label]) => <Button key={value} type="button" onClick={() => void answer(value)}>{label}</Button>)}</div> : null}
        {["form_page", "instruction", "review"].includes(step.block.kind) ? <Button type="button" disabled={step.block.acknowledgment_required && !acknowledged} onClick={() => void answer(step.block.kind === "instruction" && acknowledged ? "acknowledged" : undefined)}>Продолжить</Button> : null}
        {step.block.kind === "finish" ? <Button type="button" onClick={() => void command("finish", { revision: step.revision })}>Завершить</Button> : null}
        {step.state === "ticket_created" && step.linked_ticket_id ? <p role="status">Открываем обращение...</p> : step.block.kind === "submit_ticket" ? <div className="grid gap-3">
          {busy ? <p role="status">{ticketPreview ? "Создаём обращение..." : "Проверяем обработку обращения..."}</p> : null}
          {ticketPreview ? <>
            {ticketPreview.expected_first_response ? <p>Первый ответ: {ticketPreview.expected_first_response}</p> : null}
            {ticketPreview.expected_resolution ? <p>{ticketPreview.expected_resolution}</p> : null}
            {ticketPreview.approval ? <p>{ticketPreview.approval.text}</p> : null}
            {ticketPreview.warnings.map((text, index) => <p key={`warning-${index}`}>{text}</p>)}
            {ticketPreview.blockers.map((text, index) => <p role="alert" key={`blocker-${index}`}>{text}</p>)}
            {ticketPreview.ok && !ticketPreview.blockers.length && !error ? <Button type="button" onClick={() => void command("submit", { revision: step.revision, confirm: true })}>Создать обращение</Button> : null}
          </> : null}
          {ticketPreview && (!ticketPreview.ok || ticketPreview.blockers.length > 0) && !error ? <Button type="button" variant="outline" onClick={() => void command("ticket-preview", { revision: step.revision })}>Повторить обработку</Button> : null}
        </div> : null}
        {step.back_targets.length ? <div className="flex flex-wrap gap-2">{step.back_targets.map(target => <Button key={target.id} type="button" variant="outline" onClick={() => void command("back", { revision: step.revision, target_block_id: target.id })}>Вернуться: {target.title}</Button>)}</div> : null}
      </fieldset>
    </> : null}
  </section>;
}
