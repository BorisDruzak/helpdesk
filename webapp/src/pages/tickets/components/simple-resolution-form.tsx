import type { SupportTicketDetailPayload } from "../../../features/queues/api";
import { useEffect, useRef, useState } from "react";
export type SimpleResolutionDraft = { resolutionCode: string; requesterResolutionSummary: string; resolutionSummary: string; reason: string };
export type SimpleResolutionFormProps = {
  requirements: NonNullable<SupportTicketDetailPayload["actions"]["closure_requirements"]>; initial?: Partial<SimpleResolutionDraft>;
  pending: boolean; error?: string | null; onSubmit: (draft: SimpleResolutionDraft) => void; onCancel: () => void; onAdvanced: () => void;
};
export function SimpleResolutionForm(props: SimpleResolutionFormProps) {
  const [draft, setDraft] = useState<SimpleResolutionDraft>(() => ({ resolutionCode: "", requesterResolutionSummary: "", resolutionSummary: "", reason: "Решение обращения", ...props.initial }));
  const formRef = useRef<HTMLFormElement>(null);
  useEffect(() => { const previous = document.activeElement as HTMLElement | null; formRef.current?.querySelector<HTMLElement>("textarea")?.focus(); return () => previous?.focus(); }, []);
  const required = (key: string) => props.requirements.some((item) => item.key === key);
  const needsCode = required("resolution_code") || required("allowed_resolution_code");
  const blockers = props.requirements.filter((item) => !item.met && !["resolution_code", "allowed_resolution_code", "public_summary", "internal_summary"].includes(item.key));
  const valid = (!needsCode || Boolean(draft.resolutionCode.trim())) && (!required("public_summary") || Boolean(draft.requesterResolutionSummary.trim())) && (!required("internal_summary") || Boolean(draft.resolutionSummary.trim()));
  const change = (key: keyof SimpleResolutionDraft, value: string) => setDraft((current) => ({ ...current, [key]: value }));
  return <div className="simple-modal" role="presentation"><form ref={formRef} className="simple-panel simple-form" role="dialog" aria-modal="true" aria-labelledby="simple-resolution-title" onSubmit={(event) => { event.preventDefault(); if (valid && !props.pending) props.onSubmit(draft); }} onKeyDown={(event) => {
    if (event.key === "Escape" && !props.pending) props.onCancel();
    if (event.key === "Tab") {
      const nodes = Array.from(formRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled),input,textarea,select') ?? []);
      const first = nodes[0], last = nodes.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
  }}>
    <div className="simple-queue__heading"><div><h2 id="simple-resolution-title">Решить обращение</h2><p className="simple-muted">Сотрудник получит итог решения. Подтверждение и закрытие выполняются по действующей политике.</p></div><button aria-label="Закрыть форму решения" className="simple-button" type="button" disabled={props.pending} onClick={props.onCancel}>×</button></div>
    {props.error ? <p className="simple-notice simple-risk" role="alert">{props.error} <button className="simple-link" type="button" onClick={props.onAdvanced}>Открыть требования решения</button></p> : null}
    <label>Итог для сотрудника<textarea required={required("public_summary")} value={draft.requesterResolutionSummary} onChange={(event) => change("requesterResolutionSummary", event.target.value)} placeholder="Что исправлено и как проверить результат" rows={3} /></label>
    {needsCode ? <label>Код решения<input required value={draft.resolutionCode} onChange={(event) => change("resolutionCode", event.target.value)} /><span className="simple-muted">{props.requirements.find((item) => ["resolution_code", "allowed_resolution_code"].includes(item.key))?.detail}</span></label> : null}
    {required("internal_summary") ? <label>Внутренний итог<textarea required value={draft.resolutionSummary} onChange={(event) => change("resolutionSummary", event.target.value)} rows={2} /></label> : <details><summary>Внутренняя информация (необязательно)</summary><label>Внутренний итог<textarea value={draft.resolutionSummary} onChange={(event) => change("resolutionSummary", event.target.value)} rows={2} /></label></details>}
    {blockers.length ? <div className="simple-notice"><p>Для решения также требуются:</p>{blockers.map((item) => <p key={item.key}><button className="simple-link" type="button" title={item.detail} onClick={props.onAdvanced}>{item.label}</button></p>)}</div> : null}
    <div className="simple-composer__actions"><button className="simple-button" type="button" disabled={props.pending} onClick={props.onCancel}>Отмена</button><button className="simple-button simple-button--primary" type="submit" disabled={!valid || props.pending}>{props.pending ? "Сохраняем…" : "Решить обращение"}</button></div>
  </form></div>;
}
