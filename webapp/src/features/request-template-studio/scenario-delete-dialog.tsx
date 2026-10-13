import { useEffect, useRef, useState } from "react";
import { Button } from "../../components/ui/button";
import { Select } from "../../components/ui/select";
import { fieldUses } from "./scenario-builder-model";
import type { ScenarioBlock, ScenarioDraftDefinition } from "./scenario-contract";
import { deleteMapBlock } from "./scenario-map-model";

export function ScenarioDeleteDialog({ definition, block, disabled, onDelete, onClose }: { definition: ScenarioDraftDefinition; block: ScenarioBlock; disabled: boolean; onDelete: (next: ScenarioDraftDefinition) => void; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [replacement, setReplacement] = useState(block.transitions?.length === 1 && block.transitions[0].to !== block.id ? block.transitions[0].to : "");
  const [action, setAction] = useState<"redirect" | "detach">(block.transitions?.length === 1 ? "redirect" : "detach");
  const [entranceAction, setEntranceAction] = useState<"remove" | "reassign">("remove");
  const [error, setError] = useState("");
  const blocks = definition.blocks ?? [], entries = definition.entry_points?.filter(entry => entry.target_block_id === block.id) ?? [];
  const incoming = blocks.filter(item => item.transitions?.some(edge => edge.to === block.id));
  const dependencies = block.kind === "form_page" ? block.fields.flatMap(field => fieldUses(definition, field.key, block.id)) : [];
  useEffect(() => { const element = dialog.current; element?.showModal(); return () => { if (element?.open) element.close(); }; }, []);
  return <dialog ref={dialog} className="studio-create-dialog studio-delete-dialog" aria-label={`Удалить блок «${block.title}»?`} onCancel={onClose} onClose={onClose} onKeyDown={event => event.stopPropagation()}>
    <div className="studio-create-dialog__header"><h2 className="text-lg font-semibold">Удалить блок «{block.title}»?</h2><Button autoFocus variant="ghost" onClick={onClose}>Отмена удаления</Button></div>
    <fieldset disabled={disabled} className="studio-create-dialog__body space-y-4">
      <p>Входящие связи: {incoming.map(item => item.title).join(", ") || "нет"}. Пункты каталога: {entries.map(entry => entry.title).join(", ") || "нет"}.</p>
      {!!dependencies.length && <p role="alert">Ответы этого блока используются: {dependencies.join("; ")}. Сначала измените эти условия.</p>}
      <label className="block">Что сделать со связями?<Select value={action} onChange={event => setAction(event.target.value as typeof action)}><option value="detach">Убрать связи с удаляемым блоком</option><option value="redirect">Перенаправить на другой блок</option></Select></label>
      {!!entries.length && <label className="block">Пункты каталога<Select value={entranceAction} onChange={event => setEntranceAction(event.target.value as typeof entranceAction)}><option value="remove">Убрать из черновика</option><option value="reassign">Переназначить другому блоку</option></Select></label>}
      {(action === "redirect" || entries.length > 0 && entranceAction === "reassign") && <label className="block">Перенаправить на<Select value={replacement} onChange={event => setReplacement(event.target.value)}><option value="">Выберите блок</option>{blocks.filter(item => item.id !== block.id).map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</Select></label>}
      <p className="text-sm text-slate-500">Удаление можно отменить кнопкой «Отменить изменение». Перед публикацией проверьте маршрут.</p>
      {error && <p role="alert" className="text-red-700">{error}</p>}
      <Button disabled={disabled || !!dependencies.length} onClick={() => { try { const next = deleteMapBlock(definition, block.id, replacement || null, entries.length ? entranceAction : undefined, action); onDelete(next); } catch (failure) { setError(failure instanceof Error ? failure.message : "Не удалось удалить блок"); } }}>Подтвердить удаление блока</Button>
    </fieldset>
  </dialog>;
}
