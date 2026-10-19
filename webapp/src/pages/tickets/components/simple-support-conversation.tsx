import { Fragment, useEffect, useRef, useState, type ChangeEvent, type RefObject } from "react";
import { ArrowDown, FileText, LoaderCircle, LockKeyhole, Paperclip, Send } from "lucide-react";
import type { SupportTicketAttachmentUpload } from "../../../features/queues/api";
import type { SupportWorkspaceTimelineItem } from "../../../features/queues/support-workspace-model";

export type SimpleSupportConversationProps = {
  items: SupportWorkspaceTimelineItem[]; mode: "public" | "internal"; text: string;
  canReply: boolean; canNote: boolean; pending: boolean; loading?: boolean; error?: boolean; uploadError?: string | null;
  replyBlockedReason?: string | null; initialDescription?: string | null;
  onModeChange: (mode: "public" | "internal") => void; onTextChange: (text: string) => void; onSend: () => void;
  attachments: SupportTicketAttachmentUpload[]; onRemoveAttachment: (id: string) => void;
  inputRef?: RefObject<HTMLInputElement | null>; onUpload?: (event: ChangeEvent<HTMLInputElement>) => void;
};
type ConversationTab = "dialog" | "internal" | "history";
const normalize = (text: string) => text.replace(/\s+/g, " ").trim();
function dateOf(item: SupportWorkspaceTimelineItem) {
  const value = item.occurredAt ? new Date(item.occurredAt) : null;
  return value && !Number.isNaN(value.getTime()) ? value : null;
}
function actorOf(item: SupportWorkspaceTimelineItem, outgoing: boolean) {
  return !item.actor || ["admin", "support", "user", "requester", "system"].includes(item.actor)
    ? outgoing ? "Поддержка" : item.kind === "message" ? "Сотрудник" : "Система"
    : item.actor;
}
export function SimpleSupportConversation(props: SimpleSupportConversationProps) {
  const [tab, setTab] = useState<ConversationTab>(() => props.mode === "internal" ? "internal" : "dialog");
  const [hasNew, setHasNew] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const pinnedRef = useRef(true);
  useEffect(() => { setTab(props.mode === "internal" ? "internal" : "dialog"); pinnedRef.current = true; }, [props.mode]);
  const items = props.items.filter((item) => tab === "dialog" ? item.kind === "message" : tab === "internal" ? item.kind === "internal" : item.kind === "history" || item.kind === "diagnostics");
  const endKey = `${tab}:${items.at(-1)?.id ?? "empty"}`;
  const previousEndRef = useRef(endKey);
  useEffect(() => {
    const list = listRef.current;
    if (list && pinnedRef.current) { list.scrollTop = list.scrollHeight; setHasNew(false); }
    else if (previousEndRef.current !== endKey) setHasNew(true);
    previousEndRef.current = endKey;
  }, [endKey]);
  function selectTab(value: ConversationTab) {
    setTab(value); pinnedRef.current = true; setHasNew(false);
    if (value !== "history") props.onModeChange(value === "internal" ? "internal" : "public");
  }
  function latest() { if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight; pinnedRef.current = true; setHasNew(false); }
  const isInternal = tab === "internal";
  const allowed = isInternal ? props.canNote : props.canReply;
  const canSend = allowed && !props.pending && Boolean(props.text.trim() || props.attachments.length);
  return <section className="simple-conversation" aria-label="Переписка обращения">
    <div className="simple-tabs simple-conversation__tabs" role="tablist" aria-label="Лента обращения">
      {([["dialog", "Диалог"], ["internal", "Внутренние заметки"], ["history", "История"]] as const).map(([id, label]) => <button type="button" role="tab" aria-selected={tab === id} disabled={props.pending} key={id} onClick={() => selectTab(id)}>{label}</button>)}
    </div>
    {props.loading ? <p className="simple-feed-status" role="status"><LoaderCircle size={14} aria-hidden /> Обновляем ленту…</p> : null}
    {props.error ? <p className="simple-feed-status simple-risk" role="alert">Не удалось обновить ленту. Показаны последние загруженные сообщения.</p> : null}
    <div className="simple-conversation__feed">
      <div ref={listRef} className="simple-conversation__messages" role="tabpanel" aria-label={tab === "dialog" ? "Диалог" : isInternal ? "Внутренние заметки" : "История"}
        onScroll={(event) => { const list = event.currentTarget; pinnedRef.current = list.scrollHeight - list.scrollTop - list.clientHeight < 64; if (pinnedRef.current) setHasNew(false); }}>
        {!items.length && !props.loading ? <p className="simple-empty">{tab === "dialog" ? "Пока нет публичных сообщений." : isInternal ? "Внутренних заметок пока нет." : "Событий пока нет."}</p> : null}
        {items.map((item, index) => {
          const outgoing = item.fromRole === "support" || item.fromRole === "admin";
          const actor = actorOf(item, outgoing);
          const date = dateOf(item); const previousDate = index ? dateOf(items[index - 1]) : null;
          const showDay = date && date.toDateString() !== previousDate?.toDateString();
          const initial = tab === "dialog" && index === 0 && !outgoing && props.initialDescription && normalize(item.body) === normalize(props.initialDescription);
          return <Fragment key={item.id}>
            {showDay ? <div className="simple-message-day"><span>{date.toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" })}</span></div> : null}
            <article className="simple-message-row" data-outgoing={outgoing} data-kind={item.kind}>
              <span className="simple-message-avatar" aria-hidden>{actor.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toLocaleUpperCase()}</span>
              <div className="simple-message-group">
                <div className="simple-message__meta"><strong>{actor}</strong><time dateTime={item.occurredAt ?? undefined} title={item.timestampLabel}>{date ? date.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" }) : item.timestampLabel}</time></div>
                <div className="simple-message" data-kind={item.kind}>
                  {tab === "history" ? <h4>{item.title}</h4> : null}
                  {initial ? <details className="simple-original-message"><summary>Первичное обращение · Показать текст</summary><p>{item.body}</p></details> : <p>{item.body}</p>}
                  {item.operation ? <p className="simple-muted">{item.operation.statusLabel}{item.operation.summary ? ` · ${item.operation.summary}` : ""}</p> : null}
                  {item.attachments.length ? <ul className="simple-message__attachments">{item.attachments.map((attachment, attachmentIndex) => {
                    const url = String(attachment.url ?? attachment.download_url ?? "");
                    const safe = url.startsWith("/") && !url.startsWith("//") && !url.includes("\\");
                    const name = String(attachment.name ?? attachment.filename ?? attachment.file_name ?? "Вложение");
                    return <li key={String(attachment.artifact_id ?? attachmentIndex)}>{safe ? <a href={url} target="_blank" rel="noreferrer"><FileText size={18} aria-hidden />{name}</a> : <span>{name}</span>}</li>;
                  })}</ul> : null}
                </div>
              </div>
            </article>
          </Fragment>;
        })}
      </div>
      {hasNew ? <button className="simple-latest simple-button" type="button" onClick={latest}><ArrowDown size={16} aria-hidden />К новым сообщениям</button> : null}
    </div>
    {tab !== "history" ? <form className="simple-composer" data-internal={isInternal} data-blocked={!allowed} onSubmit={(event) => { event.preventDefault(); if (canSend) { pinnedRef.current = true; props.onSend(); } }}>
      <div className="simple-composer__heading"><label><span className="sr-only">Режим ответа</span><select aria-label="Режим ответа" disabled={props.pending} value={isInternal ? "internal" : "public"} onChange={(event) => selectTab(event.target.value === "internal" ? "internal" : "dialog")}><option value="public">Ответ сотруднику</option><option value="internal">Внутренняя заметка</option></select></label><span className="simple-muted">{isInternal ? <><LockKeyhole size={13} aria-hidden /> Видит только поддержка</> : "Сообщение увидит сотрудник"}</span></div>
      {!allowed ? <p className="simple-reply-blocked">{isInternal ? "Внутренние заметки недоступны для вашей роли." : props.replyBlockedReason || "Ответ доступен исполнителю после начала работы."}</p> : null}
      <textarea aria-label={isInternal ? "Внутренняя заметка" : "Сообщение сотруднику"} placeholder={isInternal ? "Написать заметку для поддержки…" : "Написать сообщение сотруднику…"} disabled={!allowed || props.pending} value={props.text} onChange={(event) => props.onTextChange(event.target.value)} rows={2}
        onKeyDown={(event) => { if (event.key === "Enter" && (event.ctrlKey || event.metaKey) && !event.nativeEvent.isComposing) { event.preventDefault(); if (canSend) { pinnedRef.current = true; props.onSend(); } } }} />
      {props.attachments.length ? <div className="simple-draft-attachments">{props.attachments.map((attachment) => <div className="simple-inline" key={attachment.artifact_id}><Paperclip size={14} aria-hidden /><span>{attachment.name}</span><button className="simple-link" type="button" aria-label={`Убрать вложение ${attachment.name}`} disabled={props.pending} onClick={() => props.onRemoveAttachment(attachment.artifact_id)}>×</button></div>)}</div> : null}
      {props.uploadError ? <p role="alert" className="simple-risk">{props.uploadError}</p> : null}
      <div className="simple-composer__actions">{props.onUpload ? <><input ref={props.inputRef} type="file" multiple hidden onChange={props.onUpload} /><button className="simple-button simple-attach" type="button" disabled={!allowed || props.pending} onClick={() => props.inputRef?.current?.click()}><Paperclip size={16} aria-hidden />Прикрепить файл</button></> : null}
        <span className="simple-keyboard-hint">Ctrl+Enter — отправить</span><button className="simple-button simple-button--primary" type="submit" disabled={!canSend}>{props.pending ? <LoaderCircle size={15} aria-hidden /> : <Send size={15} aria-hidden />}{props.pending ? "Отправляем…" : "Отправить"}</button></div>
    </form> : null}
  </section>;
}
