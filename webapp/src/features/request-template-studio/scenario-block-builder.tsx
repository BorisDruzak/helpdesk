import { useEffect, useRef, useState } from "react";
import { Button } from "../../components/ui/button";
import { Select } from "../../components/ui/select";
import { EmptyState } from "../../components/ui-page/page-components";
import type { ScenarioBlock, ScenarioDraftDefinition } from "./scenario-contract";
import { addBlock, blockLabels, duplicateBlock, moveBlock, removeBlock } from "./scenario-builder-model";
import { ScenarioBlockEditor } from "./scenario-block-editor";
import { ScenarioPreviewPanel } from "./scenario-preview-panel";

type Props = { definition: ScenarioDraftDefinition; disabled: boolean; onChange: (value: ScenarioDraftDefinition) => void; onSimulate?: () => void };
export function ScenarioBlockBuilder({ definition, disabled, onChange, onSimulate }: Props) {
  const [selected, setSelected] = useState(definition.entry_block_id);
  const [kind, setKind] = useState<ScenarioBlock["kind"]>("form_page");
  const [past, setPast] = useState<ScenarioDraftDefinition[]>([]);
  const [future, setFuture] = useState<ScenarioDraftDefinition[]>([]);
  const [preview, setPreview] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [replacement, setReplacement] = useState("");
  const [error, setError] = useState("");
  const [focusTitle, setFocusTitle] = useState(false);
  const emitted = useRef(definition);
  const blocks = definition.blocks ?? [];
  const block = blocks.find(item => item.id === selected) ?? blocks[0];
  const index = blocks.findIndex(item => item.id === block?.id);
  useEffect(() => {
    if (JSON.stringify(emitted.current) !== JSON.stringify(definition)) { setPast([]); setFuture([]); }
    emitted.current = definition;
  }, [definition]);
  function change(next: ScenarioDraftDefinition) {
    if (disabled || JSON.stringify(next) === JSON.stringify(definition)) return;
    setPast(previous => [...previous.slice(-99), structuredClone(definition)]);
    setFuture([]); setError(""); emitted.current = next; onChange(next);
  }
  function perform(operation: () => ScenarioDraftDefinition) {
    try { change(operation()); } catch (failure) { setError(failure instanceof Error ? failure.message : "Изменение не выполнено"); }
  }
  function choose(id: string) { setSelected(id); setRemoving(false); setError(""); setFocusTitle(false); }
  function move(delta: number) {
    if (!block) return;
    const target = blocks[index + delta];
    if (!target) return;
    change(delta < 0 ? moveBlock(definition, block.id, target.id) : moveBlock(definition, target.id, block.id));
  }
  return <div className="min-w-0 space-y-4">
    <h2 className="text-lg font-semibold">Блоки сценария</h2>
    {onSimulate && <Button variant="secondary" onClick={onSimulate}>Предпросмотр всей ветки</Button>}
    <div className="flex flex-wrap items-end gap-2">
      <label className="min-w-0 flex-1">Тип нового блока<Select disabled={disabled} value={kind} onChange={event => setKind(event.target.value as ScenarioBlock["kind"])}>{Object.entries(blockLabels).map(([type, title]) => <option key={type} value={type}>{title}</option>)}</Select></label>
      <Button disabled={disabled || blocks.length >= 256} onClick={() => {
        const next = addBlock(definition, kind, block?.id ?? null);
        const added = next.blocks!.find(item => !blocks.some(old => old.id === item.id))!;
        change(next); setSelected(added.id); setFocusTitle(true);
      }}>Добавить блок</Button>
      <Button variant="ghost" disabled={disabled || !past.length} onClick={() => {
        const next = past[past.length - 1]; setPast(past.slice(0, -1)); setFuture([structuredClone(definition), ...future]); emitted.current = next; onChange(next);
      }}>Отменить изменение</Button>
      <Button variant="ghost" disabled={disabled || !future.length} onClick={() => {
        const [next, ...rest] = future; setFuture(rest); setPast([...past, structuredClone(definition)]); emitted.current = next; onChange(next);
      }}>Повторить изменение</Button>
    </div>
    {!blocks.length ? <EmptyState title="Сценарий пока пуст" description="Добавьте страницу вопросов, инструкцию или другой блок из списка." /> : <div className={`grid min-w-0 gap-4 ${preview ? "lg:max-[1440px]:grid-cols-[260px_minmax(0,1fr)] min-[1440px]:grid-cols-[260px_minmax(0,1fr)_300px]" : "lg:grid-cols-[260px_minmax(0,1fr)]"}`}>
      <aside className="min-w-0 space-y-3 rounded-xl border p-3">
        <h3 className="font-semibold">Шаги</h3>
        <ul aria-label="Блоки сценария" className="space-y-2">{blocks.map(item => <li key={item.id} draggable={!disabled} onDragStart={event => event.dataTransfer.setData("application/x-scenario-block", item.id)} onDragOver={event => { if (!disabled) event.preventDefault(); }} onDrop={event => {
          if (disabled) return; event.preventDefault(); change(moveBlock(definition, event.dataTransfer.getData("application/x-scenario-block"), item.id));
        }}>
          <Button className="h-auto w-full justify-start whitespace-normal break-words text-left" variant={item.id === block?.id ? "secondary" : "ghost"} aria-pressed={item.id === block?.id} onClick={() => choose(item.id)}>{item.title}</Button>
          <p className="px-2 text-xs text-slate-500">{blockLabels[item.kind]}{definition.entry_block_id === item.id ? " · начало" : ""}</p>
        </li>)}</ul>
        <p className="text-xs text-slate-500">Перетащите блок или используйте кнопки «вверх» и «вниз». Порядок списка не изменяет переходы.</p>
      </aside>
      <section aria-label="Редактор выбранного блока" className="min-w-0 space-y-4 rounded-xl border p-4">
        <div className="flex flex-wrap gap-2">
          <Button variant="ghost" disabled={disabled || index <= 0} onClick={() => move(-1)}>Переместить блок вверх</Button>
          <Button variant="ghost" disabled={disabled || index >= blocks.length - 1} onClick={() => move(1)}>Переместить блок вниз</Button>
          <Button variant="ghost" disabled={disabled || blocks.length >= 256} onClick={() => {
            const next = duplicateBlock(definition, block.id); change(next); setSelected(next.blocks![index + 1].id); setFocusTitle(true);
          }}>Копировать блок</Button>
          <Button variant="ghost" disabled={disabled} onClick={() => { setRemoving(true); setReplacement(""); }}>Удалить блок</Button>
          <Button variant="ghost" disabled={disabled || definition.entry_block_id === block.id} onClick={() => change({ ...definition, entry_block_id: block.id })}>Начать с этого блока</Button>
          <Button variant="secondary" aria-expanded={preview} onClick={() => setPreview(!preview)}>{preview ? "Скрыть предпросмотр" : "Предпросмотр шага"}</Button>
        </div>
        {removing && <fieldset className="space-y-3 rounded-lg border border-amber-300 p-3" disabled={disabled}>
          <legend>Удаление блока «{block.title}»</legend>
          <p>Входящие переходы: {blocks.filter(item => item.transitions?.some(edge => edge.to === block.id)).map(item => item.title).join(", ") || "нет"}. {definition.entry_block_id === block.id ? "Это начало сценария." : ""}</p>
          <label className="block">Перенаправить на<Select value={replacement} onChange={event => setReplacement(event.target.value)}><option value="">Выберите блок</option>{blocks.filter(item => item.id !== block.id).map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</Select></label>
          <div className="flex flex-wrap gap-2"><Button onClick={() => perform(() => { const next = removeBlock(definition, block.id, replacement || null); setRemoving(false); return next; })}>Подтвердить удаление блока</Button><Button variant="ghost" onClick={() => setRemoving(false)}>Отмена удаления</Button></div>
        </fieldset>}
        {error && <p role="alert">{error}</p>}
        <ScenarioBlockEditor key={block.id} block={block} definition={definition} disabled={disabled} focusTitle={focusTitle} onChange={next => change({ ...definition, blocks: blocks.map(old => old.id === block.id ? next : old) })} />
      </section>
      {preview && <ScenarioPreviewPanel block={block} onClose={() => setPreview(false)} />}
    </div>}
  </div>;
}
