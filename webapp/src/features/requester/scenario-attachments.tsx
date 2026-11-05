import { useEffect, useRef, useState, type ReactNode } from "react";
import { ChatAttachment } from "../../components/chat-attachment";
import { ChatFileDropFeedback, useChatFileDrop } from "../../components/chat-file-draft";
import type { ScenarioAttachment } from "../request-template-studio/scenario-contract";

export function ScenarioAttachments({ attachments = [] }: { attachments?: ScenarioAttachment[] }) {
  if (!attachments.length) return null;
  return <ul className="flex min-w-0 flex-wrap gap-3" aria-label="Прикреплённые материалы">{attachments.map(item => <li key={item.asset_id} className="min-w-0 max-w-full"><ChatAttachment attachment={item} /></li>)}</ul>;
}

/** A picker, drop and paste surface for one server-scoped attachment collection. */
export function ScenarioAttachmentEditor({ attachments = [], scope, disabled, onUpload, onRemove, onBusy, children, label = "Прикрепить скриншоты или файлы" }: {
  attachments?: ScenarioAttachment[]; scope: string; disabled?: boolean; children?: ReactNode; label?: string;
  onUpload?: (file: File, signal: AbortSignal) => Promise<void>;
  onRemove?: (id: string, signal: AbortSignal) => Promise<void>;
  onBusy?: (busy: boolean) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const active = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const callbacks = useRef({ onUpload, onRemove, onBusy });
  callbacks.current = { onUpload, onRemove, onBusy };
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    generation.current++; setBusy(false); setError("");
    return () => { generation.current++; active.current?.abort(); active.current = null; callbacks.current.onBusy?.(false); };
  }, [scope]);
  async function mutate(files?: File[], id?: string) {
    if (disabled || active.current) return;
    if (files && attachments.length + files.length > 10) { setError("Можно прикрепить до 10 файлов. Выберите меньше файлов."); return; }
    if (files?.some(file => file.size > 200 * 1024 * 1024)) { setError("Размер каждого файла не должен превышать 200 МБ."); return; }
    const controller = new AbortController();
    active.current = controller;
    const started = generation.current;
    const current = () => started === generation.current && !controller.signal.aborted;
    setBusy(true); setError(""); callbacks.current.onBusy?.(true);
    try {
      if (id) await callbacks.current.onRemove?.(id, controller.signal);
      else for (const file of files || []) {
        if (!current()) return;
        await callbacks.current.onUpload?.(file, controller.signal);
      }
    } catch {
      if (current()) setError(id ? "Не удалось убрать файл. Повторите действие." : "Не удалось прикрепить файл. Уже загруженные файлы сохранены. Проверьте файл и повторите.");
    } finally {
      if (active.current === controller) active.current = null;
      if (current()) { setBusy(false); callbacks.current.onBusy?.(false); }
    }
  }
  const drop = useChatFileDrop(!!disabled || busy, onUpload ? files => void mutate(files) : undefined);
  return <div {...drop.handlers} className={`relative grid min-w-0 gap-2 rounded-lg ${drop.dragging ? "ring-2 ring-sky-500" : ""}`} aria-busy={busy}>
    {children}
    {attachments.length ? <ul className="flex min-w-0 flex-wrap gap-3" aria-label="Прикреплённые материалы">{attachments.map(item => <li key={item.asset_id} className="grid min-w-0 max-w-full gap-1">
      <ChatAttachment attachment={item} />
      {onRemove && <button type="button" className="justify-self-start text-sm font-medium text-rose-700 underline" aria-label={`Убрать вложение ${item.name}`} disabled={disabled || busy} onClick={() => void mutate(undefined, item.asset_id)}>Убрать</button>}
    </li>)}</ul> : null}
    {onUpload ? <div className="flex flex-wrap items-center gap-2">
      <input ref={input} type="file" multiple className="sr-only" tabIndex={-1} aria-label={label} disabled={disabled || busy} onChange={event => { const files = Array.from(event.currentTarget.files || []); event.currentTarget.value = ""; if (files.length) void mutate(files); }} />
      <button type="button" disabled={disabled || busy || attachments.length >= 10} className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium" onClick={() => input.current?.click()}>{label}</button>
      <span className="text-xs text-slate-500">До 10 файлов, до 200 МБ каждый. Перетащите сюда или вставьте скриншот (Ctrl+V).</span>
    </div> : null}
    {busy && <p role="status" className="text-sm">Сохраняем вложения…</p>}
    {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
    <ChatFileDropFeedback message={drop.feedback} />
  </div>;
}
