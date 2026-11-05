import { useEffect, useRef, useState, type DragEvent } from "react";
import { Paperclip, X } from "lucide-react";
import { ChatAttachment } from "./chat-attachment";
import "./chat-file-draft.css";

export function useChatFileDrop(disabled: boolean, onFiles?: (files: File[]) => void) {
  const [dragging, setDragging] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const depth = useRef(0);
  useEffect(() => {
    const reset = () => { depth.current = 0; setDragging(false); };
    window.addEventListener("drop", reset); window.addEventListener("dragend", reset); window.addEventListener("blur", reset);
    return () => { window.removeEventListener("drop", reset); window.removeEventListener("dragend", reset); window.removeEventListener("blur", reset); };
  }, []);
  useEffect(() => { if (disabled) { depth.current = 0; setDragging(false); } }, [disabled]);
  const hasFiles = (event: DragEvent<HTMLElement>) => Array.from(event.dataTransfer.types).includes("Files");
  const hasUrl = (event: DragEvent<HTMLElement>) => Array.from(event.dataTransfer.types).some(type => ["text/uri-list", "text/html"].includes(type));
  return { dragging, feedback, handlers: {
    onDragEnter: (event: DragEvent<HTMLElement>) => {
      if (!hasFiles(event)) { if (hasUrl(event)) event.preventDefault(); return; }
      event.preventDefault();
      if (!disabled && onFiles) { depth.current++; setDragging(true); }
    },
    onDragOver: (event: DragEvent<HTMLElement>) => {
      if (!hasFiles(event)) { if (hasUrl(event)) { event.preventDefault(); event.dataTransfer.dropEffect = "none"; } return; }
      event.preventDefault();
      event.dataTransfer.dropEffect = disabled || !onFiles ? "none" : "copy";
    },
    onDragLeave: (event: DragEvent<HTMLElement>) => {
      if (!hasFiles(event)) return;
      depth.current = Math.max(0, depth.current - 1);
      if (!depth.current) setDragging(false);
    },
    onDrop: (event: DragEvent<HTMLElement>) => {
      if (!hasFiles(event)) {
        if (hasUrl(event)) { event.preventDefault(); depth.current = 0; setDragging(false); setFeedback("Перетаскивайте файлы с компьютера. Ссылки на изображения не прикрепляются."); }
        return;
      }
      event.preventDefault();
      depth.current = 0; setDragging(false);
      if (disabled || !onFiles) return;
      const items = Array.from(event.dataTransfer.items ?? []).filter(item => item.kind === "file");
      let directories = false;
      const files = items.length ? items.flatMap(item => {
        if (item.webkitGetAsEntry?.()?.isDirectory) { directories = true; return []; }
        const file = item.getAsFile(); return file ? [file] : [];
      }) : Array.from(event.dataTransfer.files);
      setFeedback(directories ? "Папки не прикрепляются. Перетащите отдельные файлы." : null);
      if (files.length) onFiles(files);
    },
  } };
}

export function ChatFileDropFeedback({ message }: { message: string | null }) {
  return message ? <p className="chat-file-drop-feedback" role="status">{message}</p> : null;
}

export function ChatFileDropOverlay({ active }: { active: boolean }) {
  return active ? <div className="chat-file-drop-overlay" role="status"><Paperclip size={32} aria-hidden /><strong>Отпустите файлы, чтобы прикрепить к сообщению</strong><span>Они появятся в черновике. Отправка — вместе с вашим текстом.</span></div> : null;
}

export type DraftAttachment = { artifact_id: string; name?: string | null; filename?: string; url?: string | null; mime_type?: string | null };
export function ChatAttachmentDrafts({ attachments, onRemove, disabled, uploading }: {
  attachments: DraftAttachment[]; onRemove: (id: string) => void; disabled?: boolean; uploading?: boolean;
}) {
  if (!attachments.length && !uploading) return null;
  return <section className="chat-attachment-drafts" aria-label="Вложения к сообщению">
    <header><strong>Вложения · {attachments.length}</strong><span>{uploading ? "Загружаем файлы…" : "Будут отправлены вместе с текстом"}</span></header>
    <ul>{attachments.map(attachment => <li key={attachment.artifact_id}>
      <ChatAttachment attachment={{...attachment, name: attachment.name || attachment.filename || "Вложение"}} />
      <button className="chat-draft-remove" type="button" disabled={disabled} aria-label={`Убрать вложение ${attachment.name || attachment.filename || "Вложение"}`} onClick={() => onRemove(attachment.artifact_id)}><X size={15} aria-hidden /></button>
    </li>)}</ul>
  </section>;
}
