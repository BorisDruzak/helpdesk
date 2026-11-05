import { useLayoutEffect, useRef, useState } from "react";

type Queue = { files: File[]; active: boolean; running: boolean; errors: string[] };
export function useChatUploads<T>({ scope, enabled, upload, onUploaded, onStart, onError, errorMessage }: {
  scope: string | null; enabled: boolean; upload: (file: File) => Promise<T>;
  onUploaded: (item: T, file: File) => void; onStart: () => void;
  onError: (message: string) => void; errorMessage: (error: unknown) => string;
}) {
  const [uploading, setUploading] = useState(false);
  const queue = useRef<Queue>({ files: [], active: false, running: false, errors: [] });
  useLayoutEffect(() => {
    const current: Queue = { files: [], active: true, running: false, errors: [] };
    queue.current = current;
    setUploading(false);
    return () => { current.active = false; current.files.length = 0; };
  }, [scope, enabled]);

  function addFiles(files: File[]) {
    if (!scope || !enabled || !files.length) return;
    const current = queue.current;
    current.files.push(...files);
    if (current.running) return;
    current.running = true;
    current.errors = [];
    setUploading(true);
    onStart();
    void (async () => {
      try {
        while (current.active && current.files.length) {
          const file = current.files.shift()!;
          try {
            const item = await upload(file);
            if (!current.active) return;
            onUploaded(item, file);
          } catch (error) {
            if (!current.active) return;
            current.errors.push(`${file.name}: ${errorMessage(error)}`);
            onError(current.errors.join("\n"));
          }
        }
      } finally {
        current.running = false;
        if (current.active) setUploading(false);
      }
    })();
  }
  return { uploading, addFiles };
}
