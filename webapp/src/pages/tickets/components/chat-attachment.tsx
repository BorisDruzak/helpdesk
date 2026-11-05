import { Download, FileImage, FileText, X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

// Inline content uses only the existing same-origin, authorized artifact route.
// Keep the server's historical ticket ownership fallback, but never embed query
// credentials, unknown parameters, external URLs, SVG, HTML or document embeds.
const artifactUrl = /^\/api\/artifacts\/[A-Za-z0-9_-]+\/download(?:\?ticket_id=[A-Za-z0-9_-]+)?$/;
const rasterMime = /^image\/(png|jpeg|gif|webp|avif|bmp|x-ms-bmp)$/i;
function imageAttachment(attachment: Record<string, unknown>, name: string) {
  const mime = String(attachment.mime_type ?? attachment.mime ?? "").toLowerCase();
  return mime && mime !== "application/octet-stream" ? rasterMime.test(mime) : /\.(png|jpe?g|gif|webp|avif|bmp)$/i.test(name);
}

function ImageViewer({ url, name, onClose }: { url: string; name: string; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const title = useId();
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const dialog = ref.current!;
    dialog.showModal();
    return () => dialog.close();
  }, []);
  return <dialog ref={ref} className="simple-image-viewer" aria-labelledby={title} onClose={onClose}
    onClick={(event) => {
      if (event.target !== event.currentTarget) return;
      const bounds = event.currentTarget.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) ref.current?.close();
    }}>
    <header><h3 id={title}>Просмотр изображения: {name}</h3><button autoFocus className="simple-button" aria-label="Закрыть просмотр изображения" type="button" onClick={() => ref.current?.close()}><X size={20} aria-hidden /></button></header>
    <div className="simple-image-viewer__canvas">{failed ? <p role="status">Не удалось открыть изображение. Попробуйте скачать файл.</p> : <img src={url} alt={name} onError={() => setFailed(true)} />}</div>
    <a className="simple-button" href={url} download={name}><Download size={16} aria-hidden />Скачать изображение</a>
  </dialog>;
}

export function ChatAttachment({ attachment }: { attachment: Record<string, unknown> }) {
  const name = String(attachment.name ?? attachment.filename ?? attachment.file_name ?? attachment.original_name ?? "Вложение");
  const url = String(attachment.url ?? attachment.download_url ?? "");
  const [open, setOpen] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  if (!artifactUrl.test(url)) return <span>{name}</span>;
  if (!imageAttachment(attachment, name)) return <a href={url} download={name}><FileText size={18} aria-hidden />{name}</a>;
  return <div className="simple-image-attachment">
    <button className="simple-image-attachment__preview" type="button" aria-label={`Открыть изображение ${name}`} aria-haspopup="dialog" onClick={() => setOpen(true)}>
      {failed ? <span className="simple-image-attachment__fallback"><FileImage size={24} aria-hidden />Миниатюра недоступна</span> : <>
        <img alt={`Миниатюра: ${name}`} src={url} loading="lazy" decoding="async" onLoad={() => setLoaded(true)} onError={() => setFailed(true)} />
        {!loaded ? <span className="simple-image-attachment__loading" role="status">Загружаем миниатюру…</span> : null}
      </>}
      <span>{name}</span>
    </button>
    <a className="simple-image-attachment__download" href={url} download={name} aria-label={`Скачать ${name}`}><Download size={14} aria-hidden />Скачать</a>
    {open ? <ImageViewer url={url} name={name} onClose={() => setOpen(false)} /> : null}
  </div>;
}
