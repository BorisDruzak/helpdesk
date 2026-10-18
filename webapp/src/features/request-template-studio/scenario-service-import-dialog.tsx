import { useEffect, useRef, useState } from "react";
import { Button } from "../../components/ui/button";
import { Select } from "../../components/ui/select";
import { createServiceFromDocument, previewServiceDocument, ScenarioApiError, type ScenarioCatalog, type ScenarioDetail, type ScenarioServiceDocumentPreview } from "./scenario-api";

type Props = { catalog: ScenarioCatalog; initialCategory?: string | null; disabled?: boolean; onClose: () => void; onCreated: (detail: ScenarioDetail) => void; onDirty?: (dirty: boolean) => void };
type Issue = { code: string; path: string; message?: string };
const maxBytes = 1048576;
export function ScenarioServiceImportDialog({ catalog, initialCategory, disabled = false, onClose, onCreated, onDirty }: Props) {
  const destination = catalog.categories.find(item => item.id === initialCategory);
  const [service, setService] = useState(destination?.service_code ?? (initialCategory?.startsWith("service:") ? initialCategory.slice(8) : (catalog.services.find(item => item.lifecycle_status === "published" && item.visibility === "public") ?? catalog.services.find(item => item.lifecycle_status !== "retired"))?.code ?? ""));
  const [category, setCategory] = useState(destination?.id ?? "");
  const [format, setFormat] = useState<"json" | "yaml">("yaml"), [content, setContent] = useState("");
  const [creationKey, setCreationKey] = useState<string>(() => crypto.randomUUID());
  const [preview, setPreview] = useState<ScenarioServiceDocumentPreview | null>(null);
  const [error, setError] = useState(""), [issues, setIssues] = useState<Issue[]>([]), [busy, setBusy] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null), pending = useRef(false), mounted = useRef(true);
  useEffect(() => { const element = dialog.current; mounted.current = true; element?.showModal(); return () => { mounted.current = false; element?.close(); }; }, []);
  useEffect(() => { onDirty?.(!!content.trim()); }, [content, onDirty]);
  useEffect(() => () => onDirty?.(false), [onDirty]);
  function invalidate() { setPreview(null); setIssues([]); setError(""); setCreationKey(crypto.randomUUID()); }
  function close() { if (!pending.current && (!content.trim() || window.confirm("Закрыть импорт без сохранения документа?"))) onClose(); }
  const input = { format, content, service_code: service, category_id: category || null, creation_key: creationKey };
  async function run(create: boolean) {
    if (disabled || pending.current || !content.trim() || !service || create && (!preview || preview.issues.length)) return;
    if (new TextEncoder().encode(content).byteLength > maxBytes) { setError("Размер документа должен быть не больше 1 МиБ."); setPreview(null); return; }
    pending.current = true; setBusy(true); setError(""); setIssues([]);
    try {
      if (create && preview) {
        const detail = await createServiceFromDocument({ ...input, creation_key: preview.creation_key, source_hash: preview.source_hash });
        if (mounted.current) onCreated(detail);
      } else {
        const result = await previewServiceDocument(input);
        if (mounted.current) { setPreview(result); setCreationKey(result.creation_key); }
      }
    } catch (failure) {
      if (!mounted.current) return;
      const code = failure instanceof ScenarioApiError ? failure.errorCode : undefined;
      if (!create || code === "IMPORT_PREVIEW_CHANGED" || code === "SERVICE_PROCESSING_DEFAULT_REQUIRED" || failure instanceof ScenarioApiError && failure.status < 500) setPreview(null);
      setIssues(failure instanceof ScenarioApiError ? failure.issues : []);
      setError(code === "IMPORT_PREVIEW_CHANGED" ? "Проверка устарела: документ или настройки раздела изменились. Проверьте документ заново." : code === "SERVICE_PROCESSING_DEFAULT_REQUIRED" ? "Обработка раздела не настроена. Настройте её в каталоге и повторите проверку. Документ сохранён в окне." : create && (!(failure instanceof ScenarioApiError) || failure.status >= 500) ? "Создание не подтверждено. Документ сохранён; повторите создание — повторный запрос использует тот же ключ и не создаст дубликат." : "Документ не принят. Исправьте ошибки и повторите проверку формата, структуры, очередей и календарей. Введённый текст сохранён.");
    } finally { pending.current = false; if (mounted.current) setBusy(false); }
  }
  async function loadFile(file?: File) {
    if (!file || disabled || pending.current) return;
    invalidate();
    if (file.size > maxBytes) { setError("Размер файла должен быть не больше 1 МиБ."); return; }
    pending.current = true; setBusy(true);
    try {
      const text = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer());
      if (mounted.current) { setContent(text); setFormat(file.name.toLowerCase().endsWith(".json") ? "json" : "yaml"); }
    } catch { if (mounted.current) setError("Не удалось прочитать файл UTF-8. Проверьте кодировку или вставьте документ текстом."); }
    finally { pending.current = false; if (mounted.current) setBusy(false); }
  }
  return <dialog ref={dialog} className="studio-create-dialog" aria-labelledby="studio-service-import-title" onCancel={event => { event.preventDefault(); close(); }}>
    <div className="studio-create-dialog__header"><div><h2 id="studio-service-import-title" className="text-xl font-semibold">Создать услугу из JSON/YAML</h2><p className="mt-2 text-sm text-slate-500">Загрузите описание процесса. Сначала сервер проверит его, затем вы явно создадите черновик.</p></div><Button variant="ghost" disabled={busy} aria-label="Закрыть импорт новой услуги" onClick={close}>×</Button></div>
    <div className="studio-create-dialog__body space-y-4" aria-busy={busy}>
      <fieldset disabled={disabled || busy} className="min-w-0 space-y-3">
        <label className="block">Раздел каталога<Select className="w-full" value={service} onChange={event => { invalidate(); setService(event.target.value); setCategory(""); }}><option value="">Выберите раздел</option>{catalog.services.filter(item => item.lifecycle_status !== "retired").map(item => <option key={item.code} value={item.code}>{item.public_title}</option>)}</Select></label>
        <label className="block">Категория новой услуги<Select className="w-full" value={category} onChange={event => { invalidate(); setCategory(event.target.value); }}><option value="">Без категории</option>{catalog.categories.filter(item => item.service_code === service && item.lifecycle_status !== "archived").map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</Select></label>
        <p className="text-sm text-slate-500">Выбранные раздел и категория применятся ко всем входам в каталог. Helpdesk создаст новые внутренние привязки; идентификаторы экспортированной услуги не будут переиспользованы. Очереди и календари проверяются по документу, автоматической замены нет.</p>
        <label className="block">Загрузить JSON/YAML<input className="mt-2 block max-w-full text-sm" type="file" accept=".json,.yaml,.yml" onChange={event => { const file = event.target.files?.[0]; void loadFile(file); }} /></label>
        <label className="block">Формат документа<Select className="w-full" value={format} onChange={event => { invalidate(); setFormat(event.target.value as "json" | "yaml"); }}><option value="yaml">YAML</option><option value="json">JSON</option></Select></label>
        <label className="block">Документ новой услуги<textarea className="field-base min-h-40 w-full font-mono text-xs" value={content} spellCheck={false} onChange={event => { invalidate(); setContent(event.target.value); }} /></label>
      </fieldset>
      {error && <p role="alert">{error}</p>}
      {!!issues.length && <ul aria-label="Ошибки импорта новой услуги" className="space-y-2 text-sm">{issues.map((issue, index) => <li key={index} className="break-words"><strong>{issue.path}</strong>: {issue.message || "Проверьте структуру и допустимое значение."}</li>)}</ul>}
      {preview && <section aria-label="Результат проверки документа" className="space-y-2 rounded border p-3"><h3 className="font-semibold">{preview.definition.title}</h3><p>Шагов: {preview.definition.blocks?.length ?? 0}. Входов в каталог: {preview.definition.entry_points?.length ?? 0}.</p>{preview.issues.length ? <ul className="space-y-2 text-sm">{preview.issues.map((issue, index) => <li key={index} className="break-words"><strong>{issue.path}</strong>: {issue.message}</li>)}</ul> : <p role="status">Документ проверен. Можно создать услугу-черновик.</p>}</section>}
    </div>
    <div className="studio-create-dialog__footer"><p className="text-xs text-slate-500">Публикация не выполняется. Черновик не виден сотрудникам.</p><div className="flex flex-wrap gap-2"><Button variant="outline" disabled={busy} onClick={close}>Отмена</Button><Button variant="secondary" disabled={disabled || busy || !content.trim() || !service} onClick={() => void run(false)}>Проверить документ</Button>{preview && !preview.issues.length && <Button disabled={disabled || busy} onClick={() => void run(true)}>Создать услугу-черновик</Button>}</div></div>
  </dialog>;
}
