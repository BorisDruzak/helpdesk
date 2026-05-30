import { Wand2 } from "lucide-react";
import { Button } from "../../components/ui/button";
import type { AdminHelpdeskModelPayload } from "../forms-builder/api";
import { PROCESS_PROFILES, applyProfileDefaults, buildAutoFixSuggestions, applyAutoFix, type StudioDraft } from "./draft-model";
import { policyOptions } from "./options";

export function ProcessEditors({
  draft,
  registry,
  showAutoFix,
  onDraftChange,
  onShowAutoFixChange,
}: {
  draft: StudioDraft;
  registry: AdminHelpdeskModelPayload | null | undefined;
  showAutoFix: boolean;
  onDraftChange: (draft: StudioDraft) => void;
  onShowAutoFixChange: (value: boolean) => void;
}) {
  const suggestions = buildAutoFixSuggestions(draft, registry);
  const activeSuggestions = suggestions.filter((item) => item.available);
  return (
    <section className="surface-panel p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">Базовые блоки обработки</h2>
          <p className="mt-1 text-sm text-slate-600">Настройте маршрут, сроки, согласование, закрытие и уведомления без перехода в экспертные разделы.</p>
        </div>
        <Button type="button" variant="secondary" leadingIcon={<Wand2 className="h-4 w-4" />} onClick={() => onShowAutoFixChange(!showAutoFix)}>
          Исправить автоматически
        </Button>
      </div>

      {showAutoFix ? (
        <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="font-semibold text-amber-950">Безопасные автоисправления</h3>
              <p className="mt-1 text-sm text-amber-800">Studio применяет только существующие активные политики. Если политики нет, пункт остаётся рекомендацией для экспертной настройки.</p>
            </div>
            <Button type="button" disabled={!activeSuggestions.length} onClick={() => onDraftChange(activeSuggestions.reduce((current, suggestion) => applyAutoFix(current, suggestion), draft))}>
              Применить всё
            </Button>
          </div>
          <div className="mt-3 grid gap-2 md:grid-cols-2">
            {suggestions.map((suggestion) => (
              <div className="rounded-md border border-amber-200 bg-white p-3 text-sm" key={suggestion.label}>
                <p className="font-semibold text-slate-950">{suggestion.label}</p>
                <p className="mt-1 text-slate-600">{suggestion.description}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <section className="rounded-md border border-slate-200 bg-white p-4 xl:col-span-2">
          <h3 className="font-semibold text-slate-950">Раздел и тип обращения</h3>
          <div className="mt-3 grid gap-3 md:grid-cols-3">
            <label className="block text-sm font-semibold text-slate-800">
              Название для пользователей
              <input
                className="field-base mt-1 px-3 py-2"
                value={draft.title}
                onChange={(event) => onDraftChange({ ...draft, title: event.currentTarget.value })}
              />
            </label>
            <label className="block text-sm font-semibold text-slate-800 md:col-span-2">
              Краткое описание
              <input
                className="field-base mt-1 px-3 py-2"
                value={draft.description}
                onChange={(event) => onDraftChange({ ...draft, description: event.currentTarget.value })}
              />
            </label>
            <label className="block text-sm font-semibold text-slate-800">
              Видимость
              <select
                className="field-base mt-1 px-3 py-2"
                value={draft.visibility}
                onChange={(event) => onDraftChange({ ...draft, visibility: event.currentTarget.value as StudioDraft["visibility"] })}
              >
                <option value="public">Публичный</option>
                <option value="internal">Внутренний</option>
                <option value="restricted">Restricted</option>
              </select>
            </label>
          </div>
        </section>

        <section className="rounded-md border border-slate-200 bg-white p-4">
          <h3 className="font-semibold text-slate-950">Профиль обработки</h3>
          <label className="mt-3 block text-sm font-semibold text-slate-800">
            Профиль обработки
            <select className="field-base mt-1 px-3 py-2" value={draft.processProfile} onChange={(event) => onDraftChange({ ...draft, processProfile: event.currentTarget.value })}>
              {PROCESS_PROFILES.map((profile) => <option key={profile} value={profile}>{profile}</option>)}
            </select>
          </label>
          <p className="mt-3 text-sm text-slate-600">Будут предложены типовые маршрут, SLA, закрытие и уведомления, если такие политики есть в реестре.</p>
          <Button className="mt-3" type="button" variant="secondary" onClick={() => onDraftChange(applyProfileDefaults(draft, registry))}>
            Применить профиль
          </Button>
        </section>

        <section className="rounded-md border border-slate-200 bg-white p-4">
          <h3 className="font-semibold text-slate-950">Кто выполняет</h3>
          <label className="mt-3 block text-sm font-semibold text-slate-800">
            Кто выполняет заявку?
            <select className="field-base mt-1 px-3 py-2" value={draft.routingPolicyCode} onChange={(event) => onDraftChange({ ...draft, routingPolicyCode: event.currentTarget.value })}>
              <option value="">Выберите маршрут</option>
              {policyOptions(registry, "routing").map((option) => <option disabled={option.disabled} key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
          <p className="mt-2 text-xs text-slate-500">Если подходящего маршрута нет, нужна экспертная настройка routing policy.</p>
        </section>

        <section className="rounded-md border border-slate-200 bg-white p-4">
          <h3 className="font-semibold text-slate-950">SLA / сроки</h3>
          <label className="mt-3 block text-sm font-semibold text-slate-800">
            Срок выполнения
            <select className="field-base mt-1 px-3 py-2" value={draft.slaPolicyCode} onChange={(event) => onDraftChange({ ...draft, slaPolicyCode: event.currentTarget.value })}>
              <option value="">Выберите срок</option>
              {policyOptions(registry, "sla").map((option) => <option disabled={option.disabled} key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
          <div className="mt-3 grid gap-2 text-sm text-slate-600 sm:grid-cols-3">
            <span className="rounded-md bg-slate-50 px-3 py-2">Ответ: 30 мин / 1 час / 4 часа</span>
            <span className="rounded-md bg-slate-50 px-3 py-2">Решение: 4 часа / 1 день / 3 дня</span>
            <span className="rounded-md bg-slate-50 px-3 py-2">Пауза: пользователь / согласование / поставщик</span>
          </div>
        </section>

        <section className="rounded-md border border-slate-200 bg-white p-4">
          <h3 className="font-semibold text-slate-950">Согласование</h3>
          <div className="mt-3 flex flex-wrap gap-3">
            <label className="flex items-center gap-2 text-sm font-semibold text-slate-800">
              <input checked={draft.approvalMode === "none"} onChange={() => onDraftChange({ ...draft, approvalMode: "none", approvalPolicyCode: "" })} type="radio" />
              Согласование не требуется
            </label>
            <label className="flex items-center gap-2 text-sm font-semibold text-slate-800">
              <input checked={draft.approvalMode === "required"} onChange={() => onDraftChange({ ...draft, approvalMode: "required" })} type="radio" />
              Нужно согласование
            </label>
          </div>
          <label className="mt-3 block text-sm font-semibold text-slate-800">
            Кто согласует?
            <select className="field-base mt-1 px-3 py-2" disabled={draft.approvalMode === "none"} value={draft.approvalPolicyCode} onChange={(event) => onDraftChange({ ...draft, approvalPolicyCode: event.currentTarget.value })}>
              <option value="">Выберите правило согласования</option>
              {policyOptions(registry, "approval").map((option) => <option disabled={option.disabled} key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
        </section>

        <section className="rounded-md border border-slate-200 bg-white p-4">
          <h3 className="font-semibold text-slate-950">Закрытие</h3>
          <label className="mt-3 block text-sm font-semibold text-slate-800">
            Правила закрытия
            <select className="field-base mt-1 px-3 py-2" value={draft.closurePolicyCode} onChange={(event) => onDraftChange({ ...draft, closurePolicyCode: event.currentTarget.value })}>
              <option value="">Выберите правила закрытия</option>
              {policyOptions(registry, "closure").map((option) => <option disabled={option.disabled} key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
          <p className="mt-2 text-sm text-slate-600">Перед закрытием исполнитель должен указать результат, сообщение пользователю и код решения, если это требует policy.</p>
        </section>

        <section className="rounded-md border border-slate-200 bg-white p-4">
          <h3 className="font-semibold text-slate-950">Уведомления</h3>
          <label className="mt-3 block text-sm font-semibold text-slate-800">
            Уведомления
            <select className="field-base mt-1 px-3 py-2" value={draft.notificationPolicyCode || "__unused__"} onChange={(event) => onDraftChange({ ...draft, notificationPolicyCode: event.currentTarget.value === "__unused__" ? "" : event.currentTarget.value })}>
              <option value="__unused__">Не используется</option>
              {policyOptions(registry, "notification").map((option) => <option disabled={option.disabled} key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
          <p className="mt-2 text-sm text-slate-600">Отсутствие уведомлений не блокирует публикацию, но остаётся рекомендацией.</p>
        </section>
      </div>
    </section>
  );
}
