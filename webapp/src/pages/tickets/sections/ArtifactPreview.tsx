import {
  FileImage,
  FileText,
  Film,
  Paperclip,
} from "lucide-react";
import {
  useEffect,
  useState,
} from "react";
import {
  NormalizedAttachment,
  formatDateTime,
} from '../detail-formatting';
export function ArtifactPreview({ attachment }: { attachment: NormalizedAttachment }) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(attachment.mediaType !== "file");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!attachment.downloadUrl || attachment.mediaType === "file") {
      setLoading(false);
      return;
    }

    let active = true;
    let localUrl: string | null = null;

    setLoading(true);
    setError(null);

    void fetch(attachment.downloadUrl, { credentials: "same-origin" })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error("Не удалось загрузить артефакт");
        }
        return response.blob();
      })
      .then((blob) => {
        if (!active) {
          return;
        }
        localUrl = URL.createObjectURL(blob);
        setObjectUrl(localUrl);
      })
      .catch((loadError) => {
        if (!active) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : "Ошибка загрузки");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
      if (localUrl) {
        URL.revokeObjectURL(localUrl);
      }
    };
  }, [attachment.downloadUrl, attachment.mediaType]);

  return (
    <div className="space-y-3 rounded-[1rem] border border-border bg-white px-4 py-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-semibold text-slate-950">{attachment.label}</p>
          <p className="mt-1 text-xs text-slate-500">{attachment.summary}</p>
        </div>
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-brand-50 text-brand-700">
          {attachment.mediaType === "image" ? (
            <FileImage className="h-4 w-4" />
          ) : attachment.mediaType === "video" ? (
            <Film className="h-4 w-4" />
          ) : (
            <FileText className="h-4 w-4" />
          )}
        </div>
      </div>

      {loading ? (
        <div className="rounded-panel border border-dashed border-border bg-surface-subtle px-4 py-8 text-center text-sm text-slate-500">
          Загружаем предпросмотр...
        </div>
      ) : null}

      {!loading && error ? (
        <div className="rounded-panel border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      {!loading && !error && attachment.mediaType === "image" && objectUrl ? (
        <img
          alt={attachment.label}
          className="max-h-[22rem] w-full rounded-panel border border-border object-contain"
          loading="lazy"
          src={objectUrl}
        />
      ) : null}

      {!loading && !error && attachment.mediaType === "video" && objectUrl ? (
        <video
          className="max-h-[22rem] w-full rounded-panel border border-border"
          controls
          preload="metadata"
          src={objectUrl}
        />
      ) : null}

      {attachment.mediaType === "file" && attachment.downloadUrl ? (
        <a
          className="inline-flex items-center gap-2 rounded-pill border border-border px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:border-brand-200 hover:bg-brand-50 hover:text-brand-800"
          href={attachment.downloadUrl}
          rel="noreferrer"
          target="_blank"
        >
          <Paperclip className="h-4 w-4" />
          Скачать файл
        </a>
      ) : null}

      <p className="text-xs text-slate-400">
        {attachment.sourceLabel} • {formatDateTime(attachment.sourceTimestamp)}
      </p>
    </div>
  );
}