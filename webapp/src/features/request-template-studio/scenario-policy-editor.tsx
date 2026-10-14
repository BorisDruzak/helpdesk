import { useEffect, useRef, useState } from "react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { buildClosurePreset, buildVisibilityPreset, ClosurePolicyControls, VisibilityPolicyControls, VisibilityPolicyPreview } from "../forms-builder/forms-builder-panel";
import { publishHelpdeskPolicy, type AdminHelpdeskPolicyItem } from "../forms-builder/api";

export type EditableScenarioPolicy = "closure" | "visibility";
export const editablePolicyLabels = { closure: "Закрытие обращения", visibility: "Видимость обращения" };

// Rules are published to the canonical registry without an inherited scope target.
// Only the explicit reference in a published service map activates this copy.
export function ScenarioPolicyEditor({ kind, serviceTitle, source, disabled, onRegistered, onApply, onClose }: {
  kind: EditableScenarioPolicy; serviceTitle: string; source?: AdminHelpdeskPolicyItem; disabled: boolean;
  onRegistered: (policy: AdminHelpdeskPolicyItem) => void; onApply: (policy: AdminHelpdeskPolicyItem) => void; onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const inFlight = useRef(false);
  const [code] = useState(() => `studio_${kind}_${crypto.randomUUID().replaceAll("-", "")}`);
  const [title, setTitle] = useState(`${serviceTitle}: ${editablePolicyLabels[kind]}`);
  const [config, setConfig] = useState<Record<string, unknown>>(() => source ? structuredClone(source.config) : JSON.parse(kind === "closure" ? buildClosurePreset() : buildVisibilityPreset()));
  const [baseline] = useState(() => JSON.stringify({ title, config }));
  const [review, setReview] = useState(false), [discard, setDiscard] = useState(false), [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [published, setPublished] = useState<AdminHelpdeskPolicyItem | null>(null);
  useEffect(() => { const el = dialog.current; el?.showModal(); return () => { if (el?.open) el.close(); }; }, []);
  function close() {
    if (inFlight.current) return;
    if (!published && JSON.stringify({ title, config }) !== baseline) setDiscard(true); else onClose();
  }
  function check() {
    setError("");
    if (!title.trim()) { setError("Укажите название правила."); return; }
    const confirmation = config.requester_confirmation as Record<string, unknown> | undefined;
    const days = confirmation?.auto_close_after_days;
    if (kind === "closure" && days != null && (!Number.isInteger(Number(days)) || Number(days) < 0)) { setError("Срок автозакрытия должен быть целым числом от 0 дней. 0 отключает автозакрытие."); return; }
    setReview(true);
  }
  async function publish() {
    if (disabled || inFlight.current || !review || published) return;
    inFlight.current = true; setPending(true); setError("");
    try {
      const result = await publishHelpdeskPolicy({ kind, code, title: title.trim(), description: `Правило для услуги «${serviceTitle}»`, scope_level: "request_template", scope_ref: null, config });
      setPublished(result.policy); onRegistered(result.policy);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Не удалось опубликовать правило. Настройки сохранены в этом окне."); }
    finally { inFlight.current = false; setPending(false); }
  }
  return <dialog ref={dialog} className="studio-create-dialog" aria-label={`Настройка правила: ${editablePolicyLabels[kind]}`} onCancel={event => { event.preventDefault(); close(); }} onKeyDown={event => event.stopPropagation()}>
    <div className="studio-create-dialog__header"><div><h2 className="text-lg font-semibold">{editablePolicyLabels[kind]}</h2><p className="mt-2 text-sm">Для услуги «{serviceTitle}»</p></div><Button disabled={pending} variant="ghost" onClick={close}>Вернуться к услуге</Button></div>
    <div className="studio-create-dialog__body space-y-4">
      <p className="text-sm">{kind === "closure" ? "Определите, что поддержка должна заполнить перед завершением и нужно ли подтверждение сотрудника. 0 дней отключает автозакрытие." : "Задайте названия статусов для сотрудника и доступные ему поля. Внутренние данные остаются защищены серверными правами."}</p>
      {source && <p className="rounded border p-3 text-sm">Основа: «{source.title}». Изменения сохранятся отдельным правилом для этой услуги; исходное общее правило сохранится.</p>}
      <fieldset disabled={disabled || pending || review || !!published} className="space-y-4">
        <label className="block">Название правила<Input autoFocus maxLength={300} value={title} onChange={event => setTitle(event.target.value)} /></label>
        {kind === "closure" ? <ClosurePolicyControls config={config} onChange={setConfig} runtimeDefaults /> : <><VisibilityPolicyControls config={config} onChange={setConfig} /><VisibilityPolicyPreview config={config} /></>}
      </fieldset>
      {review && !published && <div role="status" className="rounded border border-emerald-200 bg-emerald-50 p-3 text-sm"><p>Настройки готовы к отправке. Сервер проверит правило при публикации.</p><p>После публикации нажмите «Применить к услуге», сохраните черновик карты и повторите проверку публикации услуги.</p></div>}
      {published && <p role="status" className="rounded border border-emerald-200 bg-emerald-50 p-3 text-sm">Правило «{published.title}» опубликовано. Примените его к черновику услуги, затем проверьте сохранение и карту. Автосохранение может сохранить черновик сразу после применения. Изменения услуги ещё не опубликованы.</p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {discard && <div role="alert" className="space-y-2 rounded border border-amber-300 p-3"><p>Есть несохранённые изменения правила.</p><Button variant="outline" onClick={() => setDiscard(false)}>Продолжить настройку</Button><Button variant="ghost" onClick={onClose}>Закрыть без сохранения</Button></div>}
    </div>
    <div className="studio-create-dialog__footer">
      <Button disabled={pending} variant="outline" onClick={close}>Отмена</Button>
      {published ? <Button disabled={disabled} onClick={() => onApply(published)}>Применить к услуге</Button> : review ? <div className="flex flex-wrap gap-2"><Button disabled={pending} variant="outline" onClick={() => setReview(false)}>Изменить настройки</Button><Button disabled={disabled || pending} onClick={() => void publish()}>{pending ? "Публикуем правило…" : "Опубликовать правило"}</Button></div> : <Button disabled={disabled} onClick={check}>Проверить и продолжить</Button>}
    </div>
  </dialog>;
}
