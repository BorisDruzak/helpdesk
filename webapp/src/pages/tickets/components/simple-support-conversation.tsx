import { useEffect, useState, type ChangeEvent, type RefObject } from "react";
import type { SupportTicketAttachmentUpload } from "../../../features/queues/api";
import type { SupportWorkspaceTimelineItem } from "../../../features/queues/support-workspace-model";
export type SimpleSupportConversationProps = {
  items: SupportWorkspaceTimelineItem[]; mode: "public" | "internal"; text: string;
  canReply: boolean; canNote: boolean; pending: boolean; loading?: boolean; error?: boolean; uploadError?: string | null;
  onModeChange: (mode: "public" | "internal") => void; onTextChange: (text: string) => void; onSend: () => void;
  attachments: SupportTicketAttachmentUpload[]; onRemoveAttachment: (id: string) => void;
  inputRef?: RefObject<HTMLInputElement | null>; onUpload?: (event: ChangeEvent<HTMLInputElement>) => void;
};
export function SimpleSupportConversation(props: SimpleSupportConversationProps) {
  const [tab, setTab] = useState<"dialog" | "internal" | "history">(() => props.mode === "internal" ? "internal" : "dialog");
  useEffect(() => { setTab(props.mode === "internal" ? "internal" : "dialog"); }, [props.mode]);
  const items = props.items.filter((item) => tab === "dialog" ? item.kind === "message" : tab === "internal" ? item.kind === "internal" : item.kind === "history" || item.kind === "diagnostics");
  const isInternal = tab === "internal";
  const allowed = isInternal ? props.canNote : props.canReply;
  return <section className="simple-conversation" aria-label="Переписка обращения">
    <div className="simple-tabs simple-conversation__tabs" role="tablist" aria-label="Лента обращения">{([["dialog", "Диалог"], ["internal", "Внутренние заметки"], ["history", "История"]] as const).map(([id, label]) => <button type="button" role="tab" aria-selected={tab === id} disabled={props.pending} key={id} onClick={() => { setTab(id); if (id !== "history") props.onModeChange(id === "internal" ? "internal" : "public"); }}>{label}</button>)}</div>
    {props.loading ? <p className="simple-muted" role="status">Обновляем ленту…</p> : null}
    {props.error ? <p className="simple-notice" role="alert">Не удалось обновить ленту. Показаны последние загруженные сообщения.</p> : null}
    <div className="simple-conversation__messages" role="tabpanel" aria-label={tab === "dialog" ? "Диалог" : isInternal ? "Внутренние заметки" : "История"}>
      {!items.length && !props.loading ? <p className="simple-empty">{tab === "dialog" ? "Пока нет публичных сообщений." : isInternal ? "Внутренних заметок пока нет." : "Событий пока нет."}</p> : null}
      {items.map((item) => <article key={item.id} className="simple-message" data-kind={item.kind} data-from={item.fromRole}>
        <div className="simple-message__meta"><strong>{item.actor || item.title}</strong><time>{item.timestampLabel}</time></div>
        {tab === "history" ? <h4>{item.title}</h4> : null}<p>{item.body}</p>
        {item.operation ? <p className="simple-muted">{item.operation.statusLabel}{item.operation.summary ? ` · ${item.operation.summary}` : ""}</p> : null}
        {item.attachments.length ? <ul className="simple-message__attachments">{item.attachments.map((attachment, index) => {
          const url = String(attachment.url ?? attachment.download_url ?? "");
          const safe = url.startsWith("/") && !url.startsWith("//") && !url.includes("\\");
          const name = String(attachment.name ?? attachment.filename ?? attachment.file_name ?? "Вложение");
          return <li key={String(attachment.artifact_id ?? index)}>{safe ? <a href={url} target="_blank" rel="noreferrer">↗ {name}</a> : <span>{name}</span>}</li>;
        })}</ul> : null}
      </article>)}
    </div>
    {tab !== "history" ? <form className="simple-composer" onSubmit={(event) => { event.preventDefault(); if (allowed && !props.pending && (props.text.trim() || props.attachments.length)) props.onSend(); }}>
      {!allowed ? <p className="simple-notice">{isInternal ? "Внутренние заметки недоступны для вашей роли." : "Публичный ответ доступен после взятия обращения в работу назначенным оператором."}</p> : null}
      <textarea aria-label={isInternal ? "Внутренняя заметка" : "Сообщение сотруднику"} placeholder={isInternal ? "Написать заметку для поддержки…" : "Написать сообщение сотруднику…"} disabled={!allowed || props.pending} value={props.text} onChange={(event) => props.onTextChange(event.target.value)} rows={3} />
      {props.attachments.map((attachment) => <div className="simple-inline" key={attachment.artifact_id}><span className="simple-muted">{attachment.name}</span><button className="simple-link" type="button" aria-label={`Убрать вложение ${attachment.name}`} onClick={() => props.onRemoveAttachment(attachment.artifact_id)}>×</button></div>)}
      {props.uploadError ? <p role="alert" className="simple-risk">{props.uploadError}</p> : null}
      <div className="simple-composer__actions">{props.onUpload ? <><input ref={props.inputRef} type="file" multiple hidden onChange={props.onUpload} /><button className="simple-button" type="button" disabled={!allowed || props.pending} onClick={() => props.inputRef?.current?.click()}>Прикрепить файл</button></> : null}
        <button className="simple-button simple-button--primary" type="submit" disabled={!allowed || props.pending || (!props.text.trim() && !props.attachments.length)}>{props.pending ? "Отправляем…" : "Отправить"}</button></div>
      <p className="simple-muted">{isInternal ? "Заметку видит только поддержка. Заявитель её не увидит." : "Публичный ответ увидит сотрудник. Отправка не меняет статус обращения."}</p>
    </form> : null}
  </section>;
}
