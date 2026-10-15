import { useEffect, useRef } from "react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import { AdvancedDisclosure } from "../../components/ui-page/advanced-disclosure";
import type { ScenarioBlock, ScenarioDraftDefinition } from "./scenario-contract";
import { ScenarioFormPageEditor } from "./scenario-form-page-editor";
import { ScenarioConditionEditor } from "./scenario-condition-editor";
import { conditionFields } from "./scenario-builder-model";
import { diagnosticFailureLabels } from "./scenario-diagnostics";

type Props = { block: ScenarioBlock; definition: ScenarioDraftDefinition; disabled: boolean; onChange: (value: ScenarioBlock) => void; focusTitle: boolean; focusTransitions?: boolean; hideTransitions?: boolean };
export function ScenarioBlockEditor({ block, definition, disabled, onChange, focusTitle, focusTransitions, hideTransitions = false }: Props) {
  const titleRef = useRef<HTMLInputElement>(null);
  const transitionRef = useRef<HTMLSelectElement>(null);
  useEffect(() => {
    if (!focusTransitions) return;
    const target = transitionRef.current;
    const disclosure = target?.closest("details");
    if (disclosure) disclosure.open = true;
    if (target) target.focus(); else titleRef.current?.focus();
  }, [block.id, focusTransitions]);
  useEffect(() => { if (focusTitle) titleRef.current?.focus(); }, [block.id, focusTitle]);
  const fields = conditionFields(definition, block.id);
  const targets = (definition.blocks ?? []).filter(item => item.id !== block.id);
  const transitions = block.transitions ?? [];
  const issueTransitionIndex = Math.max(0, transitions.findIndex(edge => !targets.some(item => item.id === edge.to)));
  const terminal = block.kind === "finish" || block.kind === "submit_ticket";
  const resultValues = ({ resolution_check: ["yes", "no", "unknown"], instruction: ["acknowledged", "request_ticket"], diagnostic: Object.keys(diagnosticFailureLabels) } as Partial<Record<ScenarioBlock["kind"], string[]>>)[block.kind] ?? [];
  return <div className="min-w-0 space-y-4">
    {block.kind === "form_page" && block.fields.length === 1 ? <details><summary className="cursor-pointer text-sm font-semibold">Название шага на карте</summary><label className="block">Название блока<Input ref={titleRef} disabled={disabled} maxLength={300} value={block.title} onChange={event => onChange({ ...block, title: event.target.value })} /></label></details> : <label className="block">Название блока<Input ref={titleRef} disabled={disabled} maxLength={300} value={block.title} onChange={event => onChange({ ...block, title: event.target.value })} /></label>}
    {block.kind === "form_page" && <ScenarioFormPageEditor block={block} definition={definition} disabled={disabled} onChange={onChange} />}
    {block.kind === "instruction" && <fieldset disabled={disabled} className="space-y-3">
      <label className="block">Текст инструкции<textarea className="field-base min-h-40 w-full" maxLength={10000} value={block.content.body} onChange={event => onChange({ ...block, content: { ...block.content, body: event.target.value } })} /></label>
      <label><input type="checkbox" checked={!!block.acknowledgment_required} onChange={event => onChange({ ...block, acknowledgment_required: event.target.checked })} /> Требовать подтверждение прочтения</label>
      <AdvancedDisclosure title="Расширенные настройки"><label className="block">Формат текста<Select value={block.content.format ?? "plain"} onChange={event => onChange({ ...block, content: { ...block.content, format: event.target.value as "plain" | "markdown" } })}><option value="plain">Обычный текст</option><option value="markdown">Markdown</option></Select></label><p>HTML и исполняемые ссылки запрещены. Предпросмотр показывает текст безопасно.</p></AdvancedDisclosure>
    </fieldset>}
    {block.kind === "decision" && <p>Сервер выбирает подходящий условный переход. Укажите отдельный переход на случай, когда ни одно условие не выполнено.</p>}
    {block.kind === "resolution_check" && <p>Сотрудник отвечает «Да», «Нет» или «Не знаю». Настройте переходы для каждого результата либо общий запасной путь.</p>}
    {block.kind === "diagnostic" && <div className="space-y-3">
      <p role="status">Диагностика до создания обращения недоступна. Сервер вернёт «Недоступно» и продолжит по настроенному запасному пути.</p>
      <label><input disabled={disabled} type="checkbox" checked={block.require_consent ?? true} onChange={event => onChange({ ...block, require_consent: event.target.checked })} /> Запрашивать согласие</label>
      <p>Согласие хранится как настройка. В симуляции реального разрешения нет.</p>
      <p>{transitions.some(edge => !edge.when && targets.some(item => item.id === edge.to)) ? `Запасной шаг: ${targets.find(item => item.id === transitions.find(edge => !edge.when)?.to)?.title}` : "Запасной шаг не выбран. Публикация будет заблокирована."}</p>
      <p>Симулятор позволяет проверить недоступность, отказ в согласии, тайм-аут и отсутствие возможности проверки.</p>
    </div>}
    {block.kind === "review" && <p>Перед продолжением сотрудник увидит собранные ответы и сможет вернуться к вопросам.</p>}
    {block.kind === "submit_ticket" && <p>Обращение создаёт сервер с применением политик услуги. Этот блок завершает сценарий.</p>}
    {block.kind === "finish" && <label className="block">Сообщение о решении<textarea disabled={disabled} maxLength={2000} className="field-base min-h-24 w-full" value={block.message ?? ""} onChange={event => onChange({ ...block, message: event.target.value })} /></label>}
    {((definition.schema_version ?? 1) < 2 || block.kind === "diagnostic") && <AdvancedDisclosure title="Расширенные настройки" description="Совместимость исторического шага">
      <div className="min-w-0 space-y-4">
        <p className="break-all text-sm">Стабильный ключ: {block.id}</p>
        <p>{definition.entry_block_id === block.id ? "Первый блок сценария" : "Вход создаётся линией от «Начала» к этому блоку."}</p>
        {block.kind === "diagnostic" && <>
          <label className="block">Возможность диагностики<Select disabled value={block.capability ?? "endpoint.context.diagnostic.collect"}><option value="endpoint.context.diagnostic.collect">Контекст устройства (пока недоступно)</option></Select></label>
          <label className="block">Ожидание, секунд<Input disabled={disabled} type="number" min={1} max={120} value={block.timeout_seconds ?? 30} onChange={event => onChange({ ...block, timeout_seconds: Number(event.target.value) })} /></label>
        </>}
      </div>
    </AdvancedDisclosure>}
    {!hideTransitions && <section aria-label="Следующий шаг" className="space-y-4 rounded-lg border p-3">
        <h3 className="font-medium">Что делать дальше</h3>
        {!terminal && <p className="text-sm text-slate-600">Выберите следующий шаг. Порядок шагов в списке сам по себе не задаёт переходы. Последний переход без условия — запасной путь.</p>}
        {!transitions.length && <p className="text-sm">{terminal ? "Конечный блок не имеет переходов." : "Добавьте переходы. Перестановка блоков не изменяет маршруты автоматически."}</p>}
        {transitions.map((edge, index) => <fieldset disabled={disabled} key={index} className="min-w-0 space-y-3 rounded-lg border p-3">
          <legend>Переход {index + 1}</legend>
          <label className="block">Следующий блок<Select ref={index === issueTransitionIndex ? transitionRef : undefined} value={edge.to} onChange={event => onChange({ ...block, transitions: transitions.map((old, i) => i === index ? { ...old, to: event.target.value } : old) })}>
            {!targets.some(item => item.id === edge.to) && <option value={edge.to}>Целевой блок не найден</option>}
            {targets.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}
          </Select></label>
          <ScenarioConditionEditor label="Условие перехода" value={edge.when} fields={fields} resultValues={resultValues} disabled={disabled} onChange={when => onChange({ ...block, transitions: transitions.map((old, i) => i === index ? { ...old, when } : old) })} />
          {!edge.when && <p className="text-sm">Запасной переход: используется, когда условия других ветвей не выполнены. Поместите его последним.</p>}
          <label className="block">Порядок выбора при совпадении условий<Input type="number" min={1} max={10000} value={edge.priority ?? ""} onChange={event => onChange({ ...block, transitions: transitions.map((old, i) => i === index ? { ...old, priority: event.target.value ? Number(event.target.value) : null } : old) })} /></label>
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" onClick={() => onChange({ ...block, transitions: transitions.filter((_, i) => i !== index) })}>Удалить переход {index + 1}</Button>
            <Button variant="ghost" disabled={disabled || index === transitions.length - 1} onClick={() => onChange({ ...block, transitions: [...transitions.filter((_, i) => i !== index), edge] })}>Переместить переход в конец</Button>
          </div>
        </fieldset>)}
        <Button disabled={disabled || terminal || !targets.length || transitions.length >= 30} variant="secondary" onClick={() => onChange({ ...block, transitions: [...transitions, { to: targets[0].id, when: null }] })}>Добавить переход</Button>
    </section>}
  </div>;
}
