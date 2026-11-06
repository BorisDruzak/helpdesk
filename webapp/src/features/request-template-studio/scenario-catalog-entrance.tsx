import { useState } from "react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { isPolicyAttachment } from "./scenario-policy-attachments-model";

export function ScenarioCatalogEntrance({ definition, disabled, onCreate, onClose }: {
  definition: ScenarioDraftDefinition; disabled: boolean; onCreate: (target: string, title: string) => void; onClose: () => void;
}) {
  const [target, setTarget] = useState("");
  const [title, setTitle] = useState("");
  const blocks = (definition.blocks ?? []).filter(block => !isPolicyAttachment(block));
  const full = (definition.entry_points?.length ?? 0) >= 64;
  return <section role="dialog" aria-label="Новый вход из каталога" className="space-y-3 rounded-xl border bg-white p-4">
    <h3 className="font-semibold">Новый вход из каталога</h3>
    <p className="text-sm">Всегда подключён к блоку «Начало». Сотрудник выбирает этот вход в каталоге и сразу открывает указанный шаг.</p>
    {!blocks.length && <p role="status">Сначала добавьте вопрос или инструкцию на карту.</p>}
    {full && <p role="status">Достигнут лимит 64 точек входа.</p>}
    <label className="block">Первый блок для сотрудника<Select disabled={disabled || full || !blocks.length} value={target} onChange={event => { const id=event.target.value;setTarget(id);if(!title.trim())setTitle(blocks.find(block=>block.id===id)?.title??""); }}><option value="">Выберите блок на карте</option>{blocks.map(block=><option key={block.id} value={block.id}>{block.title}</option>)}</Select></label>
    <label className="block">Название входа<Input disabled={disabled || full} maxLength={300} value={title} onChange={event=>setTitle(event.target.value)}/></label>
    <div className="flex flex-wrap gap-2"><Button disabled={disabled || full || !title.trim() || !blocks.some(block=>block.id===target)} onClick={()=>onCreate(target,title.trim())}>Создать вход от «Начала»</Button><Button variant="ghost" onClick={onClose}>Отмена</Button></div>
  </section>;
}
